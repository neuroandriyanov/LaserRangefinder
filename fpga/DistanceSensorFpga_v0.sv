///------------------------------------------------------------------------------------------//
module DistanceSensorFpga_v0
(
    // MCU interface
    input   mcu_p1,
    input   mcu_p2,
    input   mcu_rx,
    output  mcu_tx,

    // ADC interfaces (ADC8-ADC1)
    output  adc_reset,

    // ADC8
    input   adc8_sdo_0,
    output  adc8_sdi,
    output  adc8_sckl,
    output  adc8_convst_cs,
    // ADC7
    input   adc7_sdo_0,
    output  adc7_sdi,
    output  adc7_sclk,
    output  adc7_convst_cs,
    // ADC6
    input   adc6_sdo_0,
    output  adc6_sdi,
    output  adc6_sclk,
    output  adc6_convst_cs,
    // ADC5
    input   adc5_sdo_0,
    output  adc5_sdi,
    output  adc5_sclk,
    output  adc5_convst_cs,
    // ADC4
    input   adc4_sdo_0,
    output  adc4_sdi,
    output  adc4_sclk,
    output  adc4_convst_cs,
    // ADC3
    input   adc3_sdo_0,
    output  adc3_sdi,
    output  adc3_sclk,
    output  adc3_convst_cs,
    // ADC2
    input   adc2_sdo_0,
    output  adc2_sdi,
    output  adc2_sclk,
    output  adc2_convst_cs,
    // ADC1
    input   adc1_sdo_0,
    output  adc1_sdi,
    output  adc1_sclk,
    output  adc1_convst_cs,

    // MAX6316 (Watchdog)
    output  max6316_wdi,
    input   max6316_reset,

    // AD9959 (DDS)
    output  ad9959_clck,
    output  ad9959_cs,
    output  ad9959_io_upd,
    output  ad9959_mres,
    output  ad9959_p0,
    output  ad9959_p1,
    output  ad9959_p2,
    output  ad9959_p3,
    output   ad9959_sdio0,
    output   ad9959_sdio1,
    output   ad9959_sdio2,
    output   ad9959_sdio3,
    input   ad9959_sync_clck_125Mhz,
    input   ad9959_sync_out,

    // SRAM (K6R4008V1D)
    output  K6R4008V1D_a0,
    output  K6R4008V1D_a1,
    output  K6R4008V1D_a2,
    output  K6R4008V1D_a3,
    output  K6R4008V1D_a4,
    output  K6R4008V1D_a5,
    output  K6R4008V1D_a6,
    output  K6R4008V1D_a7,
    output  K6R4008V1D_a8,
    output  K6R4008V1D_a9,
    output  K6R4008V1D_a10,
    output  K6R4008V1D_a11,
    output  K6R4008V1D_a12,
    output  K6R4008V1D_a13,
    output  K6R4008V1D_a14,
    output  K6R4008V1D_a15,
    output  K6R4008V1D_a16,
    output  K6R4008V1D_a17,
    output  K6R4008V1D_a18,
    output  K6R4008V1D_oe,
    output  K6R4008V1D_we,
    output  K6R4008V1D_cs,
    inout   K6R4008V1D_io01,
    inout   K6R4008V1D_io02,
    inout   K6R4008V1D_io03,
    inout   K6R4008V1D_io04,
    inout   K6R4008V1D_io05,
    inout   K6R4008V1D_io06,
    inout   K6R4008V1D_io07,
    inout   K6R4008V1D_io08,

    // Clock_50Mhz
    input   Clock_50Mhz,

    // Miscellaneous signals
    input   sygnal1,
    input   sygnal2,
    input   sygnal3,
    input   sygnal4

);

// Runtime DDS bank; independent board clock retained for bootstrap/watchdog.
wire reset_board_n,measure_clk,update_clk,reset_update_n,pll_locked,reset_measure_n,reset_processing_n;
reset_sync board_reset(.clk(Clock_50Mhz),.async_reset_n(max6316_reset),.reset_n(reset_board_n));
reg [18:0] watchdog_count;reg watchdog;
always @(posedge Clock_50Mhz or negedge reset_board_n)
    if(!reset_board_n)begin watchdog_count<=0;watchdog<=0;end
    else if(watchdog_count==499999)begin watchdog_count<=0;watchdog<=~watchdog;end
    else watchdog_count<=watchdog_count+1'b1;
assign max6316_wdi=watchdog;
wire config_start,config_done,measuring,dds_request,dds_ack,dds_ready;
wire [7:0] config_parameter,config_status;wire [15:0] config_value,generation;
wire [255:0] settings;
wire [31:0] delta_high,delta_low,step_high,step_low;
wire [17:0] expected_high,expected_low;
dds_settings config_bank(.clk(measure_clk),.rst_n(reset_measure_n),.start(config_start),
    .parameter_id(config_parameter),.value(config_value),.dds_ready(dds_ready),.dds_acknowledge(dds_ack),
    .done(config_done),.status(config_status),.active_settings(settings),.request_toggle(dds_request),
    .measuring(measuring),.generation(generation),.delta_high(delta_high),.delta_low(delta_low),
    .step_high(step_high),.step_low(step_low),.period_high(expected_high),.period_low(expected_low));
