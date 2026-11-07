# FPGA: current Quartus project

[Русский](README.md) · **English**

Device: **Cyclone IV E EP4CE6E22C8**. Top level and revision: `DistanceSensorFpga_v0`. Open the [QPF](DistanceSensorFpga_v0.qpf). HDL, ROM, QSF and SDC match the current working bench project. There is no FIR. The archived early project is not required to build this version.

## Build

Verified with **Quartus Prime Lite 25.1std, build 1129**, with Cyclone IV support. Install the tool and device package from the [official distribution](https://www.altera.com/downloads/fpga-development-tools/quartus-prime-lite-edition-design-software-version-25-1-windows). Questa is not required to synthesise this project.

Open the QPF and select Start Compilation, or run from `fpga/`:

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1 -QuartusRoot "D:/altera_lite/25.1std/quartus"
```

Supply your own path. Instead of the parameter, set `QUARTUS_ROOTDIR` or add `quartus_sh` to PATH. The script builds the project and timing reports; it does not open the programmer or write the board. Outputs appear in `output_files/`, with additional reports in `test-results/`. For other environments the standard command from this directory is `quartus_sh --flow compile DistanceSensorFpga_v0` (Linux was not tested here).

## Simulation

Python and [Icarus Verilog](https://steveicarus.github.io/iverilog/) are required, with `iverilog` and `vvp` from the same installation. From `fpga/`:

```powershell
python tools/test_phase_hdl.py
```

If Icarus is not in PATH: `python tools/test_phase_hdl.py --iverilog "D:/iverilog/bin/iverilog.exe"`. Nine suites test ADCs, phases, variable IFs and amplitudes, DDS, the digital phase meter, CDC, UART and top level. Tests compare 88 pin assignments against `pin-lock.json`; PLL models use SIMULATION for these simulations. After variable_phase, run an independent NumPy least-squares check:

```powershell
../app/.venv/Scripts/python.exe tools/check_variable_phase.py
```

Client integration tests read UART bytes produced by these simulations; canned responses do not replace the current RTL.

## Verified images

[releases/2026-11-03](releases/2026-11-03) contains saved SOF and POF images from the working bench. The POF passed Program + Verify on 03.11.2026 at 20:31:09 Samara (UTC+4), using USB-Blaster, Active Serial and EPCS4.

POF SHA256: `7e652373ae74ca5d1734248706c16cae9fdaf9ef25b28a321869271220e0212d`. This is the image used in the [latest series](../measurements/2026-11-03/README.en.md). The new verification build of the publication copy was not written to the board; its results and hash are documented [separately](../docs/build-verification.en.md).

SOF is for temporary JTAG configuration; POF is for EPCS4 through the appropriate Active Serial connector. Do not change QSF based on photograph labels: the verified assignments belong to this particular board.

## Processing

AD9959 SYSCLK is 500 MHz, SYNC_CLK is 125 MHz. Eight ADS8681 devices start synchronously at 250 ksample/s. Analogue channels 1–4 are processed by least squares over 1000 samples, with an update every 250 samples. The digital phase meter measures 16 edges of each polarity at 125 MHz. The supported IF is approximately 1–20 kHz, with an individual IF for each pair. Amplitudes can change without changing the ideal model phase; this property does not eliminate noise, clipping or hardware distortion.

ADC5–8: |U| <0.5 V on any detector clears overall validity. The beam-loss threshold is 100 ms; validity automatically recovers with a good signal. Detailed fields and atomic DDS updates: [UART v3](../docs/protocol-v3.en.md). Distance and velocity are not yet calculated inside the FPGA.
