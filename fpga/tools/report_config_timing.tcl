project_open DistanceSensorFpga_v0
create_timing_netlist
read_sdc
update_timing_netlist
report_timing -setup -npaths 12 -detail full_path -file test-results/config-setup-paths.rpt
report_timing -hold -npaths 12 -detail full_path -file test-results/config-hold-paths.rpt
report_timing -setup -to [get_ports ad9959_io_upd] -npaths 4 -detail full_path -file test-results/config-update-setup.rpt
report_timing -hold -to [get_ports ad9959_io_upd] -npaths 4 -detail full_path -file test-results/config-update-hold.rpt
report_clocks -file test-results/config-clocks.rpt
report_ucp -file test-results/config-unconstrained.rpt
project_close
