`timescale 1ns/1ps
// Mode-0 behavioral ADS8681 model, including one-frame register read pipeline.
module adc_model #(parameter integer CHANNEL=0, SINE=0, STEP=206158000)(input wire rst_n,cs,sclk,sdi,
    input wire stuck_low,output wire sdo);
    reg [31:0] shift_in,shift_out,reply;
    reg [15:0] range_reg,data_reg;
    integer bits_seen=0,conversions=0;
    real theta,phase_deg,amplitude;
    integer sample_code;
    time last_rise,last_fall;
    assign #12 sdo=stuck_low?0:shift_out[31];
    always @(negedge rst_n) begin
        range_reg=0;data_reg=0;reply=0;shift_in=0;shift_out=0;conversions=0;bits_seen=0;
        last_rise=0;last_fall=0;
    end
    always @(negedge cs) if(rst_n) begin
        if(last_rise && $time-last_rise<665)$fatal(1,"conversion time too short");
        shift_out=reply;shift_in=0;bits_seen=0;
    end
    always @(posedge sclk) if(rst_n && !cs)begin
        if(last_fall && $time-last_fall<40)$fatal(1,"SPI low too short");
        shift_in={shift_in[30:0],sdi};bits_seen=bits_seen+1;
    end
    always @(negedge sclk) if(rst_n && !cs)begin
        last_fall=$time;shift_out=shift_out<<1;
    end
    always @(posedge cs) if(rst_n)begin
        if(last_rise && $time-last_rise!=4000)$fatal(1,"sample spacing not 4 us");
        last_rise=$time;
        if(bits_seen!=0 && bits_seen!=32)$fatal(1,"SPI length %0d",bits_seen);
        if(bits_seen==32 && shift_in[31:24]==8'hd0)begin
            case(shift_in[23:16])
                8'h14:range_reg=shift_in[15:0];
                8'h10:data_reg=shift_in[15:0];
                default:$fatal(1,"unexpected register write %h",shift_in);
            endcase
        end
        conversions=conversions+1;
        reply={(16'h8100+16'(CHANNEL*101+conversions)),16'b0};
        if(SINE)begin
            theta=6.283185307179586*STEP*conversions/4294967296.0;
            case(CHANNEL)
                0:begin phase_deg=20;amplitude=1000;end
                1:begin phase_deg=-15;amplitude=2000;end
                2:begin phase_deg=140;amplitude=4000;end
                3:begin phase_deg=-45;amplitude=1500;end
                default:begin phase_deg=0;amplitude=0;end
            endcase
            sample_code=$rtoi(32768+amplitude*$cos(theta+phase_deg*3.141592653589793/180.0)+0.5);
            if(CHANNEL>=4)sample_code=37000; // DC detector, above 0.5 V.
            reply={16'(sample_code),16'b0};
        end
        if(bits_seen==32 && shift_in[31:24]==8'hc8)begin
            case(shift_in[23:16])
                8'h14:reply={range_reg,16'b0};
                8'h10:reply={data_reg,16'b0};
                8'h0c:reply=0;
                default:$fatal(1,"unexpected read");
            endcase
        end
        if(data_reg[2:0]==5)reply=32'hffffffff;
        if(data_reg[2:0]==4)reply=0;
    end
endmodule

module tb_adc;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0;reg [7:0] stuck=0;
    wire reset_out,cs,sclk,sdi,valid,initialized;
    wire [7:0] sdo,ok,err;wire [127:0] samples;
    ads8681_bank #(.RESET_CYCLES(50),.POR_CYCLES(1000)) dut(clk,rst_n,sdo,reset_out,cs,sclk,sdi,valid,samples,ok,err,initialized);
    wire cs_pin,sclk_pin,sdi_pin;
    assign #10 cs_pin=cs;assign #10 sclk_pin=sclk;assign #10 sdi_pin=sdi;
    for(genvar ch=0;ch<8;ch=ch+1)begin: models
        adc_model #(.CHANNEL(ch)) model(reset_out,cs_pin,sclk_pin,sdi_pin,stuck[ch],sdo[ch]);
    end
    integer count=0;reg failed_channel=0;
    always @(negedge clk)if(valid)begin
        count=count+1;
        if(!initialized)$fatal(1,"uninitialized result");
        if(ok!==(failed_channel?8'hdf:8'hff))$fatal(1,"adc_ok=%h",ok);
        if(err!==(failed_channel?8'h20:8'h00))$fatal(1,"sample error=%h",err);
        for(integer ch=0;ch<8;ch=ch+1)
            if(!(failed_channel && ch==5) && samples[ch*16+:16]!==16'(16'h8100+ch*101+13+count-1))
                $fatal(1,"channel %0d data %h count %0d",ch,samples[ch*16+:16],count);
    end
    initial begin
        #1;rst_n=0;repeat(5)@(negedge clk);rst_n=1;
        wait(count==20);@(negedge clk);rst_n=0;count=0;failed_channel=1;stuck=8'h20;
        repeat(5)@(negedge clk);rst_n=1;
        wait(count==20);$display("PASS ADC: 8 synchronous channels, mode 0, readback, stuck-low detection");$finish;
    end
    initial begin #1000000;$fatal(1,"ADC timeout");end
endmodule
