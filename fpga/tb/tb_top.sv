`timescale 1ns/1ps
// Full top: selected DDS defaults, startup/reset, ADC SPI, I/Q, CORDIC, link.
// PLL simulation provides ideal 50 MHz; actual PLL timing is checked by Quartus.
module tb_top;
reg clk50=0,clk125=0,reset_n=0;
always #10 clk50=~clk50;always #4 clk125=~clk125;
wire adc_reset,tx,io_update,watchdog;
reg [3:0] comparator_signals=0;
localparam real HIGH_PERIOD=2.0*4294967296.0/57982,LOW_PERIOD=2.0*4294967296.0/34360;
initial begin #2000;forever begin comparator_signals[0]=1;#(HIGH_PERIOD/2);comparator_signals[0]=0;#(HIGH_PERIOD/2);end end
initial begin #2000;forever begin comparator_signals[1]=1;#(LOW_PERIOD/2);comparator_signals[1]=0;#(LOW_PERIOD/2);end end
initial begin #(2000+HIGH_PERIOD*2/3);forever begin comparator_signals[2]=1;#(HIGH_PERIOD/2);comparator_signals[2]=0;#(HIGH_PERIOD/2);end end
initial begin #(2000+LOW_PERIOD/12);forever begin comparator_signals[3]=1;#(LOW_PERIOD/2);comparator_signals[3]=0;#(LOW_PERIOD/2);end end
wire [7:0] cs,sclk,sdi,sdo,cs_pin,sclk_pin,sdi_pin;
assign #10 cs_pin=cs;assign #10 sclk_pin=sclk;assign #10 sdi_pin=sdi;
DistanceSensorFpga_v0 dut(.Clock_50Mhz(clk50),.ad9959_sync_clck_125Mhz(clk125),
.max6316_reset(reset_n),.max6316_wdi(watchdog),.mcu_rx(1'b1),.mcu_tx(tx),
.mcu_p1(1'b0),.mcu_p2(1'b0),.sygnal1(comparator_signals[0]),.sygnal2(comparator_signals[1]),.sygnal3(comparator_signals[2]),.sygnal4(comparator_signals[3]),
.ad9959_sync_out(1'b0),.ad9959_io_upd(io_update),.adc_reset(adc_reset),
.adc1_convst_cs(cs[0]),.adc1_sclk(sclk[0]),.adc1_sdi(sdi[0]),.adc1_sdo_0(sdo[0]),
.adc2_convst_cs(cs[1]),.adc2_sclk(sclk[1]),.adc2_sdi(sdi[1]),.adc2_sdo_0(sdo[1]),
.adc3_convst_cs(cs[2]),.adc3_sclk(sclk[2]),.adc3_sdi(sdi[2]),.adc3_sdo_0(sdo[2]),
.adc4_convst_cs(cs[3]),.adc4_sclk(sclk[3]),.adc4_sdi(sdi[3]),.adc4_sdo_0(sdo[3]),
.adc5_convst_cs(cs[4]),.adc5_sclk(sclk[4]),.adc5_sdi(sdi[4]),.adc5_sdo_0(sdo[4]),
.adc6_convst_cs(cs[5]),.adc6_sclk(sclk[5]),.adc6_sdi(sdi[5]),.adc6_sdo_0(sdo[5]),
.adc7_convst_cs(cs[6]),.adc7_sclk(sclk[6]),.adc7_sdi(sdi[6]),.adc7_sdo_0(sdo[6]),
.adc8_convst_cs(cs[7]),.adc8_sckl(sclk[7]),.adc8_sdi(sdi[7]),.adc8_sdo_0(sdo[7]));
for(genvar ch=0;ch<8;ch=ch+1)begin: models
 adc_model #(.CHANNEL(ch),.SINE(1),.STEP(ch%2==0?115964000:68720000)) adc(adc_reset,cs_pin[ch],sclk_pin[ch],sdi_pin[ch],1'b0,sdo[ch]);
end
integer good=0,updates=0;
integer raw_epoch=0,filtered_epoch=0;
real high,low,dhigh,dlow;
always @(negedge clk50)begin
 if(dut.sample_valid)raw_epoch=raw_epoch+1;
 if(dut.sample_valid)filtered_epoch=raw_epoch;
 if(dut.window_valid && filtered_epoch!=raw_epoch)$fatal(1,"Raw telemetry advanced before filtered window completed");
 if(dut.demod_overrun || dut.final_overrun)$fatal(1,"Top processing deadline missed");
end
always @(posedge io_update)if(reset_n)updates=updates+1;
always @(negedge clk50)if(dut.result_valid && dut.window_full)begin
 high=$itor($signed(dut.phase_high))*360.0/4294967296.0;
 low=$itor($signed(dut.phase_low))*360.0/4294967296.0;
 if(dut.channel_valid!==15 || dut.adc_ok!==255)$fatal(1,"top invalid %h %h",dut.channel_valid,dut.adc_ok);
 if(high<119.97 || high>120.03 || low< -30.03 || low> -29.97)$fatal(1,"top phases %f %f",high,low);
 if(cs!=={8{cs[0]}} || sclk!=={8{sclk[0]}})$fatal(1,"ADC channels not synchronous");
 dhigh=$itor($signed(dut.digital_phases[0+:24]))*360.0/16777216.0;
 dlow=$itor($signed(dut.digital_phases[24+:24]))*360.0/16777216.0;
 if(!dut.digital_valid || dhigh<119.94 || dhigh>120.06 || dlow< -30.06 || dlow> -29.94)$fatal(1,"top digital %f %f valid %d",dhigh,dlow,dut.digital_valid);
 if(!dut.link.both_valid)$fatal(1,"top detector validity");
 if(tx!==1)$fatal(1,"top UART sends without request");
 good=good+1;
 if(good==8)begin
  if(updates==0)$fatal(1,"DDS never updated");
  $display("PASS top: DDS/8 ADC, analog %f %f, digital %f %f, CDC and request-only UART idle",high,low,dhigh,dlow);$finish;
 end
end
initial begin repeat(10)@(negedge clk50);reset_n=1;end
initial begin #100000000;$fatal(1,"top timeout, DDS updates %0d",updates);end
endmodule
