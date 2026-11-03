// Coherent IF edge phase. 125 MHz is DDS SYSCLK/4; IF step is 4*DDS delta FTW.
// Both polarities, 16 consecutive periods, branch-safe averaging in 24-bit turns.
// Every edge is captured; decimation applies to publication, not input sampling.
module digital_phase_meter #(
    
    parameter integer AVG_LOG2=4
)(input wire clk,rst_n,input wire [3:0] signals,input wire publish_ready,
  input wire [31:0] delta_high,delta_low,
  input wire [17:0] expected_high,expected_low,
  output reg [143:0] phases, // high,low,high-rise,high-fall,low-rise,low-fall
  output reg [63:0] periods,output reg [15:0] sequence_number,
  output reg valid,output reg result_pulse,output reg overflow_seen);
    (* altera_attribute="-name SYNCHRONIZER_IDENTIFICATION FORCED_IF_ASYNCHRONOUS" *)
    reg [3:0] input_meta,input_sync,input_clean;
    reg [3:0] previous;
    wire [3:0] edges=input_clean^previous;
    // Constant zero low bits are omitted (step is 4*DDS FTW delta).
    reg [29:0] nco_high,nco_low;
    reg [17:0] ticks,last_edge[0:3];
    reg [3:0] seen,pending,buffer_level;
    reg [23:0] buffer_phase[0:3];
    reg [17:0] buffer_tick[0:3];
    reg [1:0] scan,chosen,watch_channel,watch_cycle;
    reg [17:0] watch_age,watch_limit;
    reg watch_seen;
    reg [4:0] state;
    wire take=(state==1 && !(&ready) && pending[scan]);
    // A second edge before service is invalid even if service coincides with it.
    wire collision=|(edges & pending);
    wire expired=watch_cycle==2 && watch_seen && watch_age>watch_limit;
    reg fault;
    reg restart;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) restart<=0;
        else restart<=collision|expired|fault;
    // RAM record: {seen, count[3:0], previous_tick[15:0], sum[27:0], anchor[23:0]}.
    (* ramstyle="M9K" *) reg [74:0] history[0:7];
    (* ramstyle="M9K" *) reg [23:0] averages[0:7];
    reg [2:0] address,average_address,clear_index,read_index;
    reg [74:0] hist_read,hist_write;
    reg [23:0] average_read,average_write;
    reg hist_we,average_we;
    always @(posedge clk) begin
        hist_read<=history[address];average_read<=averages[average_address];
        if(hist_we)history[address]<=hist_write;
        if(average_we)averages[average_address]<=average_write;
    end
    reg [23:0] edge_phase,anchor,delta,average_value;
    reg [17:0] edge_tick,period_work;
    reg signed [27:0] sum_work;
    // Division by 2^AVG_LOG2, then intentional modulo-2^24 phase reduction.
    wire [23:0] mean_offset=sum_work[AVG_LOG2+:24];
    reg [3:0] count;
    reg prior_seen;
    reg [7:0] ready;
    reg [23:0] ref_high,ref_low,rise_high,rise_low,fall_high,fall_low;
    reg signed [23:0] gap_high,gap_low;
    reg [17:0] period_high,period_low;
    wire [17:0] expected=chosen[0]?expected_low:expected_high;
    reg [17:0] period_min,period_max;
    integer j;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin
            input_meta<=0;input_sync<=0;input_clean<=0;previous<=0;nco_high<=0;nco_low<=0;ticks<=0;
            pending<=0;buffer_level<=0;seen<=0;watch_channel<=0;watch_cycle<=0;watch_seen<=0;watch_age<=0;watch_limit<=0;
            for(j=0;j<4;j=j+1)begin buffer_phase[j]<=0;buffer_tick[j]<=0;last_edge[j]<=0;end
        end else begin
            input_meta<=signals;input_sync<=input_meta;input_clean<=input_sync;previous<=input_clean;
            nco_high<=nco_high+delta_high[29:0];nco_low<=nco_low+delta_low[29:0];ticks<=ticks+1'b1;
            watch_cycle<=watch_cycle+1'b1;
            if(watch_cycle==0)begin
                watch_age<=ticks-last_edge[watch_channel];watch_seen<=seen[watch_channel];
                watch_limit<=watch_channel[0]?expected_low:expected_high;
            end
            if(watch_cycle==1)watch_limit<=watch_limit+(watch_limit>>1);
            if(watch_cycle==3)watch_channel<=watch_channel+1'b1;
            if(state==0 || restart)begin pending<=0;seen<=0;watch_seen<=0;end
            else begin
                if(take)pending[scan]<=0;
                for(j=0;j<4;j=j+1)if(edges[j])begin
                    buffer_phase[j]<=(j%2)?nco_low[29:6]:nco_high[29:6];buffer_tick[j]<=ticks;
                    buffer_level[j]<=input_clean[j];pending[j]<=1;
                    last_edge[j]<=ticks;seen[j]<=1;
                end
            end
        end
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin
            state<=0;clear_index<=0;period_min<=0;period_max<=0;address<=0;hist_we<=0;average_we<=0;
            hist_write<=0;average_address<=0;average_write<=0;
            scan<=0;chosen<=0;fault<=0;ready<=0;edge_phase<=0;edge_tick<=0;
            anchor<=0;sum_work<=0;count<=0;prior_seen<=0;period_work<=0;delta<=0;average_value<=0;
            read_index<=0;ref_high<=0;ref_low<=0;rise_high<=0;rise_low<=0;fall_high<=0;fall_low<=0;
            gap_high<=0;gap_low<=0;period_high<=0;period_low<=0;
            phases<=0;periods<=0;sequence_number<=0;valid<=0;result_pulse<=0;overflow_seen<=0;
        end else begin
            hist_we<=0;average_we<=0;result_pulse<=0;fault<=0;
            if(restart)begin
                state<=0;clear_index<=0;ready<=0;valid<=0;
                if(collision)overflow_seen<=1;
            end else case(state)
                0:begin
                    address<=clear_index;hist_write<=0;hist_we<=1;
                    if(clear_index==7)begin clear_index<=0;state<=1;end
                    else clear_index<=clear_index+1'b1;
                end
                1:begin
                    if(&ready)begin read_index<=0;state<=10;end
                    else if(pending[scan])begin
                        period_min<=scan[0]?expected_low:expected_high;
                        chosen<=scan;address<={~buffer_level[scan],scan};
                        edge_phase<=buffer_phase[scan];edge_tick<=buffer_tick[scan];state<=2;
                    end
                    scan<=scan+1'b1;
                end
                2:state<=3;
                3:begin
                    period_max<=(period_min>>5)+4;
                    anchor<=hist_read[23:0];sum_work<=hist_read[51:24];
                    period_work<=hist_read[69:52];count<=hist_read[73:70];prior_seen<=hist_read[74];
                    state<=7;
                end
                7:begin period_min<=period_min-period_max;period_max<=period_min+period_max;period_work<=edge_tick-period_work;delta<=edge_phase-anchor;state<=4;end
                4:begin
                    if(prior_seen && (period_work<period_min || period_work>period_max))fault<=1;
                    if(count==0)begin anchor<=edge_phase;sum_work<=0;end
                    else sum_work<=sum_work+{{4{delta[23]}},delta};
                    if(!address[2] && prior_seen)begin
                        if(chosen==0)period_high<=period_work;
                        if(chosen==1)period_low<=period_work;
                    end
                    state<=5;
                end
                5:begin
                    hist_write<={1'b1,((count==((1<<AVG_LOG2)-1))?4'd0:count+4'd1),edge_tick,sum_work,anchor};
                    hist_we<=1;
                    if(count==((1<<AVG_LOG2)-1))begin
                        // Signal phase is negative of the clock phase at its edge.
                        average_value<=-(anchor+mean_offset);state<=6;
                    end else state<=1;
                end
                6:begin
                    average_address<=address;average_write<=average_value;average_we<=1;
                    ready[address]<=1;state<=1;
                end
                10:begin average_address<=read_index;state<=11;end
                11:state<=12;
                12:begin average_value<=average_read;state<=15;end
                15:begin
                    case(read_index)
                        0:ref_high<=average_value;
                        1:ref_low<=average_value;
                        2:rise_high<=average_value-ref_high;
                        3:rise_low<=average_value-ref_low;
                        4:ref_high<=average_value;
                        5:ref_low<=average_value;
                        6:fall_high<=average_value-ref_high;
                        7:fall_low<=average_value-ref_low;
                    endcase
                    if(read_index==7)state<=13;
                    else begin read_index<=read_index+1'b1;state<=10;end
                end
                13:begin gap_high<=fall_high-rise_high;gap_low<=fall_low-rise_low;state<=14;end
                14:if(publish_ready)begin
                    phases<={fall_low,rise_low,fall_high,rise_high,
                        ($signed(rise_low)+($signed(gap_low)>>>1)),($signed(rise_high)+($signed(gap_high)>>>1))};
                    periods<={14'd0,period_low,14'd0,period_high};sequence_number<=sequence_number+1'b1;
                    valid<=1;result_pulse<=1;ready<=0;state<=1;
                end
                default:state<=0;
            endcase
        end
    end
endmodule
