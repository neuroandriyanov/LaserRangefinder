`timescale 1ns/1ps
module tb_phase #(parameter FILTER=0);
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,sv=0;reg [127:0] samples=0;reg [7:0] errors=0;
    wire wv,wf,ov1,ov2,rv;wire [671:0] wd;wire [3:0] wb,cv;
    wire [31:0] si,ph,pl;wire [127:0] mag;
    wire [4:0] wa;wire [41:0] wdata;
    wire fs,fov;wire [63:0] fd;wire [3:0] fe;
    generate if(FILTER)begin
        adc_phase_filter prefilter(clk,rst_n,sv,samples[63:0],errors[3:0],fs,fd,fe,fov);
    end else begin assign fs=sv;assign fd=samples[63:0];assign fe=errors[3:0];assign fov=0;end endgenerate
    phase_demod demod(clk,rst_n,fs,32'd206158000,32'd206158000,{samples[127:64],fd},{errors[7:4],fe},wv,wf,wd,wa,wdata,wb,si,ov1);
    phase_lsq finish_phase(clk,rst_n,wv,wf,wdata,wa,wb,16'd100,rv,ph,pl,mag,cv,ov2);
    real a[0:3],p[0:3],dc[0:3];real theta,v,h,l,eh,el,max_error=0;
    integer n,j,code,results=0,scenario=0,checked=0;
    function real wrap(input real x);
        begin while(x>=180.0)x=x-360;while(x< -180.0)x=x+360;wrap=x;end
    endfunction
    always @(posedge clk) if(rv) begin
        results=results+1;
        h=$itor($signed(ph))*360.0/4294967296.0;
        l=$itor($signed(pl))*360.0/4294967296.0;
        if(si>=1000) begin
            if(ov1||ov2||fov) $fatal(1,"processing overrun");
            if(scenario<=2 || scenario==6 || scenario==7 || scenario==8) begin
                if(cv!==15) $fatal(1,"valid mask %h scenario %0d sample %0d",cv,scenario,si);
                eh=wrap(h-(p[2]-p[0]+((scenario==7)?0.004*(si-500.5+8*FILTER):0.0)));el=wrap(l-(p[3]-p[1]));
                if(eh<0)eh=-eh;if(el<0)el=-el;
                // FIR output adds one rounding to 16 bits. At the lowest tested
                // amplitude (180 ADC counts), allow 0.05 deg; raw path stays 0.03.
                if(eh>((FILTER)?0.05:0.03)||el>((FILTER)?0.05:0.03)) $fatal(1,"phase error high=%f low=%f actual %f %f",eh,el,h,l);
                if(eh>max_error)max_error=eh;if(el>max_error)max_error=el;
            end else if(scenario==3 && cv[2]!==0) $fatal(1,"beam absent accepted");
            else if(scenario==4 && cv[3]!==0) $fatal(1,"off-frequency accepted");
            else if(scenario==5 && cv[0]!==0) $fatal(1,"clipping accepted");
            checked=checked+1;
        end
    end
    task run_case(input integer mode);
        begin
            scenario=mode;rst_n=0;sv=0;repeat(8)@(negedge clk);rst_n=1;
            repeat(40)@(negedge clk);
            a[0]=15000;a[1]=7000;a[2]=3500;a[3]=1800;
            p[0]=43.7;p[1]=-72.4;p[2]=-126.2;p[3]=106.9;
            dc[0]=2000;dc[1]=-800;dc[2]=500;dc[3]=0;
            if(mode==1)begin a[0]=180;a[1]=600;a[2]=13000;a[3]=250;end
            if(mode==2)begin p[2]=p[0]+180.2;p[3]=p[1]-180.1;end
            if(mode==7)p[2]=p[0]+178.0;
            if(mode==3)a[2]=0;
            if(mode==5)begin a[0]=32000;dc[0]=8000;end
            for(n=0;n<2500+16*FILTER;n=n+1)begin
                theta=6.283185307179586*206158000.0*n/4294967296.0;
                for(j=0;j<4;j=j+1)begin
                    v=32768+dc[j]+a[j]*$cos(theta+p[j]*3.141592653589793/180.0);
                    if(mode==7 && j==2)v=32768+dc[j]+a[j]*$cos(theta+(p[j]+0.004*n)*3.141592653589793/180.0);
                    if(mode==4 && j==3)v=32768+1800*$cos(theta*1.5);
                    if(mode==6)v=v+3*$sin(n*1.234+j);
                    if(mode==8)v=v+0.25*a[j]*$cos(2*theta+j)+0.20*a[j]*$sin(3*theta-j);
                    code=$rtoi(v+0.5);if(code<0)code=0;if(code>65535)code=65535;
                    samples[j*16+:16]=code;
                end
                sv=1;@(negedge clk);sv=0;repeat(199)@(negedge clk);
            end
            repeat(1500)@(negedge clk);
            $display("PASS scenario %0d",mode);
        end
    endtask
    initial begin
        for(integer mode=0;mode<=8;mode=mode+1)run_case(mode);
        if(checked!=63)$fatal(1,"checked windows %0d",checked);
        $display("PASS phase FILTER=%0d: 63 full windows, max error %.6f degrees",FILTER,max_error);$finish;
    end
    initial begin #100000000;$fatal(1,"timeout");end
endmodule
