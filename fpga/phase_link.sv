// Protocol v3: request/reply only; immutable byte RAM snapshot.
module phase_link #(parameter integer UART_DIVISOR=434)(
    input wire clk,rst_n,rx,result_valid,window_full,
    input wire [3:0] channel_valid,window_bad,input wire [7:0] adc_ok,
    input wire [31:0] phase_high,phase_low,sample_index,
    input wire [127:0] magnitudes,samples,input wire processing_overrun,
    input wire [143:0] digital_phases,input wire [63:0] digital_periods,
    input wire [15:0] digital_sequence,input wire digital_valid,digital_update,digital_overflow,
    input wire config_done,measuring,input wire [7:0] config_status,
    input wire [255:0] settings,input wire [15:0] generation,
    input wire [31:0] delta_high,delta_low,
    output reg config_start,output reg [7:0] config_parameter,output reg [15:0] config_value,
    output wire tx,output wire [15:0] min_amplitude,output wire snapshot_hold);
    function [15:0] crc_byte(input [15:0] old_crc,input [7:0] b);
        reg [15:0] c;integer k;
        begin c=old_crc^{8'b0,b};for(k=0;k<8;k=k+1)c=c[0]?(c>>1)^16'ha001:c>>1;crc_byte=c;end
    endfunction
    assign min_amplitude=16'd100;
    // ADC5..8 are DC detector voltages, not the AC amplitudes from ADC1..4.
    // ADS8681 offset binary, +/-12.288 V. Require |U| >= 0.5 V, either polarity.
    // 0.5 V / 0.000375 V = 1333.333 counts; accept codes <=31434 or >=34102.
    function detector_level_ok(input [15:0] code);
        begin detector_level_ok=(code<=16'd31434 || code>=16'd34102);end
    endfunction
    wire detector_ok=detector_level_ok(samples[64+:16]) &&
        detector_level_ok(samples[80+:16]) &&
        detector_level_ok(samples[96+:16]) &&
        detector_level_ok(samples[112+:16]);
    wire byte_done,byte_busy,rx_valid,framing_error;
    wire [7:0] rx_data;
    reg byte_start;reg [7:0] tx_data;
    uart_phy #(.DIVISOR(UART_DIVISOR)) phy(.clk(clk),.rst_n(rst_n),.rx(rx),.tx(tx),
        .start(byte_start),.tx_data(tx_data),.busy(byte_busy),.done(byte_done),
        .rx_data(rx_data),.rx_valid(rx_valid),.framing_error(framing_error));
    reg [3:0] rx_index;
    reg [15:0] rx_crc,request_id,request_value;
    reg [7:0] crc_low,command,param;
    reg [20:0] rx_timeout;
    reg header_ok,rx_error,queue_overflow,pending;
    reg [7:0] pending_command,pending_param;
    reg [15:0] pending_id,pending_value;
    reg pending_argument_bad;
    reg [31:0] sequence_number;
    reg [6:0] invalid_ms;
    reg beam_lost;
    reg [7:0] digital_age;
    wire analog_ok=window_full && !processing_overrun && measuring && detector_ok;
    wire digital_ok=digital_valid && digital_age<20 && measuring && detector_ok;
    wire both_valid=(&channel_valid) && (&adc_ok) && analog_ok && digital_ok;
    wire beam_next=both_valid?1'b0:(invalid_ms>=99 || beam_lost);
    wire [7:0] flags={processing_overrun,rx_error,(!window_full || !measuring),|window_bad,
        (adc_ok!=8'hff),beam_next,
        (channel_valid[1]&channel_valid[3]&adc_ok[1]&adc_ok[3]&analog_ok),
        (channel_valid[0]&channel_valid[2]&adc_ok[0]&adc_ok[2]&analog_ok)};
    localparam IDLE=0,WAIT_RESULT=1,BUILD=2,PREPARE=3,SEND=4,WAIT_BYTE=5,LOAD_WORD=6,WAIT_SET=7;
    reg [2:0] state;
    reg [7:0] response_kind,response_status,response_param,snapshot_flags,snapshot_digital;
    reg [15:0] response_id,tx_crc;
    reg [6:0] length,build_index,tx_index;
    reg [31:0] build_word,build_word_mux;
    always @(posedge clk)build_word<=build_word_mux;
    wire [7:0] build_byte=(build_index==length-2)?tx_crc[7:0]:
        (build_index==length-1)?tx_crc[15:8]:build_word[build_index[1:0]*8+:8];
    (* ramstyle="M9K" *) reg [7:0] packet_mem[0:127];
    reg [7:0] packet_read;
    always @(posedge clk)begin
        packet_read<=packet_mem[tx_index];
        if(state==BUILD)packet_mem[build_index]<=build_byte;
    end
    assign snapshot_hold=(state==BUILD || state==LOAD_WORD);
    // Analog fields are stable ~1 ms after result_valid; RAM fills in <2 us.
    // The digital bridge holds its epoch for the entire RAM fill.
    always @*begin
        build_word_mux=0;
        if(length==48 && build_index>=12)begin
            if(build_index<44)build_word_mux=settings[(build_index[6:2]-3)*32+:32];
        end
        else case(build_index[6:2])
            0:build_word_mux={1'b0,length,8'd3,8'h5a,8'ha5};
            1:build_word_mux=(length==12)?{8'd0,response_param,response_status,response_kind}:
                ((length==48)?{7'd0,!measuring,8'h80,response_status,response_kind}:
                {snapshot_digital,snapshot_flags,response_status,response_kind});
            2:build_word_mux=(length==48)?{generation,response_id}:{4'd0,channel_valid,adc_ok,response_id};
            3:build_word_mux=sequence_number;
            4:build_word_mux=sample_index;
            5:build_word_mux=phase_high;
            6:build_word_mux=phase_low;
            7:build_word_mux={digital_phases[0+:24],8'd0};
            8:build_word_mux={digital_phases[24+:24],8'd0};
            9:build_word_mux={digital_phases[48+:24],8'd0};
            10:build_word_mux={digital_phases[72+:24],8'd0};
            11:build_word_mux={digital_phases[96+:24],8'd0};
            12:build_word_mux={digital_phases[120+:24],8'd0};
            13:build_word_mux=magnitudes[0+:32];
            14:build_word_mux=magnitudes[32+:32];
            15:build_word_mux=magnitudes[64+:32];
            16:build_word_mux=magnitudes[96+:32];
            17:build_word_mux=samples[0+:32];
            18:build_word_mux=samples[32+:32];
            19:build_word_mux=samples[64+:32]; // ADC5/6 detector outputs
            20:build_word_mux=samples[96+:32]; // ADC7/8 detector outputs
            21:build_word_mux={16'd100,digital_sequence};
            22:build_word_mux=digital_periods[31:0];
            23:build_word_mux=digital_periods[63:32];
            24:build_word_mux={generation,5'd0,digital_overflow,queue_overflow,rx_error,digital_age};
            25:build_word_mux=delta_high;
            26:build_word_mux=delta_low;
            27:build_word_mux={24'd0,7'd0,!measuring};
            default:build_word_mux=0;
        endcase
    end
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            rx_index<=0;rx_crc<=16'hffff;crc_low<=0;command<=0;param<=0;request_id<=0;request_value<=0;
            rx_timeout<=0;header_ok<=0;rx_error<=0;queue_overflow<=0;pending<=0;
            pending_command<=0;pending_param<=0;pending_id<=0;pending_value<=0;pending_argument_bad<=0;
            config_start<=0;config_parameter<=0;config_value<=0;
            sequence_number<=0;invalid_ms<=0;beam_lost<=0;digital_age<=255;
            response_kind<=0;response_status<=0;response_param<=0;response_id<=0;
            snapshot_flags<=0;snapshot_digital<=0;length<=0;build_index<=0;tx_index<=0;
            state<=IDLE;tx_crc<=16'hffff;byte_start<=0;tx_data<=0;
        end else begin
            byte_start<=0;config_start<=0;
            if(digital_update)digital_age<=0;
            else if(result_valid && digital_age!=255)digital_age<=digital_age+1'b1;
            if(result_valid)begin
                sequence_number<=sequence_number+1'b1;
                if(both_valid)begin invalid_ms<=0;beam_lost<=0;end
                else begin if(invalid_ms<100)invalid_ms<=invalid_ms+1'b1;beam_lost<=beam_next;end
            end
            case(state)
                IDLE:if(pending)begin
                    pending<=0;response_id<=pending_id;response_param<=pending_param;
                    build_index<=0;tx_index<=0;tx_crc<=16'hffff;
                    if(pending_command==2 && !pending_argument_bad)begin
                        response_kind<=8'h82;response_status<=0;
                        if(pending_param==1)begin length<=48;state<=LOAD_WORD;end
                        else begin length<=112;state<=WAIT_RESULT;end
                    end else if(pending_command==1)begin
                        length<=12;response_kind<=8'h81;state<=WAIT_SET;
                        config_parameter<=pending_param;config_value<=pending_value;config_start<=1;
                    end else begin
                        length<=12;state<=LOAD_WORD;
                        response_kind<=(pending_command==1)?8'h81:((pending_command==2)?8'h82:8'hff);
                        response_status<=(pending_command==1)?8'd1:((pending_command==2)?8'd3:8'd2);
                    end
                end
                WAIT_SET:if(config_done)begin response_status<=config_status;state<=LOAD_WORD;end
                WAIT_RESULT:if(result_valid || !measuring)begin
                    snapshot_flags<=flags;snapshot_digital<={6'd0,digital_ok,digital_ok};state<=LOAD_WORD;
                end
                BUILD:begin
                    if(build_index>=2 && build_index<length-2)tx_crc<=crc_byte(tx_crc,build_byte);
                    if(build_index==length-1)begin tx_index<=0;state<=PREPARE;end
                    else begin
                        build_index<=build_index+1'b1;
                        if(build_index[1:0]==3)state<=LOAD_WORD;
                    end
                end
                LOAD_WORD:state<=BUILD;
                PREPARE:state<=SEND;
                SEND:begin tx_data<=packet_read;byte_start<=1;state<=WAIT_BYTE;end
                WAIT_BYTE:if(byte_done)begin
                    if(tx_index==length-1)state<=IDLE;
                    else begin tx_index<=tx_index+1'b1;state<=PREPARE;end
                end
                default:state<=IDLE;
            endcase
            if(framing_error)begin rx_error<=1;rx_index<=0;end
            if(rx_index!=0)begin
                if(rx_timeout==1500000)begin rx_index<=0;rx_error<=1;rx_timeout<=0;end
                else rx_timeout<=rx_timeout+1'b1;
            end
            if(rx_valid)begin
                rx_timeout<=0;
                if(rx_index==0)begin if(rx_data==8'ha5)rx_index<=1;end
                else if(rx_index==1)begin
                    if(rx_data==8'h5a)begin rx_index<=2;rx_crc<=16'hffff;header_ok<=1;end
                    else if(rx_data!=8'ha5)rx_index<=0;
                end else begin
                    rx_index<=rx_index+1'b1;
                    if(rx_index>=2 && rx_index<=9)rx_crc<=crc_byte(rx_crc,rx_data);
                    case(rx_index)
                        2:if(rx_data!=3)header_ok<=0;
                        3:if(rx_data!=12)header_ok<=0;
                        4:command<=rx_data;
                        5:param<=rx_data;
                        6:request_id[7:0]<=rx_data;
                        7:request_id[15:8]<=rx_data;
                        8:request_value[7:0]<=rx_data;
                        9:request_value[15:8]<=rx_data;
                        10:crc_low<=rx_data;
                        11:begin
                            rx_index<=0;
                            if(header_ok && {rx_data,crc_low}==rx_crc)begin
                                if(!pending)begin
                                    pending<=1;pending_command<=command;pending_param<=param;pending_id<=request_id;
                                    pending_value<=request_value;pending_argument_bad<=(param>1 || request_value!=0);
                                end else queue_overflow<=1;
                            end else rx_error<=1;
                        end
                    endcase
                end
            end
        end
    end
endmodule
