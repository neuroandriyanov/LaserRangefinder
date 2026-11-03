// Four 250-sample blocks; two runtime NCOs and LS reference moments.
// 26 sequential products/sample share one 18x18 multiplier; worst case <200 clocks.
module phase_demod(
    input wire clk,rst_n,sample_valid,
    input wire [31:0] nco_step_high,nco_step_low,
    input wire [127:0] samples,
    input wire [7:0] sample_error,
    output reg window_valid,window_full,
    output reg [671:0] window_data,
    input wire [4:0] window_read_address,
    output reg [41:0] window_read_data,
    output reg [3:0] window_bad,
    output reg [31:0] sample_index,
    output reg overrun
);
    reg signed [15:0] sine_rom [0:4095];
    initial $readmemh("sin.hex",sine_rom);
    reg [31:0] nco_high,nco_low;
    reg signed [15:0] sin_read,cos_read;
    reg signed [17:0] cos_high,q_high,cos_low,q_low;
    wire [31:0] selected_phase=(state==12 || state==13)?nco_low:nco_high;
    wire [11:0] cosine_address=selected_phase[31:20]+12'd1024;
    always @(posedge clk) begin
        sin_read<=sine_rom[selected_phase[31:20]];
        cos_read<=sine_rom[cosine_address];
    end
    (* ramstyle="M9K" *) reg signed [41:0] acc_mem [0:31];
    (* ramstyle="M9K" *) reg signed [41:0] total_mem [0:31];
    (* ramstyle="M9K" *) reg signed [41:0] history_mem [0:127];
    reg [4:0] address;
    reg [6:0] history_address;
    reg signed [41:0] acc_read,total_read,history_read;
    reg signed [41:0] acc_write,total_write,history_write,next_total;
    reg acc_we,total_we,history_we;
    (* ramstyle="M9K" *) reg [41:0] window_mem[0:31];
    always @(posedge clk)begin
        window_read_data<=window_mem[window_read_address];
        if(state==9)window_mem[word_index]<=next_total;
    end
    always @(posedge clk) begin
        acc_read<=acc_mem[address]; total_read<=total_mem[address];
        history_read<=history_mem[history_address];
        if(acc_we) acc_mem[address]<=acc_write;
        if(total_we) total_mem[address]<=total_write;
        if(history_we) history_mem[history_address]<=history_write;
    end
    reg signed [17:0] mul_a,mul_b;
    reg signed [35:0] product;
    always @(posedge clk) product<=mul_a*mul_b;
    reg [127:0] held_samples;
    wire [15:0] raw_channel=held_samples[operation[1:0]*16+:16];
    wire signed [15:0] signed_channel={~raw_channel[15],raw_channel[14:0]};
    reg [3:0] state;reg [4:0] operation,word_index;
    reg [5:0] clear_index;
    reg [7:0] sample_count;
    reg last_sample;
    reg [1:0] history_slot;
    reg [2:0] filled;
    reg [3:0] block_bad,bad_history[0:3];
    reg [3:0] new_bad;
    integer j;
    always @* begin
        new_bad=block_bad;
        for(integer k=0;k<4;k=k+1)
            if(k!=history_slot && filled!=0) new_bad=new_bad|bad_history[k];
    end
    always @(posedge clk or negedge rst_n)
        if(!rst_n)begin nco_high<=0;nco_low<=0;end
        else if(state==14)begin nco_high<=nco_high+nco_step_high;nco_low<=nco_low+nco_step_low;end
    wire signed [17:0] op_cos=operation[0]?cos_low:cos_high;
    wire signed [17:0] op_q=operation[0]?q_low:q_high;
    wire signed [17:0] ref_cos=(operation>=21)?cos_low:cos_high;
    wire signed [17:0] ref_q=(operation>=21)?q_low:q_high;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=0;clear_index<=0;address<=0;history_address<=0;
            acc_we<=0;total_we<=0;history_we<=0;
            acc_write<=0;total_write<=0;history_write<=0;next_total<=0;
            cos_high<=0;q_high<=0;cos_low<=0;q_low<=0;mul_a<=0;mul_b<=0;
            held_samples<=0;operation<=0;word_index<=0;sample_count<=0;last_sample<=0;
            history_slot<=0;filled<=0;window_valid<=0;window_full<=0;window_data<=0;
            window_bad<=15;block_bad<=0;sample_index<=0;overrun<=0;
            for(j=0;j<4;j=j+1) bad_history[j]<=0;
        end else begin
            window_valid<=0; acc_we<=0;total_we<=0;history_we<=0;
            if(sample_valid && state!=1 && state!=0) overrun<=1;
            case(state)
                0: begin // Clear only accumulators/totals; history gated by filled.
                    if(clear_index<32) begin
                        address<=clear_index[4:0];acc_write<=0;total_write<=0;
                        acc_we<=1;total_we<=1;clear_index<=clear_index+1'b1;
                    end else state<=1;
                end
                1: if(sample_valid) begin
                    held_samples<=samples;
                    sample_index<=sample_index+1'b1;last_sample<=sample_count==249;
                    if(sample_count==249) sample_count<=0;else sample_count<=sample_count+1'b1;
                    for(j=0;j<4;j=j+1)
                        block_bad[j]<=block_bad[j]|sample_error[j]|
                            (samples[j*16+:16]<=16'd16)|(samples[j*16+:16]>=16'd65519);
                    state<=2;
                end
                2:begin cos_high<=cos_read;q_high<=-$signed({{2{sin_read[15]}},sin_read});state<=12;end
                12:state<=13;
                13:state<=14;
                14:begin cos_low<=cos_read;q_low<=-$signed({{2{sin_read[15]}},sin_read});operation<=0;state<=3;end
                3: begin
                    address<=operation;mul_a<=signed_channel;
                    if(operation<16)case(operation[3:2])
                        0:mul_b<=op_cos;
                        1:mul_b<=op_q;
                        2:mul_b<=signed_channel;
                        3:mul_b<=18'sd32768;
                    endcase
                    else case(operation)
                        16,21:begin mul_a<=ref_cos;mul_b<=ref_cos;end
                        17,22:begin mul_a<=ref_q;mul_b<=ref_q;end
                        18,23:begin mul_a<=ref_cos;mul_b<=ref_q;end
                        19,24:begin mul_a<=ref_cos;mul_b<=18'sd32768;end
                        20,25:begin mul_a<=ref_q;mul_b<=18'sd32768;end
                        default:begin mul_a<=0;mul_b<=0;end
                    endcase
                    state<=4;
                end
                4:state<=5; // synchronous RAM and multiplier latency
                5:begin
                    acc_write<=acc_read+{{6{product[35]}},product};acc_we<=1;
                    if(operation==25) begin
                        if(last_sample) begin word_index<=0;state<=6;end else state<=1;
                    end else begin operation<=operation+1'b1;state<=3;end
                end
                6:begin address<=word_index;history_address<={history_slot,word_index};state<=7;end
                7:state<=8;
                8:begin
                    next_total<=total_read+acc_read-((filled==4)?history_read:42'sd0);
                    history_write<=acc_read;state<=9;
                end
                9:begin
                    total_write<=next_total;total_we<=1;history_we<=1;acc_write<=0;acc_we<=1;
                    if(word_index<16)window_data[word_index*42+:42]<=next_total;
                    if(word_index==25) begin
                        window_full<=filled>=3;
                        if(filled<4) filled<=filled+1'b1;
                        window_bad<=new_bad;bad_history[history_slot]<=block_bad;block_bad<=0;
                        history_slot<=history_slot+1'b1;state<=10;
                    end else begin word_index<=word_index+1'b1;state<=6;end
                end
                10:begin window_valid<=1;state<=1;end
                default:state<=0;
            endcase
        end
    end
endmodule
