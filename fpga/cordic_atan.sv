// Vectoring, four-quadrant. angle: signed turns * 2^32; +/-180 deg wraps naturally.
// Input must fit +/-2^29. Magnitude output includes CORDIC gain 1.646760258.
module cordic_atan #(parameter XY_WIDTH=34)(input wire clk,rst_n,start,
    input wire signed [31:0] x_in,y_in,
    output reg busy,done,
    output reg signed [31:0] angle,
    output reg [31:0] magnitude);
    reg signed [XY_WIDTH-1:0] x,y;
    reg signed [31:0] z;
    reg [4:0] iteration;
    reg signed [31:0] table_atan [0:31];
    initial $readmemh("atan.hex",table_atan);
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin busy<=0;done<=0;angle<=0;magnitude<=0;x<=0;y<=0;z<=0;iteration<=0;end
        else begin
            done<=0;
            if(start && !busy) begin
                busy<=1;iteration<=0;
                if(x_in<0) begin
                    x<=-$signed({{2{x_in[31]}},x_in});
                    y<=-$signed({{2{y_in[31]}},y_in});
                    z<=32'h80000000;
                end else begin x<=x_in;y<=y_in;z<=0;end
            end else if(busy) begin
                if(iteration==24) begin
                    angle<=z; magnitude<=x; busy<=0; done<=1;
                end else begin
                    if(y>=0) begin
                        x<=x+(y>>>iteration); y<=y-(x>>>iteration); z<=z+table_atan[iteration];
                    end else begin
                        x<=x-(y>>>iteration); y<=y+(x>>>iteration); z<=z-table_atan[iteration];
                    end
                    iteration<=iteration+1'b1;
                end
            end
        end
    end
endmodule
