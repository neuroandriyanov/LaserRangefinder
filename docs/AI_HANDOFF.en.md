# Context for the next AI assistant

[Русский](AI_HANDOFF.md) | **English**

Technical state as of **3 November 2026, Samara (UTC+4)**. This file describes
the standalone publication folder. It does not require access to the author's
workstation. Reading order and checks: [AGENTS.en.md](../AGENTS.en.md).

Canonical repository: [neuroandriyanov/LaserRangefinder](https://github.com/neuroandriyanov/LaserRangefinder).
The first publication was prepared on 3 November 2026 at the author's request,
using a separate branch and a pull request into main. Check the repository history
for the exact commit and merge result. The software version and measurement results
were unchanged by the transfer.

## Bilingual documentation — 7 November 2026

The hardware and software state below remains the state of 3 November.
Complete English documents, oscilloscope captions and a separate English
measurement workbook were added. Numerical sources, firmware and historical
manifests are preserved; no instruments were queried. Russian material can
be added first and translated later following the [workflow](TRANSLATIONS.en.md).
Checks and the reason for updating the root manifest.json are recorded
in the [project log](PROJECT_LOG.en.md).

## Contents

Desktop application 0.5.1, FPGA UART v3, schematics, photos and the latest measurement
series. Background: optics and receiver assembly from a faulty LE-200 PROFIBUS;
PIN photodiodes replaced with BPX65 and the laser diode with QL67D7SA. These are
the author's statements recorded when preparing the description. The main board
is a custom design. Details: [story](project-story.en.md), [bench](stand.en.md).

## Current implementation

| Block | State |
|---|---|
| FPGA | EP4CE6E22C8, DistanceSensorFpga_v0 project in fpga/ |
| DDS | AD9959, SYSCLK 500 MHz, common IO_UPDATE, 4 channels |
| ADC | 8 ADS8681 devices, synchronous 250 ksample/s |
| Analogue phase | Least-squares/CORDIC, 1000-sample window, updated every 250 samples; no FIR |
| Digital phase | 125 MHz, 16 edges of each polarity |
| Validity | In addition to phase, checks voltage magnitude ≥0.5 V on every ADC5–8 input |
| UART | v3, 115200 8N1, request 12 bytes, measurement frame 112, DDS bank 48 |
| Distance | Calculated by the PC using cal2; no distance or speed calculation in the FPGA |
| Distance meter | Vector60 through a separate WinUSB Bluetooth adapter; optional for FPGA/demo use |

Startup bank: FTW `[12845056, 635888254, 12879416, 635830272]`,
ASF `[200, 1000, 1000, 450]`, all POW values 0. Exact copy:
[default.json](../app/profiles/dds/default.json). LF IF 4000.030458 Hz,
HF IF 6749.993190 Hz. LF uses DDS CH0/CH2, HF uses CH1/CH3; input phase
pairs are 3−1 HF and 4−2 LF. Settings sent over COM last until reset;
they are saved separately on the PC.

## What has been verified

Latest series: 762, 1091, 1480, 1958, 2398, 2876, 3425, 4198, 4814 and 5635 mm.
Two captures per point, CH1+CH3 and CH2+CH4. Cal2 was fixed before the series,
range 638–5583 mm, ID `6c959d57db56d0397e0618d8026c43604e38874606a59c39262eb9daf9059de6`.
Nine points fall inside it: RMS discrepancy against the distance meter
13.36/13.16 mm, max |error| 22.96/22.81 mm (analogue/digital). 5635 mm is
outside the model. [Report and data](../measurements/2026-11-03/README.en.md).

Working-series POF: `7e652373ae74ca5d1734248706c16cae9fdaf9ef25b28a321869271220e0212d`.
Program+Verify on the author's board: 3 November 2026, 20:31:09 Samara.
A verification build of the publication copy produced the same POF, without
programming the board again. Quartus Lite 25.1std: 6162/6272 LE, 23/30 M9K,
5/15 DSP18, 1/2 PLL; 66 checks, min slack +0.137 ns, unconstrained 0.
63 application tests, 22 protocol tests and 9 HDL test suites passed;
a clean installation and relocated demo were checked on Windows/Python 3.14.
[Evidence](build-verification.en.md). These checks refer to the saved version.

## Open questions

- At 5635 mm, `diagnostics=4` appeared: latched digital overflow. Its source is
  digital_phase_meter.overflow_seen and/or bridge.overrun; which one and why
  are not yet established. After recovery, the current valid flag can be 1.
- The cause of rare hardware phase jumps is unproven. The DDS check found no
  periodic updates with unchanged settings. FIR was removed after no noticeable
  improvement according to the author's observations.
- DDS selection was performed at one point, 1642 mm. The profile is not a
  universal calibration.
- Motion and temperature effects, long distances of 100–200 m and further
  distance/speed calculations need investigation. Room-scale tests do not
  replace those investigations.
- IP68 was an enclosure-selection target; there is no test report for the
  assembled device.

Last confirmed state of the author's bench after the series: previous DDS bank,
generation=0, diagnostics=4, COM/BLE released, oscilloscope RUN, all four channels,
50 µs/div. No instruments were polled while preparing this documentation.
For another bench or another day, establish the state afresh.

## Where to continue

The [guide](START_WITH_AI.en.md), demo and saved data are enough for exploration.
For development, select the user's task and then the corresponding tests. For bit2,
first obtain a reproducible case and localise its source; do not reset or conceal
the flag to improve the statistics. For a new bench, first confirm connections,
the actual bank and the suitability of its calibration.

Record new information here and completed stages in [PROJECT_LOG.en.md](PROJECT_LOG.en.md).
Preserve the original data and old manifests. The author has already selected
MIT and CERN-OHL-P-2.0; scope: [NOTICE.en.md](../NOTICE.en.md).
