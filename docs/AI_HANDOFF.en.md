# Context for the next AI assistant

[Русский](AI_HANDOFF.md) · **English**

Status as of **3 November 2026, Samara (UTC+4)**. This file describes the standalone publication directory. It requires no access to the author's computer. Reading and checking order: [AGENTS.md](../AGENTS.en.md).

Canonical repository: [neuroandriyanov/LaserRangefinder](https://github.com/neuroandriyanov/LaserRangefinder). The first publication was prepared on 03.11.2026 at the author's request through a separate branch and pull request into main. Check repository history for the exact commit and merge status. Software version and measurement results were unchanged during transfer.

## What is here

Desktop application 0.5.1, FPGA UART v3, schematics, photographs and the latest measurement series. Background: optics and receiver assembly from a faulty LE-200 PROFIBUS; PIN photodiodes replaced with BPX65 and laser diode with QL67D7SA. This is information supplied by the author when preparing the description. The main board is a custom design. Details: [story](project-story.en.md), [bench](stand.en.md).

## Current implementation

| Subsystem | Status |
|---|---|
| FPGA | EP4CE6E22C8, DistanceSensorFpga_v0 project in fpga/ |
| DDS | AD9959, SYSCLK 500 MHz, common IO_UPDATE, 4 channels |
| ADCs | 8 ADS8681 devices, synchronous 250 ksample/s |
| Analogue phase | Least squares/CORDIC, 1000-sample window, update every 250; no FIR |
| Digital phase | 125 MHz, 16 edges of each polarity |
| Validity | In addition to phases, voltage magnitude U ≥0.5 V is checked on every ADC5–8 |
| UART | v3, 115200 8N1, request 12 bytes, measurements 112, DDS bank 48 |
| Distance | Calculated on the PC using cal2; no distance/velocity calculation in FPGA |
| Distance meter | Vector60 through a dedicated WinUSB Bluetooth adapter; optional for FPGA/demo |

Startup bank: FTW `[12845056, 635888254, 12879416, 635830272]`, ASF `[200, 1000, 1000, 450]`, all POW 0. Exact copy: [default.json](../app/profiles/dds/default.json). LF IF is 4000.030458 Hz; HF IF is 6749.993190 Hz. DDS CH0/CH2 are LF; CH1/CH3 are HF. Input phase pairs are 3−1 HF and 4−2 LF. COM settings remain active until reset; PC settings are saved separately.

## What was checked

Latest series: 762, 1091, 1480, 1958, 2398, 2876, 3425, 4198, 4814, 5635 mm. Two screenshots per point, CH1+CH3 and CH2+CH4. Cal2 was fixed before the series; domain 638–5583 mm, ID `6c959d57db56d0397e0618d8026c43604e38874606a59c39262eb9daf9059de6`. Nine points are inside it: RMS difference from the distance meter 13.36/13.16 mm, max |error| 22.96/22.81 mm (analogue/digital). The 5635 mm point is outside the model. [Report and data](../measurements/2026-11-03/README.en.md).

Working-series POF: `7e652373ae74ca5d1734248706c16cae9fdaf9ef25b28a321869271220e0212d`. Program+Verify on the author's board: 03.11.2026 20:31:09 Samara. A verification build of the publication copy produced the same POF, without writing the board again. Quartus Lite 25.1std: 6162/6272 LE, 23/30 M9K, 5/15 DSP18, 1/2 PLL; 66 checks, min slack +0.137 ns, unconstrained 0. 63 application tests, 22 protocol tests and 9 HDL suites passed; clean installation and demo after transfer were verified on Windows/Python 3.14. [Evidence](build-verification.en.md). These checks apply to the saved version.

## Open questions

- The 5635 mm point showed `diagnostics=4`, a latched digital overflow. Its source is digital_phase_meter.overflow_seen and/or bridge.overrun; which source and why remain unknown. Current valid can become 1 after recovery.
- The cause of rare hardware phase jumps is unproven. DDS checking found no periodic updates with an unchanged setpoint. FIR was removed after no noticeable improvement was observed by the author.
- DDS selection was performed at one point, 1642 mm. The profile is not a universal calibration.
- Dynamics, temperature, long distances of 100–200 m and further distance/velocity calculations need investigation. Room-scale experiments do not replace these tests.
- IP68 was a goal in enclosure selection; there is no assembled-device test report.

Last confirmed state of the author's bench after the series: previous DDS bank, generation=0, diagnostics=4, COM/BLE released, oscilloscope RUN, all four channels, 50 μs/div. Instruments were not polled while preparing this documentation. The state of another bench or a new session must be established again.

## Where to continue

For study, the [guide](START_WITH_AI.en.md), demonstration and saved data suffice. For development, choose the user's task and corresponding tests. For bit2, first establish a reproducible scenario and locate the source; do not reset or hide the flag for attractive statistics. For a new bench, first confirm connections, actual bank and suitability of its calibration.

Record new information here and completed stages in [PROJECT_LOG.md](PROJECT_LOG.en.md). Retain primary data and old manifests. Licences were selected at the author's request: MIT and CERN-OHL-P-2.0; scope is in [NOTICE.md](../NOTICE.en.md).

## 7 November 2026: bilingual documentation

Russian remains the source language; English documents and asset captions are maintained alongside it. See [TRANSLATION.md](TRANSLATION.en.md) and `i18n/manifest.json` for source versions and translation coverage. Localisation does not change software, HDL, calibration, primary measurements or original photographs. The desktop application still has a Russian interface. Existing build and hardware-test results refer to their original version and dates.
