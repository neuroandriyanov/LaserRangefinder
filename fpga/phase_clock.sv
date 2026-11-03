`timescale 1ns/1ps
module phase_clock(input wire refclk125, reset, output wire clk50, update_clk, locked);
`ifdef SIMULATION
    reg clock_sim=0;
    always #10 clock_sim=~clock_sim;
    assign clk50=clock_sim;
    reg update_sim=0;
    initial begin #2.75;update_sim=1;forever #4 update_sim=~update_sim;end
    assign update_clk=update_sim;
    assign locked=~reset;
`else
    wire [4:0] clocks;
    altpll #(.bandwidth_type("AUTO"), .clk0_divide_by(5), .clk0_multiply_by(2),
        .clk1_divide_by(1), .clk1_multiply_by(1), .clk1_duty_cycle(50), .clk1_phase_shift("-1250"),
        .clk0_duty_cycle(50), .clk0_phase_shift("0"), .compensate_clock("CLK0"),
        .inclk0_input_frequency(8000), .intended_device_family("Cyclone IV E"),
        .operation_mode("NORMAL"), .pll_type("AUTO"), .width_clock(5),
        .port_areset("PORT_USED"), .port_inclk0("PORT_USED"),
        .port_locked("PORT_USED"), .port_clk0("PORT_USED"), .port_clk1("PORT_USED")) pll(
        .inclk({1'b0,refclk125}), .areset(reset), .clk(clocks), .locked(locked),
        .clkena(6'b111111), .extclkena(4'b1111), .pfdena(1'b1), .pllena(1'b1));
    assign clk50=clocks[0];assign update_clk=clocks[1];
`endif
endmodule

module reset_sync(input wire clk, async_reset_n, output wire reset_n);
    (* altera_attribute="-name SYNCHRONIZER_IDENTIFICATION FORCED_IF_ASYNCHRONOUS" *)
    reg [2:0] sync=0;
    always @(posedge clk or negedge async_reset_n)
        if(!async_reset_n) sync<=0; else sync<={sync[1:0],1'b1};
    assign reset_n=sync[2];
endmodule
