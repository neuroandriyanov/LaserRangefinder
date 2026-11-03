// Three-parameter least squares at known frequency, including DC. One shared
// 32x32 multiplier, RAM microprogram, signed Q28 normalized to ADC full scale.
module phase_lsq(input wire clk,rst_n,window_valid,window_full,
    input wire [41:0] window_read_data,output reg [4:0] window_read_address,
    input wire [3:0] window_bad,input wire [15:0] min_amplitude,
    output reg result_valid,output reg [31:0] phase_high,phase_low,
    output reg [127:0] magnitudes,output reg [3:0] channel_valid,output reg overrun);
    localparam LOAD=0,MUL=1,SUB=2,ADD=3,CONST=4,SCALE=5;
    reg [2:0] opcode,state;
    reg [4:0] ra,rb,rd;
    reg [6:0] pc;
    reg [1:0] cycle,channel;
    reg full;reg [3:0] bad,valid_work;reg [15:0] threshold;
    reg [127:0] mag_work;reg [31:0] angles[0:3];
    reg signed [31:0] constant_value;
    (* ramstyle="M9K" *) reg signed [31:0] work[0:31];
    reg signed [31:0] a,b;
    wire signed [31:0] window_scaled=$signed(window_read_data)>>>10;
    wire signed [31:0] mul_a=(opcode==LOAD)?window_scaled:a;
    wire signed [31:0] mul_b=(opcode==LOAD)?32'sd68719477:((opcode==SCALE)?32'sd500:b);
    reg signed [63:0] product;
    reg signed [31:0] write_value;
    always @(posedge clk)begin
        a<=work[ra];b<=work[rb];product<=mul_a*mul_b;
        if(state==1 && cycle==3)work[rd]<=write_value;
    end
    always @*begin
        case(opcode)
            LOAD,MUL:write_value=product>>>28;
            SUB:write_value=a-b;
            ADD:write_value=a+b;
            SCALE:write_value=product>>>13; // ADC peak * N/2, existing UART scale
            default:write_value=constant_value;
        endcase
    end
    // 0..8: E[xc], E[xq], E[x*x], E[x], E[c*c], E[q*q], E[cq], E[c], E[q].
    // q=-sin. 9..25 scratch; 26=2, 27=reciprocal determinant initially 4.
    always @*begin
        opcode=MUL;ra=0;rb=0;rd=9;window_read_address=0;constant_value=0;
        if(pc<9)begin
            opcode=LOAD;rd=pc[4:0];
            if(pc<4)window_read_address={pc[1:0],channel};
            else window_read_address=(channel[0]?5'd21:5'd16)+(pc-4);
        end else case(pc)
            9:begin opcode=CONST;rd=26;constant_value=32'sh20000000;end
            10:begin opcode=CONST;rd=27;constant_value=32'sh40000000;end
            11:begin ra=7;rb=7;rd=9;end
            12:begin opcode=SUB;ra=4;rb=9;rd=4;end
            13:begin ra=8;rb=8;rd=9;end
            14:begin opcode=SUB;ra=5;rb=9;rd=5;end
            15:begin ra=7;rb=8;rd=9;end
            16:begin opcode=SUB;ra=6;rb=9;rd=6;end
            17:begin ra=3;rb=7;rd=9;end
            18:begin opcode=SUB;ra=0;rb=9;rd=0;end
            19:begin ra=3;rb=8;rd=9;end
            20:begin opcode=SUB;ra=1;rb=9;rd=1;end
            21:begin ra=3;rb=3;rd=9;end
            22:begin opcode=SUB;ra=2;rb=9;rd=2;end
            23:begin ra=4;rb=5;rd=10;end
            24:begin ra=6;rb=6;rd=9;end
            25:begin opcode=SUB;ra=10;rb=9;rd=10;end
            // Three reciprocal Newton steps: r <- r*(2-det*r).
            26,29,32:begin ra=10;rb=27;rd=9;end
            27,30,33:begin opcode=SUB;ra=26;rb=9;rd=9;end
            28,31,34:begin ra=27;rb=9;rd=27;end
            35:begin ra=0;rb=5;rd=11;end
            36:begin ra=1;rb=6;rd=9;end
            37:begin opcode=SUB;ra=11;rb=9;rd=11;end
            38:begin ra=11;rb=27;rd=11;end
            39:begin ra=1;rb=4;rd=12;end
            40:begin ra=0;rb=6;rd=9;end
            41:begin opcode=SUB;ra=12;rb=9;rd=12;end
            42:begin ra=12;rb=27;rd=12;end
            43:begin ra=11;rb=11;rd=13;end
            44:begin ra=12;rb=12;rd=9;end
            45:begin opcode=ADD;ra=13;rb=9;rd=13;end
            46:begin opcode=SCALE;ra=11;rd=14;end
            47:begin opcode=SCALE;ra=12;rd=15;end
            48:begin ra=14;rb=15;end
            49:begin ra=13;rb=2;end
            50:begin ra=10;rb=10;end
            default:begin end
        endcase
    end
    reg cordic_start,tone_pure,conditioned;
    reg signed [31:0] iv,qv;
    wire cordic_done,cordic_busy;wire [31:0] angle,magnitude;
    cordic_atan #(.XY_WIDTH(28)) angle_unit(.clk(clk),.rst_n(rst_n),.start(cordic_start),
        .x_in(iv),.y_in(qv),.busy(cordic_busy),.done(cordic_done),.angle(angle),.magnitude(magnitude));
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=0;pc<=0;cycle<=0;channel<=0;full<=0;bad<=15;threshold<=0;
            valid_work<=0;mag_work<=0;iv<=0;qv<=0;tone_pure<=0;conditioned<=0;
            cordic_start<=0;result_valid<=0;phase_high<=0;phase_low<=0;
            magnitudes<=0;channel_valid<=0;overrun<=0;
            angles[0]<=0;angles[1]<=0;angles[2]<=0;angles[3]<=0;
        end else begin
            result_valid<=0;cordic_start<=0;
            if(window_valid && state!=0)overrun<=1;
            case(state)
                0:if(window_valid)begin
                    full<=window_full;bad<=window_bad;threshold<=min_amplitude;
                    channel<=0;pc<=0;cycle<=0;state<=1;
                end
                1:begin
                    cycle<=cycle+1'b1;
                    if(cycle==3)begin if(pc==47)state<=2;pc<=pc+1'b1;end
                end
                2:begin
                    cycle<=cycle+1'b1;
                    if(cycle==3)begin
                        if(pc==48)begin iv<=a;qv<=b;end
                        if(pc==49)tone_pure<=b>0 && a>=b;
                        if(pc==50)begin
                            conditioned<=a>32'sd60000000 && a<32'sd70000000;
                            cordic_start<=1;state<=3;
                        end else pc<=pc+1'b1;
                    end
                end
                3:if(cordic_done)begin
                    angles[channel]<=angle;mag_work[channel*32+:32]<=magnitude;
                    valid_work[channel]<=full && !bad[channel] && tone_pure && conditioned && magnitude>=threshold*32'd824;
                    if(channel==3)state<=4;
                    else begin channel<=channel+1'b1;pc<=0;cycle<=0;state<=1;end
                end
                4:begin
                    phase_high<=angles[2]-angles[0];phase_low<=angles[3]-angles[1];
                    channel_valid<=valid_work;magnitudes<=mag_work;result_valid<=1;state<=0;
                end
                default:state<=0;
            endcase
        end
    end
endmodule

