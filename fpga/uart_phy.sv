// 50 MHz / 434 = 115207.37 baud, 8N1. RX is asynchronous to this clock.
module uart_phy #(parameter integer DIVISOR=434)(
    input wire clk,rst_n,rx,start,input wire [7:0] tx_data,
    output reg tx,busy,done,output reg [7:0] rx_data,
    output reg rx_valid,framing_error);
    (* altera_attribute="-name SYNCHRONIZER_IDENTIFICATION FORCED_IF_ASYNCHRONOUS" *)
    reg [1:0] rx_sync;
    reg [15:0] tx_count,rx_count;
    reg [3:0] tx_bit,rx_bit;
    reg [9:0] tx_shift;
    reg [7:0] rx_shift;
    reg [1:0] rx_state;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) rx_sync<=2'b11; else rx_sync<={rx_sync[0],rx};
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            tx<=1;busy<=0;done<=0;tx_count<=0;tx_bit<=0;tx_shift<=10'h3ff;
            rx_count<=0;rx_bit<=0;rx_shift<=0;rx_state<=0;
            rx_data<=0;rx_valid<=0;framing_error<=0;
        end else begin
            done<=0;rx_valid<=0;framing_error<=0;
            if(!busy) begin
                if(start) begin
                    tx_shift<={1'b1,tx_data,1'b0};tx<=0;busy<=1;tx_count<=16'(DIVISOR-1);tx_bit<=0;
                end
            end else if(tx_count!=0) tx_count<=tx_count-1'b1;
            else if(tx_bit==9) begin tx<=1;busy<=0;done<=1;end
            else begin
                tx_shift<={1'b1,tx_shift[9:1]};tx<=tx_shift[1];
                tx_bit<=tx_bit+1'b1;tx_count<=16'(DIVISOR-1);
            end
            case(rx_state)
                0:if(!rx_sync[1]) begin rx_count<=16'(DIVISOR/2-1);rx_state<=1;end
                1:if(rx_count!=0) rx_count<=rx_count-1'b1;
                  else if(rx_sync[1]) rx_state<=0;
                  else begin rx_count<=16'(DIVISOR-1);rx_bit<=0;rx_state<=2;end
                2:if(rx_count!=0) rx_count<=rx_count-1'b1;
                  else begin
                      rx_shift<={rx_sync[1],rx_shift[7:1]};rx_count<=16'(DIVISOR-1);
                      if(rx_bit==7) rx_state<=3;else rx_bit<=rx_bit+1'b1;
                  end
                3:if(rx_count!=0) rx_count<=rx_count-1'b1;
                  else begin
                      rx_state<=0;
                      if(rx_sync[1]) begin rx_data<=rx_shift;rx_valid<=1;end
                      else framing_error<=1;
                  end
            endcase
        end
    end
endmodule
