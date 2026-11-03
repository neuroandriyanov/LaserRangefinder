`timescale 1ns/1ps
module tb_variable_digital;
reg clk=0,rst_n=0;always #4 clk=~clk;
reg [31:0] dh=65536,dl=40960;reg [17:0] eh=16384,el=26214;
reg [3:0] raw_signals=0,enabled=15;wire [3:0] signals=raw_signals & enabled;
wire [143:0] phases;wire [63:0] periods;wire [15:0] seq;wire valid,rv,overflow;
digital_phase_meter dut(clk,rst_n,signals,1'b1,dh,dl,eh,el,phases,periods,seq,valid,rv,overflow);
real cycles,offset;integer mode,checks=0;
for(genvar ch=0;ch<4;ch=ch+1)begin: stimulus
 real period_ns,delay_ns;
 initial forever begin
  wait(rst_n);
  period_ns=8589934592.0/((ch%2)?$itor(dl):$itor(dh));
  delay_ns=(ch==2)?period_ns*(1.0-179.8/360.0):((ch==3)?period_ns*73.56/360.0:0.0);
  #(delay_ns);
  while(rst_n)begin raw_signals[ch]=1;#(period_ns/2);raw_signals[ch]=0;#(period_ns/2);end
 end
end
function real err(input [23:0] v,input real target);
 real d;begin d=$itor($signed(v))*360.0/16777216.0-target;
 while(d>180)d=d-360;while(d< -180)d=d+360;err=d<0?-d:d;end
endfunction
initial begin
 for(mode=0;mode<3;mode=mode+1)begin
  rst_n=0;#2100000;
  case(mode)
   0:begin dh=65536;dl=40960;eh=16384;el=26214;end
   1:begin dh=171799;dl=8590;eh=6250;el=124999;end
   2:begin dh=8590;dl=171799;eh=124999;el=6250;end
  endcase
  rst_n=1;
  repeat(2)begin
   @(posedge rv);#1;
   if(!valid || overflow || err(phases[0+:24],179.8)>0.065 || err(phases[24+:24],-73.56)>0.065)
    $fatal(1,"variable digital mode=%0d valid=%d phases=%f %f",mode,valid,err(phases[0+:24],179.8),err(phases[24+:24],-73.56));
   if(periods[31:0]+1<eh || periods[31:0]>eh+1 || periods[63:32]+1<el || periods[63:32]>el+1)$fatal(1,"period truncation");
   checks=checks+1;
  end
  enabled[3]=0;#1600000;if(valid)$fatal(1,"loss at low IF remained valid");
  enabled[3]=1;@(posedge rv);#1;if(!valid)$fatal(1,"recovery");
  $display("PASS variable digital mode=%0d periods=%0d/%0d",mode,periods[31:0],periods[63:32]);
 end
 $display("PASS variable digital: %0d phase checks, 1..20kHz, unequal periods, loss/recovery",checks);$finish;
end
initial begin #180000000;$fatal(1,"variable digital timeout");end
endmodule
