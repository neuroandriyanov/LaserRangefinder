create_clock -name board50 -period 20.000 [get_ports Clock_50Mhz]
create_clock -name dds125 -period 8.000 [get_ports ad9959_sync_clck_125Mhz]
derive_pll_clocks
derive_clock_uncertainty
set_clock_groups -asynchronous -group [get_clocks board50] -group [get_clocks {dds125 *sample_clock*}]
# Asynchronous reset and UART input terminate at explicit synchronizers.
set_false_path -from [get_ports max6316_reset]
set_false_path -from [get_ports mcu_rx] -to [get_registers {*|phy|rx_sync[0]}]
# Comparator pins are asynchronous; only the FIRST synchronizer stage is exempt.
set_false_path -from [get_ports {sygnal1 sygnal2 sygnal3 sygnal4}] -to [get_registers {*digital_meter|input_meta*}]
# Toggle/valid CDC controls tolerate metastability in the first stage. Even
# though 125/50 clocks are related, the handshake does not depend on their
# 4 ns closest-edge relationship. Keep stage0->stage1 normally timed.
set_false_path -from [get_registers {*digital_bridge|ack_toggle}] -to [get_registers {*digital_bridge|ack_sync[0]}]
set_false_path -from [get_registers {*digital_bridge|request_toggle}] -to [get_registers {*digital_bridge|request_sync[0]}]
set_false_path -from [get_registers {*digital_meter|valid}] -to [get_registers {*digital_bridge|valid_sync[0]}]
set_false_path -from [get_registers {*digital_meter|overflow_seen *digital_bridge|overrun}] -to [get_registers {*digital_diag_sync[0]}]
# Mailbox is held until ACK. Two destination synchronizers precede its capture
# (>=40 ns at 50 MHz). Bound the data routing explicitly, not a blanket CDC cut.
set_max_delay 16.000 -from [get_registers {*digital_meter|phases* *digital_meter|periods* *digital_meter|sequence_number*}] -to [get_registers {*digital_bridge|phases* *digital_bridge|periods* *digital_bridge|sequence_number*}]
set_min_delay 0.000 -from [get_registers {*digital_meter|phases* *digital_meter|periods* *digital_meter|sequence_number*}] -to [get_registers {*digital_bridge|phases* *digital_bridge|periods* *digital_bridge|sequence_number*}]
# SPI SDO is launched at falling SCLK; capture is two 50-MHz cycles later.
# ADS8681 tD_CKDO <=12 ns at DVDD=3.3 V, plus 3 ns provisional PCB budget and <=10 ns FPGA SCLK launch delay.
set_input_delay -clock [get_clocks {*sample_clock*clk?0?}] -max 25.000 [get_ports {adc*_sdo_0}]
set_input_delay -clock [get_clocks {*sample_clock*clk?0?}] -min 0.000 [get_ports {adc*_sdo_0}]
set_multicycle_path -setup 2 -from [get_ports {adc*_sdo_0}] -to [get_registers {*adc_bank*rx*}]
set_multicycle_path -hold 1 -from [get_ports {adc*_sdo_0}] -to [get_registers {*adc_bank*rx*}]
# Pin propagation bounds; serial protocol intervals checked separately in RTL tests.
set_max_delay 10.000 -from [get_registers {*adc_bank*}] -to [get_ports {adc*_sdi adc*_sclk adc8_sckl adc*_convst_cs adc_reset}]
set_max_delay 10.000 -from [get_registers {*ad9959_ctrl*}] -to [get_ports {ad9959_clck ad9959_cs ad9959_mres ad9959_sdio* ad9959_p*}]
set_max_delay 10.000 -to [get_ports {mcu_tx max6316_wdi}]

# No receiver requires a minimum absolute output propagation delay.
set_min_delay 0.000 -to [get_ports {adc*_sdi adc*_sclk adc8_sckl adc*_convst_cs adc_reset ad9959_clck ad9959_cs ad9959_mres ad9959_sdio* ad9959_p* mcu_tx max6316_wdi}]

# Runtime settings are held before request and until ACK. Only first control
# synchronizers are cut. Settings to 125 MHz meters are static while reset.
set_false_path -to [get_registers {*ad9959_ctrl|update_sync[0]}]
set_false_path -to [get_registers {*config_bank|ready_sync[0] *config_bank|ack_sync[0]}]
set_max_delay 16.000 -from [get_registers {*config_bank|delta_* *config_bank|period_*}] -to [get_registers {*digital_meter*}]
set_min_delay 0.000 -from [get_registers {*config_bank|delta_* *config_bank|period_*}] -to [get_registers {*digital_meter*}]
# AD9959 Rev C tSU=4.8 ns; provisional 0.5 ns total clock+update PCB flight.
# PLL update clock leads SYNC_CLK by 1.25 ns; the pin arrives AFTER that edge.
# Capture at the following edge (9.25 ns relationship), with hold checked at the
# intervening edge. Do NOT add the usual multicycle -hold 1 here.
set_output_delay -clock dds125 -max 5.300 [get_ports ad9959_io_upd]
set_output_delay -clock dds125 -min 0.000 [get_ports ad9959_io_upd]

set_multicycle_path -setup 2 -to [get_ports ad9959_io_upd]
# Reset synchronizer async inputs intentionally assert asynchronously; their
# outputs release on local clocks. No downstream recovery/removal is excluded.
set_false_path -from [get_registers {*config_bank*}] -to [get_registers {*digital_reset|sync* *processing_reset|sync*}]

# These settings change only while the entire phase meter is held reset; they
# settle >2 ms before reset release. Keep 16 ns routing bounds, but the nominal
# related-clock hold edge is not a possible functional data transition.
set_false_path -hold -from [get_registers {*config_bank|delta_* *config_bank|period_*}] -to [get_registers {*digital_meter*}]
