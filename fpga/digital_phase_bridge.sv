// Bundled-data handshake: source holds a complete epoch until destination ACK.
// Independent live validity path clears stale good values after a meter fault.
module digital_phase_bridge(input wire src_clk,src_rst_n,dst_clk,dst_rst_n,hold,
    input wire publish,src_valid,input wire [143:0] src_phases,
    input wire [63:0] src_periods,input wire [15:0] src_sequence,
    output reg [143:0] phases,output reg [63:0] periods,
    output reg [15:0] sequence_number,output wire valid,output reg update,
    output reg overrun,output wire publish_ready);
    // The meter's output registers are the mailbox; publish_ready prevents overwrite.
    wire [223:0] mailbox={src_sequence,src_periods,src_phases};
    reg request_toggle,ack_toggle;
    (* altera_attribute="-name SYNCHRONIZER_IDENTIFICATION FORCED_IF_ASYNCHRONOUS" *)
    reg [1:0] ack_sync,request_sync,valid_sync;
    assign publish_ready=(ack_sync[1]==request_toggle);
    always @(posedge src_clk or negedge src_rst_n)begin
        if(!src_rst_n)begin request_toggle<=0;ack_sync<=0;overrun<=0;end
        else begin
            ack_sync<={ack_sync[0],ack_toggle};
            if(publish)begin
                if(ack_sync[1]==request_toggle)begin
                    request_toggle<=~request_toggle;
                end else overrun<=1;
            end
        end
    end
    reg received;
    assign valid=received & valid_sync[1];
    always @(posedge dst_clk or negedge dst_rst_n)begin
        if(!dst_rst_n)begin
            request_sync<=0;valid_sync<=0;ack_toggle<=0;received<=0;
            phases<=0;periods<=0;sequence_number<=0;update<=0;
        end else begin
            request_sync<={request_sync[0],request_toggle};valid_sync<={valid_sync[0],src_valid};update<=0;
            if(!valid_sync[1])received<=0;
            if(request_sync[1]!=ack_toggle && !hold)begin
                {sequence_number,periods,phases}<=mailbox;
                ack_toggle<=request_sync[1];received<=valid_sync[1];update<=1;
            end
        end
    end
endmodule
