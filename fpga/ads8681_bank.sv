// Eight independent ADS8681, shared timing. TI SBAS633E pages 9, 38-44, 51-53.
// 50 MHz clock; 250 kSPS; SPI mode 0, 12.5 MHz. All apertures on the same edge.
module ads8681_bank #(
    parameter integer RESET_CYCLES=50,
    parameter integer POR_CYCLES=1000000,
    parameter integer PERIOD=200
)(
    input wire clk, rst_n,
    input wire [7:0] sdo,
    output reg adc_reset_n, cs, sclk, sdi,
    output reg sample_valid,
    output reg [127:0] samples,
    output reg [7:0] adc_ok, sample_error,
    output reg initialized
);
    reg [20:0] wait_count;
    reg [1:0] state;
    reg [7:0] cycle;
    reg [3:0] step;
    reg [5:0] bit_count;
    reg [31:0] tx;
    reg [31:0] rx [0:7];
    integer ch;
    function [31:0] command_word(input [3:0] index);
        case(index)
            0: command_word=32'hD0140000; // +/-12.288 V, internal reference
            1: command_word=32'hC8140000; // read RANGE, returned in frame 2
            3: command_word=32'hD0100005; // test: all ones
            5: command_word=32'hD0100004; // test: all zeros
            7: command_word=32'hD0100000; // real conversion, no appended flags
            8: command_word=32'hC8100000;
            10:command_word=32'hC80C0000; // confirm single-SDO SPI mode
            default:command_word=0;
        endcase
    endfunction
    wire [31:0] next_command=command_word(step);
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=0; wait_count<=0; cycle<=0; step<=0; bit_count<=0;
            adc_reset_n<=0; cs<=0; sclk<=0; sdi<=0; tx<=0;
            adc_ok<=8'hFF; sample_error<=8'hFF; initialized<=0;
            sample_valid<=0; samples<=0;
            for(ch=0;ch<8;ch=ch+1) rx[ch]<=0;
        end else begin
            sample_valid<=0;
            case(state)
                0: if(wait_count==RESET_CYCLES-1) begin
                    adc_reset_n<=1; wait_count<=0; state<=1;
                end else wait_count<=wait_count+1'b1;
                1: if(wait_count==POR_CYCLES-1) begin
                    cs<=1; cycle<=0; state<=2; // first conversion, no stale sample published
                end else wait_count<=wait_count+1'b1;
                2: begin
                    if(cycle==40) begin // 820 ns after preceding CONVST edge
                        cs<=0; tx<=next_command; sdi<=next_command[31];
                        bit_count<=0;
                        for(ch=0;ch<8;ch=ch+1) rx[ch]<=0;
                    end
                    if(cycle>=42 && cycle<=168) begin
                        if(cycle[1:0]==2) begin
                            sclk<=1;
                            for(ch=0;ch<8;ch=ch+1) rx[ch]<={rx[ch][30:0],sdo[ch]};
                        end
                        if(cycle[1:0]==0) begin
                            sclk<=0; tx<={tx[30:0],1'b0}; sdi<=tx[30];
                            bit_count<=bit_count+1'b1;
                        end
                    end
                    if(cycle==PERIOD-1) begin
                        cycle<=0; cs<=1; sdi<=0;
                        for(ch=0;ch<8;ch=ch+1) begin
                            if((step==2 || step==6 || step==9 || step==11) && rx[ch][31:16]!=0)
                                adc_ok[ch]<=0;
                            if(step==4 && rx[ch][31:16]!=16'hFFFF) adc_ok[ch]<=0;
                            if(step>=12) begin
                                samples[ch*16+:16]<=rx[ch][31:16];
                                sample_error[ch]<=!adc_ok[ch] || rx[ch][15:0]!=0;
                            end
                        end
                        if(step<12) step<=step+1'b1;
                        else begin initialized<=1; sample_valid<=1; end
                    end else cycle<=cycle+1'b1;
                end
                default:state<=0;
            endcase
        end
    end
endmodule
