// AD9959 single-bit, MSB-first serial writes. One update for the complete bank.
// Serial startup uses the independent board clock, so DDS reset cannot deadlock it.
module dds_programmer(
    input wire clk, rst_n, update_clk,update_rst_n,
    input wire request_toggle, input wire [255:0] settings,
    output reg acknowledge_toggle, output reg ready,
    output reg mreset, cs_n, sclk, sdio,
    output reg io_update
);
    (* altera_attribute="-name SYNCHRONIZER_IDENTIFICATION FORCED_IF_ASYNCHRONOUS" *)
    reg [1:0] request_sync, update_ack_sync;
    reg update_toggle, update_ack;
    (* altera_attribute="-name SYNCHRONIZER_IDENTIFICATION FORCED_IF_ASYNCHRONOUS" *)
    reg [1:0] update_sync;
    reg [2:0] pulse_count;
    // Phase-advanced PLL launch, constrained to the specified DDS sampling edge.
    // The 4.8 ns DDS setup and positive hold are both checked in TimeQuest.
    always @(posedge update_clk or negedge update_rst_n) begin
        if(!update_rst_n) begin update_sync<=0;update_ack<=0;io_update<=0;pulse_count<=0;end
        else begin
            update_sync<={update_sync[0],update_toggle};
            if(io_update) begin
                if(pulse_count==3)begin io_update<=0;update_ack<=update_sync[1];end
                else pulse_count<=pulse_count+1'b1;
            end else if(update_sync[1]!=update_ack)begin io_update<=1;pulse_count<=0;end
        end
    end
    reg [4:0] frame;
    reg [39:0] shift_word;
    reg [5:0] bits_left;
    reg [9:0] delay_count;
    reg [3:0] state;
    reg accepted;
    reg [39:0] frame_word;
    reg [5:0] frame_bits;
    wire [1:0] channel=(frame-4)>>2;
    wire [63:0] channel_settings=settings[channel*64+:64];
    always @*begin
        frame_word=0;frame_bits=16;
        case(frame)
            0:frame_word={8'h00,8'hf0,24'd0}; // all channels, single-bit two-wire
            1:begin frame_word={8'h01,24'h000000,8'd0};frame_bits=32;end
            2:begin frame_word={8'h02,16'h0040,16'd0};frame_bits=24;end
            3:begin frame_word={8'h03,24'h000321,8'd0};frame_bits=32;end
            default:case(frame[1:0])
                0:frame_word={8'h00,(8'h10<<channel),24'd0};
                1:begin frame_word={8'h04,channel_settings[31:0]};frame_bits=40;end
                2:begin frame_word={8'h05,channel_settings[47:32],16'd0};frame_bits=24;end
                3:begin frame_word={8'h06,8'd0,(16'h1000|channel_settings[63:48]),8'd0};frame_bits=32;end
            endcase
        endcase
    end
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            request_sync<=0;update_ack_sync<=0;acknowledge_toggle<=0;ready<=0;
            update_toggle<=0;frame<=0;shift_word<=0;bits_left<=0;delay_count<=0;
            state<=0;accepted<=0;mreset<=1;cs_n<=1;sclk<=0;sdio<=0;
        end else begin
            request_sync<={request_sync[0],request_toggle};
            update_ack_sync<={update_ack_sync[0],update_ack};
            case(state)
                0:if(delay_count==499)begin mreset<=0;delay_count<=0;state<=1;end
                  else delay_count<=delay_count+1'b1;
                1:if(delay_count==499)begin delay_count<=0;ready<=1;state<=8;end
                  else delay_count<=delay_count+1'b1;
                2:begin
                    shift_word<=frame_word;bits_left<=frame_bits;
                    sdio<=frame_word[39];cs_n<=0;sclk<=0;delay_count<=9;state<=3;
                end
                3:if(delay_count!=0)delay_count<=delay_count-1'b1;
                  else begin sclk<=1;delay_count<=9;state<=4;end
                4:if(delay_count!=0)delay_count<=delay_count-1'b1;
                  else begin
                    sclk<=0;delay_count<=9;
                    if(bits_left==1)state<=5;
                    else begin shift_word<=shift_word<<1;sdio<=shift_word[38];bits_left<=bits_left-1'b1;state<=3;end
                  end
                5:if(delay_count!=0)delay_count<=delay_count-1'b1;
                  else begin cs_n<=1;delay_count<=9;state<=6;end
                6:if(delay_count!=0)delay_count<=delay_count-1'b1;
                  else if(frame==19)begin update_toggle<=~update_toggle;state<=7;end
                  else begin frame<=frame+1'b1;state<=2;end
                7:if(update_ack_sync[1]==update_toggle)begin
                    acknowledge_toggle<=accepted;ready<=1;state<=8;
                  end
                8:if(request_sync[1]!=acknowledge_toggle)begin
                    accepted<=request_sync[1];ready<=0;frame<=0;state<=2;
                  end
                default:state<=0;
            endcase
        end
    end
endmodule
