`timescale 1ns/1ps
module tb_link;
localparam D=434;
reg clk=0;always #10 clk=~clk;
reg rst_n=0,rx=1,rv=0,dv=1,du=0;reg [3:0] cv=15;
reg [31:0] index=0;wire tx,hold,config_start;wire [15:0] min_amp;
reg [127:0] samples=128'h90089007900690058004800380028001;
integer ticker=0;
always @(negedge clk)if(rst_n)begin
 rv=0;du=0;
 if(ticker==49999)begin ticker=0;rv=1;du=dv;index=index+250;end
 else ticker=ticker+1;
end
phase_link #(.UART_DIVISOR(D)) dut(.clk(clk),.rst_n(rst_n),.rx(rx),.tx(tx),
 .result_valid(rv),.window_full(1'b1),.channel_valid(cv),.window_bad(4'd0),.adc_ok(8'hff),
 .phase_high(index^32'h12345678),.phase_low(32'h89abcdef),.sample_index(index),
 .magnitudes(128'h44444444333333332222222211111111),
 .samples(samples),.processing_overrun(1'b0),.min_amplitude(min_amp),
 .digital_phases(144'h060000050000040000030000020000010000),
 .digital_periods({32'd10417,32'd10416}),.digital_sequence(16'd42),
 .digital_valid(dv),.digital_update(du),.digital_overflow(1'b0),.snapshot_hold(hold),.config_done(config_start),.config_status(8'd1),.measuring(1'b1),
 .settings(256'd0),.generation(16'd0),.delta_high(32'd103079),.delta_low(32'd103079),
 .config_start(config_start),.config_parameter(),.config_value());
function [15:0] crc(input [15:0] c0,input [7:0] b);
 reg [15:0] c;begin c=c0^b;repeat(8)c=c[0]?(c>>1)^16'ha001:c>>1;crc=c;end
endfunction
reg [7:0] packet[0:127],byte_rx,request_packet[0:11];
reg [15:0] crc_check,last_id;reg [7:0] flags,dflags,kind,status;
integer packets=0,pos=0,k,fd,length=0;
initial begin
 fd=$fopen("test-results/uart-v3-regression.bin","wb");
 forever begin
  @(negedge tx);#(D*20+D*10);
  for(k=0;k<8;k=k+1)begin byte_rx[k]=tx;#(D*20);end
  if(tx!==1)$fatal(1,"TX stop bit");
  packet[pos]=byte_rx;$fwrite(fd,"%c",byte_rx);
  if(pos==3)begin length=byte_rx;if(length!=12 && length!=112)$fatal(1,"length");end
  if(length!=0 && pos==length-1)begin
   crc_check=16'hffff;for(integer n=2;n<length-2;n=n+1)crc_check=crc(crc_check,packet[n]);
   if({packet[length-1],packet[length-2]}!==crc_check)$fatal(1,"response CRC");
   if(packet[0]!=8'ha5 || packet[1]!=8'h5a || packet[2]!=3)$fatal(1,"header");
   kind=packet[4];status=packet[5];flags=packet[6];dflags=packet[7];last_id={packet[9],packet[8]};
   if(length==112)begin
    if(({packet[23],packet[22],packet[21],packet[20]}^32'h12345678)!=={packet[19],packet[18],packet[17],packet[16]})$fatal(1,"mixed analog epochs");
    if({packet[31],packet[30],packet[29],packet[28]}!==32'h01000000)$fatal(1,"digital phase");
    for(integer c=4;c<8;c=c+1)
     if({packet[69+c*2],packet[68+c*2]}!==samples[c*16+:16])$fatal(1,"detector raw telemetry ADC%0d",c+1);
    if({packet[85],packet[84]}!==16'd42)$fatal(1,"digital sequence");
   end
   packets=packets+1;pos=0;length=0;
  end else pos=pos+1;
 end
end
task send_byte(input [7:0] value);
 begin
  @(negedge clk);rx=0;repeat(D)@(negedge clk);
  for(integer bitn=0;bitn<8;bitn=bitn+1)begin rx=value[bitn];repeat(D)@(negedge clk);end
  rx=1;repeat(D)@(negedge clk);
 end
endtask
task send_command(input [7:0] cmd,param,input [15:0] id,value,input corrupt);
 reg [15:0] c;
 begin
  request_packet[0]=8'ha5;request_packet[1]=8'h5a;request_packet[2]=3;request_packet[3]=12;
  request_packet[4]=cmd;request_packet[5]=param;request_packet[6]=id[7:0];request_packet[7]=id[15:8];
  request_packet[8]=value[7:0];request_packet[9]=value[15:8];
  c=16'hffff;for(integer n=2;n<10;n=n+1)c=crc(c,request_packet[n]);
  if(corrupt)c=c^1;
  request_packet[10]=c[7:0];request_packet[11]=c[15:8];
  for(integer n=0;n<12;n=n+1)send_byte(request_packet[n]);
 end
endtask

initial begin
 repeat(8)@(negedge clk);rst_n=1;
 #15000000;if(packets!=0 || tx!==1)$fatal(1,"unsolicited stream");
 send_command(2,0,16'h1234,0,0);wait(packets==1);
 if(last_id!=16'h1234 || flags!=3 || dflags!=3 || status!=0)$fatal(1,"GET result");
 #12000000;if(packets!=1)$fatal(1,"GET repeated");
 send_command(1,7,16'h2345,16'd777,0);wait(packets==2);
 if(kind!=8'h81 || status!=1 || last_id!=16'h2345 || min_amp!=100)$fatal(1,"SET stub changed state or pretended success");
 send_command(2,0,16'h3456,0,1);#12000000;if(packets!=2)$fatal(1,"bad CRC accepted");
 send_command(2,0,16'h3457,0,0);wait(packets==3);if(!flags[6])$fatal(1,"missing CRC diagnostic");
 // One pending request while a previous reply is being transmitted.
 send_command(2,0,16'h4000,0,0);send_command(2,0,16'h4001,0,0);wait(packets==5);
 if(last_id!=16'h4001)$fatal(1,"request ID queue");
 dv=0;cv=0;#110000000;send_command(2,0,16'h5000,0,0);wait(packets==6);
 if(flags[1:0]!=0 || !flags[2] || dflags!=0)$fatal(1,"loss flags");
 dv=1;cv=15;#3000000;send_command(2,0,16'h5001,0,0);wait(packets==7);
 if(flags[1:0]!=3 || flags[2] || dflags!=3)$fatal(1,"automatic recovery");
 send_byte(8'ha5);send_byte(8'h5a);send_byte(3);#31000000;
 send_command(2,0,16'h6000,0,0);wait(packets==8);if(last_id!=16'h6000)$fatal(1,"truncated parser recovery");
 send_command(99,0,16'h6001,0,0);wait(packets==9);if(kind!=8'hff || status!=2)$fatal(1,"unknown command");
 send_command(2,2,16'h6002,0,0);wait(packets==10);if(status!=3)$fatal(1,"invalid GET args");
 // Analog tone flags and comparator phases remain good while each DC detector fails.
 for(integer c=4;c<8;c=c+1)begin
  samples[c*16+:16]=34101; // 0.499875 V: below the requested 0.5 V threshold.
  #1000000;send_command(2,0,16'h7000+c*2,0,0);wait(packets==11+(c-4)*2);
  if(flags[1:0]!=0 || dflags!=0 || flags[2] || packet[11]!=15)$fatal(1,"ADC%0d low level not immediately invalid",c+1);
  samples[c*16+:16]=34102; // 0.500250 V: first representable code >= 0.5 V.
  #1000000;send_command(2,0,16'h7001+c*2,0,0);wait(packets==12+(c-4)*2);
  if(flags[1:0]!=3 || dflags!=3 || flags[2])$fatal(1,"ADC%0d boundary recovery",c+1);
 end
 for(integer c=4;c<8;c=c+1)begin
  samples[c*16+:16]=31435; // -0.499875 V: magnitude below threshold.
  #1000000;send_command(2,0,16'h7800+c*2,0,0);wait(packets==19+(c-4)*2);
  if(flags[1:0]!=0 || dflags!=0 || flags[2])$fatal(1,"ADC%0d negative low level accepted",c+1);
  samples[c*16+:16]=31434; // -0.500250 V: negative boundary accepted.
  #1000000;send_command(2,0,16'h7801+c*2,0,0);wait(packets==20+(c-4)*2);
  if(flags[1:0]!=3 || dflags!=3 || flags[2])$fatal(1,"ADC%0d negative boundary recovery",c+1);
 end
 samples[64+:16]=32768; // Zero detector voltage must fail.
 #110000000;send_command(2,0,16'h8000,0,0);wait(packets==27);
 if(flags[1:0]!=0 || dflags!=0 || !flags[2])$fatal(1,"detector loss timeout");
 samples[64+:16]=34102;#3000000;send_command(2,0,16'h8001,0,0);wait(packets==28);
 if(flags[1:0]!=3 || dflags!=3 || flags[2])$fatal(1,"detector automatic recovery");
 $display("PASS ADC5..8 detector gate: every channel +/-0.499875 V rejects, +/-0.500250 V accepts, mixed polarity, raw telemetry, immediate invalidation, 100 ms loss and automatic recovery");
 $fclose(fd);$display("PASS UART v3: request-only, CRC, coherent RAM snapshots, detector ADCs, reserved legacy ACK, queue, loss/recovery, parser recovery");$finish;
end
initial begin #900000000;$fatal(1,"UART timeout");end
endmodule
