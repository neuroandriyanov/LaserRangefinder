# LaserRangefinder — exploring distance through the phase of light

[Русский](README.md) · **English**

Repository: [neuroandriyanov/LaserRangefinder](https://github.com/neuroandriyanov/LaserRangefinder).

**A dual-frequency FPGA laser rangefinder and a bench on which we learn to measure and calibrate it.**

This repository brings together custom electronics, Verilog code, a desktop application, schematics, photographs and real measurements. The project develops through collaboration between a person and AI: from restoring the optics and capturing the first waveforms to phase-meter algorithms, frequency selection and checking calibrated distance measurements.

![Rangefinder board and receiver assembly in the open enclosure](hardware/photos/rangefinder-05.jpg)

*Custom board in its enclosure. The restored optical assembly is in the centre. [More photographs](hardware/photos/README.en.md).*

## Where to start

| What you want to do | Where to go |
|---|---|
| Learn how the project began | [Restoration and development story](docs/project-story.en.md) |
| Understand the measurement | [Architecture and data flow](docs/architecture.en.md) |
| Inspect the bench and connections | [Bench equipment](docs/stand.en.md) |
| See the results | [Experiments](docs/experiments.en.md) · [Latest series](measurements/2026-11-03/README.en.md) |
| Download a spreadsheet with formulas | [Excel: distances and errors](measurements/2026-11-03/Стендовые%20измерения.en.xlsx) |
| Examine the signals | [20 waveforms labelled with distances](measurements/2026-11-03/Осциллограммы/README.en.md) |
| Run the application | [Application and installation](app/README.en.md) |
| Build the firmware | [Quartus and HDL tests](fpga/README.en.md) |
| Inspect the hardware | [Schematics and BOM](hardware/README.en.md) · [Photos](hardware/photos/README.en.md) |
| Continue with your own AI assistant | [Getting started](docs/START_WITH_AI.en.md) · [AGENTS.md](AGENTS.en.md) |

## How it began

Investigating the phase method required an instrument in which signals could be observed and processing changed. The starting point was the optics of a faulty **LE-200 PROFIBUS**: a lens, collimator and receiver assembly with SA612 mixers. The damaged original electronics could not be restored. Failed PIN photodiodes were replaced with **BPX65** devices and the laser diode with a **QL67D7SA**, for the red spectral range around 670 nm.

After restoring the optics, a new board was designed. Convenient oscilloscope connection points make it possible to observe the analogue signal path and immediately compare it with FPGA calculations. The enclosure was selected with IP68 protection and future equipment trials in mind; the protection rating of the assembled device has not yet been confirmed by a separate test.

[Optical assembly story and photographs →](docs/project-story.en.md)

## How distance is measured

The laser is modulated at two frequencies simultaneously. One photodiode receives reference light directly from the emitter through an optical fibre; the other receives the reflection from the target. Mixers shift the signals into the several-kilohertz range while preserving phase-difference information. Four sine waves and four digital signals from comparators reach the FPGA.

The high frequency provides sensitivity to small changes in distance. The low frequency helps select the correct high-frequency phase cycle. We compare two measurement methods: processing ADC samples and measuring digital-edge arrival times.

| Part | Implementation |
|---|---|
| FPGA | Cyclone IV E, EP4CE6E22C8 |
| Signal generation | AD9959, four configurable outputs |
| Digitisation | Eight ADS8681 devices, synchronous sampling |
| Analogue phase | Sinusoidal least squares and CORDIC, without FIR |
| Digital phase | 125 MHz counter, edge accumulation |
| PC connection | USB–TTL, UART v3 with CRC and a common DDS update |
| Reference distance | Vector60 laser distance meter |
| Signal observation | Four-channel RIGOL DS1104Z |

Details are in the [signal-path description](docs/architecture.en.md) and [communication protocol](docs/protocol-v3.en.md).

## How we worked with AI

Sergey built and restored the hardware, connected instruments, moved the target and checked device behaviour. AI helped analyse the schematic, write Verilog and the desktop application, prepare simulations, run builds, read instruments through available interfaces and compare results.

Experiments proceeded step by step: record a stationary target, request movement, confirm that it has stopped, then record again. The distance-meter readings, FPGA phases and amplitudes, and later oscilloscope screenshots were saved together. This grounded discussion of the algorithm in concrete data.

Not every change helped. For example, the tested FIR showed no noticeable improvement according to the author's observations and was removed. Frequency and amplitude selection produced a working profile for subsequent measurements, but we do not consider it a universal optimum. The history of decisions and unresolved questions is retained for continued work.

**To start with your own AI assistant, open the project root and have it read [AGENTS.md](AGENTS.en.md).** A ready-to-use first task and workflow are in the [guide](docs/START_WITH_AI.en.md). A useful contribution can begin with one graph, a hypothesis check or a documentation improvement.

## Measurements and current status

The latest series covers **10 stationary target positions, from 762 to 5635 mm**. Each point has two screenshots: reference and reflected HF signals, followed by the equivalent LF pair. The Excel workbook contains distance-meter readings, FPGA data, calculated distance and error relative to the distance meter.

![HF pair at a distance of 1480 mm](measurements/2026-11-03/Осциллограммы/point-03_01480.0mm_ch1-ch3.en.svg)

*Reference and reflected signals after the mixers. The caption is outside the native screenshot; measurement traces have not been redrawn.*

For nine points within the cal2 range, the RMS difference from the distance meter was **13.36 mm for ADC phases and 13.16 mm for digital phases**. Coefficients were fixed before this series. This is an averaged result for this particular bench, not a rated accuracy specification. The 5635 mm point is outside the calibration range and has a digital-overflow diagnostic flag, as noted in the report.

Distance is currently calculated by the desktop application. Moving distance and velocity calculations into the FPGA, investigating rare glitches, dynamics and temperature effects are the next tasks. A full **100–200 m** test needs a long space, such as a corridor about 200 m long. Current tests are limited to a small room.

[Report and spreadsheet →](measurements/2026-11-03/README.en.md) · [Experiment map →](docs/experiments.en.md) · [What remains unverified →](docs/known-limitations.en.md)

## Try it without hardware

After installing Python with Tcl/Tk, run from the project root:

~~~powershell
powershell -ExecutionPolicy Bypass -File app/install.ps1
app/Run.cmd --demo
~~~

Tested on Windows and Python 3.14 x64. Demo mode does not access instruments. To use a board, select your own COM port; DDS settings are sent using a button. [Detailed installation and distance-meter connection](app/README.en.md).

## Materials and further work

The app/, fpga/, hardware/ and measurements/ folders can be studied independently. The package includes build instructions, tests, a saved working image and [portability verification results](docs/build-verification.en.md). Photographs and measurements include provenance and checksums. A [link catalogue](docs/website-links.en.md) is provided for publishing materials on the website.

The purpose of this publication is to share both the code and the investigation: how the bench is arranged, what we tried, what worked and which questions remain. If you can measure over a greater distance, compare processing methods or suggest an improvement, these materials provide a verified starting point.

## Other projects by the author

- [FerroDSP](https://github.com/neuroandriyanov/FerroDsp) — an experimental ADAU1452 metal detector with custom electronics and SigmaStudio algorithms.
- [PropValve-RE06MT](https://github.com/neuroandriyanov/PropValve-RE06MT) — remote proportional-valve control electronics based on ADAU1701.

The shared approach is custom hardware, observable signals and development that can be continued with AI using the saved materials.

## Licences

Author-written code, documentation, photographs and measurement materials are provided under **MIT**. Original electrical schematics and the BOM are under **CERN-OHL-P-2.0**. Scope and exceptions for manufacturer materials are described in [NOTICE.md](NOTICE.en.md). Full texts: [MIT](LICENSE), [CERN-OHL-P-2.0](LICENSES/CERN-OHL-P-2.0.txt).

Hardware author: Sergey Andriyanov ([NeuroAndriyanov](https://github.com/neuroandriyanov)). Code, measurement procedures and documentation were developed in collaboration with AI.
