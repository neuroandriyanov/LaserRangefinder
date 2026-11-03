`timescale 1ns/1ps
module tb_config;
localparam D=16;
reg clk=0,board=0,uc=0,rst=0,rx=1,rv=0;
always #10 clk=~clk;initial begin #3;forever #10 board=~board;end
initial begin #3;uc=1;forever #4 uc=~uc;end
wire tx,start,done,measuring,req,ack,ready,mreset,cs,sclk,sdio,upd,hold;
wire [7:0] param,status;wire [15:0] value,gen,threshold;
wire [255:0] settings;wire [31:0] dh,dl,sh,sl;wire [17:0] ph,pl;
dds_settings cfg(clk,rst,start,param,value,ready,ack,done,status,settings,req,measuring,gen,dh,dl,sh,sl,ph,pl);
dds_programmer dds(board,rst,uc,rst,req,settings,ack,ready,mreset,cs,sclk,sdio,upd);
integer ticker=0;reg [31:0] index=0;
always @(negedge clk)begin
 rv=0;if(rst)begin if(ticker==49999)begin ticker=0;rv=1;index=index+250;end else ticker=ticker+1;end
end
phase_link #(.UART_DIVISOR(D)) link(.clk(clk),.rst_n(rst),.rx(rx),.tx(tx),.result_valid(rv),
 .window_full(1'b1),.channel_valid(4'hf),.window_bad(4'd0),.adc_ok(8'hff),
 .phase_high(index),.phase_low(index),.sample_index(index),.magnitudes(128'd0),.samples({4{32'h90009000}}),
 .processing_overrun(1'b0),.digital_phases(144'd0),.digital_periods({32'd125000,32'd6250}),
 .digital_sequence(16'd12),.digital_valid(1'b1),.digital_update(rv),.digital_overflow(1'b0),
 .config_done(done),.measuring(measuring),.config_status(status),.settings(settings),.generation(gen),
 .delta_high(dh),.delta_low(dl),.config_start(start),.config_parameter(param),.config_value(value),
 .min_amplitude(threshold),.snapshot_hold(hold));
function [15:0] crc(input [15:0] old,input [7:0] b);
 reg [15:0] c;begin c=old^b;repeat(8)c=c[0]?(c>>1)^16'ha001:c>>1;crc=c;end
endfunction
reg [7:0] packet[0:127],reqbytes[0:11],br;
reg [15:0] check_crc;integer received=0,pos=0,len=0,k,fd;
initial begin
 fd=$fopen("test-results/uart-v3.bin","wb");
 forever begin
  @(negedge tx);#(D*30);
  for(k=0;k<8;k=k+1)begin br[k]=tx;#(D*20);end
  if(tx!==1)$fatal(1,"UART stop");packet[pos]=br;$fwrite(fd,"%c",br);
  if(pos==3)len=br;
  if(len!=0 && pos==len-1)begin
   check_crc=16'hffff;for(integer n=2;n<len-2;n=n+1)check_crc=crc(check_crc,packet[n]);
   if({packet[len-1],packet[len-2]}!=check_crc || packet[2]!=3)$fatal(1,"response CRC/version");
   received=received+1;pos=0;len=0;
  end else pos=pos+1;
 end
end
task byte_tx(input [7:0] v);
 begin @(negedge clk);rx=0;repeat(D)@(negedge clk);
 for(integer b=0;b<8;b=b+1)begin rx=v[b];repeat(D)@(negedge clk);end
 rx=1;repeat(D)@(negedge clk);end
endtask
integer id=0;
task command(input [7:0] cmd,p,input [15:0] v,input corrupt,input [7:0] expect_status);
 reg [15:0] c;integer before_count;
 begin
  before_count=received;id=id+1;
  reqbytes[0]=8'ha5;reqbytes[1]=8'h5a;reqbytes[2]=3;reqbytes[3]=12;
  reqbytes[4]=cmd;reqbytes[5]=p;reqbytes[6]=id;reqbytes[7]=id>>8;reqbytes[8]=v;reqbytes[9]=v>>8;
  c=16'hffff;for(integer n=2;n<10;n=n+1)c=crc(c,reqbytes[n]);if(corrupt)c=c^1;
  reqbytes[10]=c;reqbytes[11]=c>>8;
  for(integer n=0;n<12;n=n+1)byte_tx(reqbytes[n]);
  if(corrupt)begin #100000;if(received!=before_count)$fatal(1,"bad CRC executed");end
  else begin
   wait(received==before_count+1);
   if(packet[5]!=expect_status || {packet[9],packet[8]}!=id)$fatal(1,"ACK id=%0d status=%0d expected=%0d",id,packet[5],expect_status);
   repeat(4*D)@(negedge clk);
  end
 end
endtask
reg [255:0] candidate,initial_bank;
task stage;
 begin command(1,8'hf0,16'hb001,0,4);
 for(integer w=0;w<16;w=w+1)command(1,16+w,candidate[w*16+:16],0,4);end
endtask
integer updates=0,frames=0,bits=0;reg [39:0] spi_word=0;
reg [7:0] instruction,selection=0;reg [255:0] spi_bank=0;reg [31:0] spi_data;
realtime last_up;
always @(negedge cs)begin bits=0;spi_word=0;end
always @(posedge sclk)if(!cs)begin spi_word={spi_word[38:0],sdio};bits=bits+1;end
always @(posedge cs)if(rst && bits!=0)begin
 instruction=spi_word>>(bits-8);spi_data=spi_word;
 if(instruction==0)selection=spi_data;
 if(instruction==3 && (spi_data & 24'hffffff)!=24'h321)$fatal(1,"DDS mode/phase clear changed");
 for(integer c=0;c<4;c=c+1)if(selection==(16<<c))case(instruction)
  4:spi_bank[c*64+:32]=spi_data;
  5:spi_bank[c*64+32+:16]=spi_data;
  6:spi_bank[c*64+48+:16]=spi_data & 1023;
 endcase
 frames=frames+1;
end
always @(posedge upd)begin
 if(uc!==1 || ($realtime-3)%8!=0)$fatal(1,"IO_UPDATE not synchronous");
 if(frames%20!=0 || spi_bank!==settings)$fatal(1,"partial DDS update frames=%0d got=%h expected=%h",frames,spi_bank,settings);
 updates=updates+1;last_up=$realtime;
end
always @(negedge upd)if(updates!=0 && $realtime-last_up!=32)$fatal(1,"IO_UPDATE width");
initial begin
 #101;rst=1;wait(measuring);initial_bank=settings;
 if(settings!=={16'd450,16'd0,32'd635830272,16'd1000,16'd0,32'd12879416,
     16'd1000,16'd0,32'd635888254,16'd200,16'd0,32'd12845056})$fatal(1,"startup bank");
 if(updates!=1 || dh!=57982 || dl!=34360 || sh!=115964000 || sl!=68720000 || ph!=18519 || pl!=31250)$fatal(1,"startup defaults/NCO/period");
 command(2,0,0,0,0);if(packet[3]!=112 || {packet[95],packet[94],packet[93],packet[92]}!=125000)$fatal(1,"32-bit period telemetry");
 command(1,8'hf1,16'ha55a,0,6);
 command(1,8'hf0,16'hb001,0,4);command(1,16,123,1,4);
 command(1,8'hf1,16'ha55a,0,6);if(settings!==initial_bank)$fatal(1,"incomplete modified DDS");
 candidate={16'd321,16'd100,32'h25e60000,16'd170,16'd200,32'h00c4a000,
            16'd450,16'd300,32'h25e70000,16'd210,16'd400,32'h00c40000};
 stage();if(updates!=1 || settings!==initial_bank)$fatal(1,"staged applied early");
 command(1,8'hf1,16'ha55a,0,0);
 if(!measuring || updates!=2 || gen!=1 || dh!=65536 || dl!=40960 || sh!=131072000 || sl!=81920000 || ph!=16384 || pl!=26214)$fatal(1,"commit/NCO/period mismatch %d %d",ph,pl);
 command(2,1,0,0,0);if(packet[3]!=48 || packet[6]!=128 || packet[10]!=1)$fatal(1,"configuration readback header");
 for(integer b=0;b<32;b=b+1)if(packet[12+b]!==candidate[b*8+:8])$fatal(1,"readback word %d",b);
 initial_bank=settings;
 candidate[48+:16]=1024;stage();command(1,8'hf1,16'ha55a,0,3);
 if(settings!==initial_bank || updates!=2)$fatal(1,"invalid amplitude applied");
 candidate=initial_bank;candidate[32+:16]=16384;stage();command(1,8'hf1,16'ha55a,0,3);
 candidate=initial_bank;candidate[128+:32]=candidate[0+:32]+8589;stage();command(1,8'hf1,16'ha55a,0,3);
 candidate=initial_bank;candidate[64+:32]=candidate[192+:32]+171800;stage();command(1,8'hf1,16'ha55a,0,3);
 candidate=initial_bank;candidate[128+:32]=candidate[0+:32]+8590;candidate[64+:32]=candidate[192+:32]+171799;
 stage();command(1,8'hf1,16'ha55a,0,0);
 if(pl!=124999 || ph!=6250 || updates!=3 || gen!=2)$fatal(1,"boundary period %0d %0d",ph,pl);
 command(1,8'hf2,0,0,0);#5000000;
 if(updates!=3 || mreset)$fatal(1,"unsolicited DDS activity");
 $fclose(fd);$display("PASS configuration/UART/SPI: defaults, CRC, incomplete/staged/atomic commits, readback, limits 1..20kHz, phase/amp ranges, synchronous updates, no periodic writes");$finish;
end
initial begin #50000000;$fatal(1,"configuration timeout state=%d link=%d id=%d",cfg.state,link.state,id);end
endmodule
