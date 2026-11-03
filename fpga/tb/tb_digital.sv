`timescale 1ns/1ps
module tb_digital;
reg clk=0,rst_n=0;always #4 clk=~clk;
reg [3:0] signals=0;
real phase[0:3],duty[0:3];
reg [3:0] enable_ch=15;
reg [3:0] glitch=0;
wire [143:0] phases;wire [63:0] periods;wire [15:0] seq;
wire valid,rv,overflow;
digital_phase_meter dut(clk,rst_n,signals,1'b1,32'd103079,32'd103079,18'd10417,18'd10417,phases,periods,seq,valid,rv,overflow);
localparam real PERIOD=83333.507232;
real cycle;
always @(negedge clk) begin
 #1;
 for(integer ch=0;ch<4;ch=ch+1)begin
  cycle=$realtime/PERIOD+phase[ch]/360.0;
  cycle=cycle-$floor(cycle);
  signals[ch]=enable_ch[ch] && ((cycle<duty[ch])^glitch[ch]);
 end
end
function real degrees(input [23:0] x);
 degrees=$itor($signed(x))*360.0/16777216.0;
endfunction
function real error(input real got,want);
 real d;begin d=got-want;while(d>180)d=d-360;while(d< -180)d=d+360;error=(d<0)?-d:d;end
endfunction
task check(input real high,low,tolerance);
 begin
  repeat(3)@(posedge rv);#1;
  if(!valid)$fatal(1,"digital invalid");
  if(error(degrees(phases[0+:24]),high)>tolerance || error(degrees(phases[24+:24]),low)>tolerance)
   $fatal(1,"digital phase got %f %f want %f %f",degrees(phases[0+:24]),degrees(phases[24+:24]),high,low);
  if(periods[15:0]<10415 || periods[15:0]>10418)$fatal(1,"digital period %d",periods[15:0]);
 end
endtask
initial begin
 phase[0]=10;phase[1]=20;phase[2]=130;phase[3]=-10;
 for(integer ch=0;ch<4;ch=ch+1)duty[ch]=0.5;
 #101;rst_n=1;
 check(120,-30,0.05);
 // Unequal duty: rising stays +120, falling shifts by -18 degrees.
 duty[2]=0.55;check(111,-30,0.05);
 if(error(degrees(phases[48+:24]),120)>0.05 || error(degrees(phases[72+:24]),102)>0.05)$fatal(1,"edge polarities");
 duty[2]=0.5;phase[0]=0;phase[1]=0;phase[2]=179.98;phase[3]=-179.98;
 check(179.98,-179.98,0.05);
 // Missing signal clears validity before two cycles and recovers automatically.
 enable_ch[2]=0;#200000;if(valid)$fatal(1,"stale digital valid");
 enable_ch[2]=1;check(179.98,-179.98,0.05);
 // Identical edges exercise simultaneous capture on all four channels.
 for(integer ch=0;ch<4;ch=ch+1)phase[ch]=0;
 check(0,0,0.05);
 if(overflow)$fatal(1,"unexpected capture collision");
 @(negedge signals[2]);#5000;glitch[2]=1;#2000;glitch[2]=0;
 #10000;if(valid)$fatal(1,"short extra pulse did not invalidate period");
 check(0,0,0.05);
 $display("PASS digital: 125MHz/16 periods, phase sign/wrap, both edges, loss/recovery, simultaneous edges, short pulse rejection");$finish;
end
initial begin #40000000;$fatal(1,"digital timeout");end
endmodule