dds_programmer ad9959_ctrl(.clk(Clock_50Mhz),.rst_n(reset_board_n),.update_clk(update_clk),.update_rst_n(reset_update_n),
    .request_toggle(dds_request),.settings(settings),.acknowledge_toggle(dds_ack),.ready(dds_ready),
    .mreset(ad9959_mres),.cs_n(ad9959_cs),.sclk(ad9959_clck),.sdio(ad9959_sdio0),.io_update(ad9959_io_upd));
assign ad9959_sdio1=0;assign ad9959_sdio2=0;assign ad9959_sdio3=0;
assign ad9959_p0=0;assign ad9959_p1=0;assign ad9959_p2=0;assign ad9959_p3=0;
phase_clock sample_clock(.refclk125(ad9959_sync_clck_125Mhz),
    .reset(!reset_board_n),.clk50(measure_clk),.update_clk(update_clk),.locked(pll_locked));
// Keep ADC/UART alive during settings transactions. Reset only phase histories.
reset_sync measure_reset(.clk(measure_clk),
    .async_reset_n(reset_board_n & pll_locked),
    .reset_n(reset_measure_n));
reset_sync processing_reset(.clk(measure_clk),.async_reset_n(reset_measure_n & measuring),.reset_n(reset_processing_n));
reset_sync update_reset(.clk(update_clk),.async_reset_n(reset_board_n & pll_locked),.reset_n(reset_update_n));
wire reset_digital_n;
reset_sync digital_reset(.clk(ad9959_sync_clck_125Mhz),
    .async_reset_n(reset_measure_n & measuring),
    .reset_n(reset_digital_n));
wire [143:0] digital_phases_native,digital_phases;
wire [63:0] digital_periods_native,digital_periods;
wire [15:0] digital_sequence_native,digital_sequence;
wire digital_valid_native,digital_publish,digital_valid,digital_update;
wire digital_capture_overflow,digital_bridge_overflow,snapshot_hold,digital_publish_ready;
digital_phase_meter digital_meter(.clk(ad9959_sync_clck_125Mhz),.rst_n(reset_digital_n),
    .delta_high(delta_high),.delta_low(delta_low),.expected_high(expected_high),.expected_low(expected_low),
    .signals({sygnal4,sygnal3,sygnal2,sygnal1}),.publish_ready(digital_publish_ready),.phases(digital_phases_native),
    .periods(digital_periods_native),.sequence_number(digital_sequence_native),
    .valid(digital_valid_native),.result_pulse(digital_publish),.overflow_seen(digital_capture_overflow));
digital_phase_bridge digital_bridge(.src_clk(ad9959_sync_clck_125Mhz),.src_rst_n(reset_digital_n),
    .dst_clk(measure_clk),.dst_rst_n(reset_processing_n),.hold(snapshot_hold),
    .publish(digital_publish),.src_valid(digital_valid_native),.src_phases(digital_phases_native),
    .src_periods(digital_periods_native),.src_sequence(digital_sequence_native),
    .phases(digital_phases),.periods(digital_periods),.sequence_number(digital_sequence),
    .valid(digital_valid),.update(digital_update),.overrun(digital_bridge_overflow),.publish_ready(digital_publish_ready));
(* altera_attribute="-name SYNCHRONIZER_IDENTIFICATION FORCED_IF_ASYNCHRONOUS" *)
reg [1:0] digital_diag_sync;
always @(posedge measure_clk or negedge reset_measure_n)
    if(!reset_measure_n)digital_diag_sync<=0;
    else digital_diag_sync<={digital_diag_sync[0],digital_capture_overflow|digital_bridge_overflow};
wire cs,sclk,sdi,sample_valid,initialized;
wire [127:0] samples;
wire [7:0] adc_ok,sample_error;
ads8681_bank adc_bank(.clk(measure_clk),.rst_n(reset_measure_n),
    .sdo({adc8_sdo_0,adc7_sdo_0,adc6_sdo_0,adc5_sdo_0,adc4_sdo_0,adc3_sdo_0,adc2_sdo_0,adc1_sdo_0}),
    .adc_reset_n(adc_reset),.cs(cs),.sclk(sclk),.sdi(sdi),
    .sample_valid(sample_valid),.samples(samples),.adc_ok(adc_ok),
    .sample_error(sample_error),.initialized(initialized));
