// Atomic UART transaction: BEGIN, sixteen 16-bit words, COMMIT. Staging never
// touches hardware. The settings bus is held throughout the board-clock CDC.
module dds_settings(input wire clk,rst_n,start,input wire [7:0] parameter_id,
    input wire [15:0] value,input wire dds_ready,dds_acknowledge,
    output reg done,output reg [7:0] status,
    output wire [255:0] active_settings,output reg request_toggle,
    output wire measuring,output reg [15:0] generation,
    output reg [31:0] delta_high,delta_low,step_high,step_low,
    output reg [17:0] period_high,period_low);
    // Selected bench profile; physical pairs remain CH0/2 LF and CH1/3 HF.
    localparam [255:0] DEFAULTS={16'd450,16'd0,32'd635830272,
        16'd1000,16'd0,32'd12879416,16'd1000,16'd0,32'd635888254,
        16'd200,16'd0,32'd12845056};
    localparam [31:0] DEFAULT_HIGH=DEFAULTS[64+:32]-DEFAULTS[192+:32];
    localparam [31:0] DEFAULT_LOW=DEFAULTS[128+:32]-DEFAULTS[0+:32];
    reg [31:0] frequencies[0:3];
    reg [13:0] offsets[0:3];
    reg [9:0] amplitudes[0:3];
    genvar c;
    generate for(c=0;c<4;c=c+1)begin: bank
        assign active_settings[c*64+:64]={6'd0,amplitudes[c],2'd0,offsets[c],frequencies[c]};
    end endgenerate
    (* ramstyle="M9K" *) reg [15:0] staging[0:15];
    reg [15:0] stage_read,word_low;
    reg [3:0] scan;
    reg [31:0] low_base,high_base;
    reg [17:0] pending_high,pending_low;
    reg invalid_bank,inhibit,boot;
    wire [31:0] frequency={stage_read,word_low};
    wire [31:0] difference=scan[3:2]==2?frequency-low_base:high_base-frequency;
    always @(posedge clk)begin
        stage_read<=staging[scan];
        if(start && state==1 && transaction && parameter_id>=16 && parameter_id<=31)
            staging[parameter_id[3:0]]<=value;
    end
    reg [15:0] written;
    reg transaction;
    reg [3:0] state;
    reg [16:0] settling;
    (* altera_attribute="-name SYNCHRONIZER_IDENTIFICATION FORCED_IF_ASYNCHRONOUS" *)
    reg [1:0] ready_sync,ack_sync;
    assign measuring=!inhibit && ready_sync[1] && ack_sync[1]==request_toggle;
    // Restoring divider computes round(2^30 / delta FTW), in 32 clocks.
    reg [31:0] dividend,quotient;
    reg [18:0] remainder;
    reg [17:0] divisor;
    reg [5:0] division_count;
    reg division_low;
    wire [19:0] trial={remainder,dividend[31]};
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            done<=0;status<=0;for(integer c=0;c<4;c=c+1)begin
                frequencies[c]<=DEFAULTS[c*64+:32];offsets[c]<=0;amplitudes[c]<=DEFAULTS[c*64+48+:10];
            end
            written<=0;transaction<=0;
            scan<=0;word_low<=0;low_base<=0;high_base<=0;pending_high<=0;pending_low<=0;invalid_bank<=0;inhibit<=1;boot<=1;
            request_toggle<=0;generation<=0;state<=0;settling<=0;ready_sync<=0;ack_sync<=0;
            delta_high<=DEFAULT_HIGH;delta_low<=DEFAULT_LOW;
            step_high<=DEFAULT_HIGH*32'd2000;step_low<=DEFAULT_LOW*32'd2000;
            period_high<=(32'h40000000+DEFAULT_HIGH/2)/DEFAULT_HIGH;
            period_low<=(32'h40000000+DEFAULT_LOW/2)/DEFAULT_LOW;
            dividend<=0;quotient<=0;remainder<=0;divisor<=0;division_count<=0;division_low<=0;
        end else begin
            done<=0;ready_sync<={ready_sync[0],dds_ready};ack_sync<={ack_sync[0],dds_acknowledge};
            case(state)
                0:if(ready_sync[1])begin request_toggle<=~ack_sync[1];state<=5;end
                1:if(start)begin
                    done<=1;status<=3;
                    if(parameter_id==8'hf0 && value==16'hb001)begin transaction<=1;written<=0;status<=4;end
                    else if(parameter_id==8'hf2 && value==0)begin transaction<=0;written<=0;status<=0;end
                    else if(parameter_id>=8'h10 && parameter_id<=8'h1f)begin
                        if(transaction)begin
                            written[parameter_id[3:0]]<=1;status<=4;
                        end else status<=6;
                    end else if(parameter_id==8'hf1 && value==16'ha55a)begin
                        if(!transaction || written!=16'hffff)status<=6;
                        else begin done<=0;scan<=0;invalid_bank<=0;state<=7;end
                    end else if(parameter_id<16)status<=1; // reserved legacy stub IDs
                end
                2:begin
                    divisor<=division_low?delta_low[17:0]:delta_high[17:0];
                    dividend<=32'h40000000;quotient<=0;remainder<=0;division_count<=0;state<=3;
                end
                3:begin
                    dividend<=dividend<<1;quotient<={quotient[30:0],trial>=divisor};
                    remainder<=trial>=divisor?trial-divisor:trial;
                    if(division_count==31)state<=4;else division_count<=division_count+1'b1;
                end
                4:begin
                    if(division_low)begin
                        period_low<=quotient[17:0]+((remainder<<1)>=divisor);
                        request_toggle<=~request_toggle;state<=5;
                    end else begin
                        period_high<=quotient[17:0]+((remainder<<1)>=divisor);
                        division_low<=1;state<=2;
                    end
                end
                5:if(ack_sync[1]==request_toggle && ready_sync[1])begin if(!boot)generation<=generation+1'b1;boot<=0;settling<=0;state<=6;end
                6:if(settling==99999)begin
                    state<=1;inhibit<=0;if(generation!=0)begin done<=1;status<=0;end
                end else settling<=settling+1'b1;
                7:state<=8; // Synchronous staging RAM latency.
                8:begin
                    case(scan[1:0])
                        0:word_low<=stage_read;
                        1:begin
                            if(frequency==0 || frequency[31])invalid_bank<=1;
                            case(scan[3:2])
                                0:low_base<=frequency;
                                1:high_base<=frequency;
                                2,3:begin
                                    if(difference<8590 || difference>171799)invalid_bank<=1;
                                    if(scan[3:2]==2)pending_low<=difference[17:0];
                                    else pending_high<=difference[17:0];
                                end
                            endcase
                        end
                        2:if(stage_read>16383)invalid_bank<=1;
                        3:if(stage_read>1023)invalid_bank<=1;
                    endcase
                    if(scan==15)state<=9;
                    else begin scan<=scan+1'b1;state<=7;end
                end
                9:begin
                    if(invalid_bank)begin status<=3;done<=1;state<=1;end
                    else begin inhibit<=1;scan<=0;state<=10;transaction<=0;written<=0;end
                end
                10:state<=11;
                11:begin
                    case(scan[1:0])
                        0:frequencies[scan[3:2]][15:0]<=stage_read;
                        1:frequencies[scan[3:2]][31:16]<=stage_read;
                        2:offsets[scan[3:2]]<=stage_read[13:0];
                        3:amplitudes[scan[3:2]]<=stage_read[9:0];
                    endcase
                    if(scan==15)begin
                        delta_high<={14'd0,pending_high};delta_low<={14'd0,pending_low};
                        // 2000 = 2048-32-16, narrow FTW deltas avoid extra DSPs.
                        step_high<=({14'd0,pending_high}<<11)-({14'd0,pending_high}<<5)-({14'd0,pending_high}<<4);
                        step_low<=({14'd0,pending_low}<<11)-({14'd0,pending_low}<<5)-({14'd0,pending_low}<<4);
                        state<=2;division_low<=0;
                    end else begin scan<=scan+1'b1;state<=10;end
                end
                default:state<=0;
            endcase
            if(start && state!=1)begin done<=1;status<=5;end
        end
    end
endmodule

