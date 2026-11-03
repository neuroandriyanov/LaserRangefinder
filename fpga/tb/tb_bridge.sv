`timescale 1ns/1ps
module tb_bridge;
 reg src_clk=0,dst_clk=0;always #4 src_clk=~src_clk;always #10 dst_clk=~dst_clk;
 reg rst_n=0,hold=0,publish=0,sv=0;
 reg [143:0] sp=0;reg [63:0] periods_in=0;reg [15:0] seq_in=0;
 wire [143:0] p;wire [63:0] periods;wire [15:0] seq;
 wire valid,update,overrun,ready;
 digital_phase_bridge dut(src_clk,rst_n,dst_clk,rst_n,hold,publish,sv,sp,
    periods_in,seq_in,p,periods,seq,valid,update,overrun,ready);
 task send(input [15:0] epoch);
  begin
   wait(ready);@(negedge src_clk);
   seq_in=epoch;sp={9{epoch}};periods_in={4{epoch}};sv=1;publish=1;
   @(negedge src_clk);publish=0;
  end
 endtask
 always @(negedge dst_clk)if(update)begin
  if(p!=={9{seq}} || periods!=={4{seq}})$fatal(1,"mixed CDC epoch");
 end
 initial begin
  #100;rst_n=1;
  send(1);wait(update);#1;if(!valid || seq!=1)$fatal(1,"initial epoch");
  @(negedge dst_clk);hold=1;send(2);
  #500;if(seq!=1 || ready)$fatal(1,"hold failed");
  hold=0;wait(update);#1;if(seq!=2 || !valid)$fatal(1,"held epoch lost");
  wait(ready);@(negedge dst_clk);hold=1;send(3);sv=0;
  #200;if(valid)$fatal(1,"fault did not clear live validity");
  hold=0;wait(update);#1;if(valid)$fatal(1,"old pending record became valid");
  wait(ready);#100;sv=1;
  #100;if(valid)$fatal(1,"old data reused on recovery before publication");
  send(4);wait(update);#1;if(!valid || seq!=4 || overrun)$fatal(1,"recovery");
  $display("PASS bridge: coherent epochs, backpressure, live fault, no stale recovery");$finish;
 end
 initial begin #10000;$fatal(1,"bridge timeout");end
endmodule
