`timescale 1ns/1ps
module tb_variable_phase;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,sv=0;reg [127:0] samples=0;
    reg [31:0] high_step=206158000,low_step=206158000;
    wire wv,wf,ov1,ov2,rv;wire [671:0] wd;wire [3:0] wb,cv;
    wire [31:0] si,ph,pl;wire [127:0] mag;wire [4:0] wa;wire [41:0] data;
    phase_demod demod(clk,rst_n,sv,high_step,low_step,samples,8'd0,wv,wf,wd,wa,data,wb,si,ov1);
    phase_lsq finish_phase(clk,rst_n,wv,wf,data,wa,wb,16'd100,rv,ph,pl,mag,cv,ov2);
    real a[0:3],p[0:3],dc[0:3],theta,v,h,l,eh,el,amp,ae;
    real max_error=0,max_amplitude_error=0;
    integer mode,n,j,code,checked=0,fd;
    function real wrap(input real x);
        begin while(x>=180)x=x-360;while(x< -180)x=x+360;wrap=x;end
    endfunction
    always @(negedge clk)if(rv && wf)begin
        if(ov1||ov2||cv!==15)$fatal(1,"variable phase invalid mode=%0d cv=%h overrun=%b%b",mode,cv,ov1,ov2);
        h=$itor($signed(ph))*360.0/4294967296.0;l=$itor($signed(pl))*360.0/4294967296.0;
        eh=wrap(h-(p[2]-p[0]));el=wrap(l-(p[3]-p[1]));if(eh<0)eh=-eh;if(el<0)el=-el;
        if(eh>0.08 || el>0.08)$fatal(1,"variable phase error mode=%0d high=%f low=%f",mode,eh,el);
        if(eh>max_error)max_error=eh;if(el>max_error)max_error=el;
        for(integer k=0;k<4;k=k+1)begin
            amp=$itor(mag[k*32+:32])*2.0/(1000.0*1.646760258121);
            ae=amp-a[k];if(ae<0)ae=-ae;
            if(ae>2.0)$fatal(1,"amplitude error mode=%0d ch=%0d expected=%f got=%f",mode,k,a[k],amp);
            if(ae>max_amplitude_error)max_amplitude_error=ae;
        end
        $fwrite(fd,"%0d,%0d,%.9f,%.9f\n",mode,si,h,l);
        checked=checked+1;
    end
    initial begin
        fd=$fopen("test-results/variable-phase.csv","w");
        for(mode=0;mode<16;mode=mode+1)begin
            rst_n=0;sv=0;repeat(8)@(negedge clk);
            case(mode/2)
                0:begin high_step=206158000;low_step=206158000;end
                1:begin high_step=131072000;low_step=81920000;end
                2:begin high_step=17180000;low_step=343598000;end
                3:begin high_step=343598000;low_step=17180000;end
                4:begin high_step=19018000;low_step=65538000;end
                5:begin high_step=314574000;low_step=17344000;end
                6:begin high_step=77778000;low_step=222222000;end
                7:begin high_step=123456000;low_step=234568000;end
            endcase
            for(j=0;j<4;j=j+1)begin p[j]=mode*23.13+j*11.1;dc[j]=(j%2)?-6000:24000;end
            p[2]=p[0]+179.8;p[3]=p[1]-73.56;
            if(mode%2==0)begin a[0]=180;a[1]=23000;a[2]=3500;a[3]=250;end
            else begin a[0]=4200;a[1]=210;a[2]=180;a[3]=17000;end
            rst_n=1;repeat(40)@(negedge clk);
            for(n=0;n<2000;n=n+1)begin
                for(j=0;j<4;j=j+1)begin
                    theta=6.283185307179586*((j%2)?$itor(low_step):$itor(high_step))*n/4294967296.0;
                    v=32768+dc[j]+a[j]*$cos(theta+p[j]*3.141592653589793/180.0);
                    code=$rtoi(v+0.5);samples[j*16+:16]=code;
                end
                sv=1;@(negedge clk);sv=0;repeat(199)@(negedge clk);
            end
            repeat(1500)@(negedge clk);
            $display("PASS variable phase case=%0d steps=%0d/%0d",mode,high_step,low_step);
        end
        $fclose(fd);
        if(checked!=80)$fatal(1,"variable checked windows %0d",checked);
        $display("PASS variable phase: %0d windows, max phase error=%f deg, max amplitude error=%f ADC counts",checked,max_error,max_amplitude_error);$finish;
    end
    initial begin #200000000;$fatal(1,"variable phase timeout");end
endmodule