wire window_valid,window_full,demod_overrun,final_overrun,result_valid;
wire [671:0] window_data;
wire [4:0] window_read_address;wire [41:0] window_read_data;
wire [3:0] window_bad,channel_valid;
wire [31:0] sample_index,phase_high,phase_low;
wire [127:0] magnitudes;
wire [15:0] min_amplitude;
phase_demod demod(.clk(measure_clk),.rst_n(reset_processing_n),.sample_valid(sample_valid),
    .nco_step_high(step_high),.nco_step_low(step_low),.samples(samples),.sample_error(sample_error),.window_valid(window_valid),
    .window_full(window_full),.window_read_address(window_read_address),.window_read_data(window_read_data),.window_bad(window_bad),
    .sample_index(sample_index),.overrun(demod_overrun));
phase_lsq finalize(.clk(measure_clk),.rst_n(reset_processing_n),.window_valid(window_valid),
    .window_full(window_full),.window_read_address(window_read_address),.window_read_data(window_read_data),.window_bad(window_bad),
    .min_amplitude(min_amplitude),.result_valid(result_valid),.phase_high(phase_high),
    .phase_low(phase_low),.magnitudes(magnitudes),.channel_valid(channel_valid),.overrun(final_overrun));
// Timestamp and raw values belong to the same completed block as the I/Q window.
reg [31:0] result_sample_index;
reg [127:0] result_samples;
always @(posedge measure_clk or negedge reset_measure_n)
    if(!reset_measure_n) begin result_sample_index<=0;result_samples<=0;end
    else if(window_valid) begin result_sample_index<=sample_index;result_samples<=samples;end
phase_link link(.clk(measure_clk),.rst_n(reset_measure_n),.rx(mcu_rx),.tx(mcu_tx),
    .result_valid(result_valid),.window_full(window_full),.channel_valid(channel_valid),
    .window_bad(window_bad),.adc_ok(adc_ok),.phase_high(phase_high),.phase_low(phase_low),
    .sample_index(result_sample_index),.magnitudes(magnitudes),.samples(result_samples),
    .processing_overrun(demod_overrun|final_overrun),.min_amplitude(min_amplitude),
    .digital_phases(digital_phases),.digital_periods(digital_periods),.digital_sequence(digital_sequence),
    .digital_valid(digital_valid),.digital_update(digital_update),.digital_overflow(digital_diag_sync[1]),
    .snapshot_hold(snapshot_hold),.config_done(config_done),.config_status(config_status),.measuring(measuring),
    .settings(settings),.generation(generation),.delta_high(delta_high),.delta_low(delta_low),
    .config_start(config_start),.config_parameter(config_parameter),.config_value(config_value));
assign adc1_sdi=sdi; assign adc1_sclk=sclk; assign adc1_convst_cs=cs;
assign adc2_sdi=sdi; assign adc2_sclk=sclk; assign adc2_convst_cs=cs;
assign adc3_sdi=sdi; assign adc3_sclk=sclk; assign adc3_convst_cs=cs;
assign adc4_sdi=sdi; assign adc4_sclk=sclk; assign adc4_convst_cs=cs;
assign adc5_sdi=sdi; assign adc5_sclk=sclk; assign adc5_convst_cs=cs;
assign adc6_sdi=sdi; assign adc6_sclk=sclk; assign adc6_convst_cs=cs;
assign adc7_sdi=sdi; assign adc7_sclk=sclk; assign adc7_convst_cs=cs;
assign adc8_sdi=sdi; assign adc8_sckl=sclk; assign adc8_convst_cs=cs;
assign K6R4008V1D_a0=1'b0;
assign K6R4008V1D_a1=1'b0;
assign K6R4008V1D_a2=1'b0;
assign K6R4008V1D_a3=1'b0;
assign K6R4008V1D_a4=1'b0;
assign K6R4008V1D_a5=1'b0;
assign K6R4008V1D_a6=1'b0;
assign K6R4008V1D_a7=1'b0;
assign K6R4008V1D_a8=1'b0;
assign K6R4008V1D_a9=1'b0;
assign K6R4008V1D_a10=1'b0;
assign K6R4008V1D_a11=1'b0;
assign K6R4008V1D_a12=1'b0;
assign K6R4008V1D_a13=1'b0;
assign K6R4008V1D_a14=1'b0;
assign K6R4008V1D_a15=1'b0;
assign K6R4008V1D_a16=1'b0;
assign K6R4008V1D_a17=1'b0;
assign K6R4008V1D_a18=1'b0;
assign K6R4008V1D_cs=1'b1;
assign K6R4008V1D_oe=1'b1;
assign K6R4008V1D_we=1'b1;
assign K6R4008V1D_io01=1'bz;
assign K6R4008V1D_io02=1'bz;
assign K6R4008V1D_io03=1'bz;
assign K6R4008V1D_io04=1'bz;
assign K6R4008V1D_io05=1'bz;
assign K6R4008V1D_io06=1'bz;
assign K6R4008V1D_io07=1'bz;
assign K6R4008V1D_io08=1'bz;
endmodule
