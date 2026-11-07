# Experiments and results

[Русский](experiments.md) | **English**

Use this page to choose what to examine: real signals and distances, the
calibration model or calculation checks. Each type of check has a different
purpose: simulation does not replace an optical experiment, and a successful
experiment at one point does not establish performance over the entire range.

## Latest independent series: 762–5635 mm

**3 November 2026, 10 stationary target positions.** The cal2 coefficients were
fixed before the series and were not fitted to these points.

| Material | Contents |
|---|---|
| [Series report](../measurements/2026-11-03/README.en.md) | Method, selection criteria, results and failed attempts |
| [Excel with formulas](../measurements/2026-11-03/Bench%20measurements.en.xlsx) | Distance meter, phases, amplitudes, analogue and digital distances, errors |
| [Oscilloscope captures](../measurements/2026-11-03/Осциллограммы/README.en.md) | Two screenshots per point with distance captions |
| [Numerical results](../measurements/2026-11-03/measurements.json) | Means, spread and diagnostic fields for independent analysis |
| [Coefficients](../measurements/2026-11-03/calibration.json) | Model, application limits and identifier |
| [Provenance and SHA256](../measurements/2026-11-03/manifest.json) | Checksums of the compact files and references to primary sources |

For the nine points within the cal2 range, RMS discrepancy against Vector60 was
13.36 mm for analogue phase and 13.16 mm for digital phase. The model is not
applied at 5635 mm; `diagnostics=4` was also recorded there. That point is
preserved rather than removed from the history because its result is inconvenient.

## Cal2 calibration

The source series contains 21 points from 638 to 5583 mm. Its
[CSV](../app/desktop_app/cal2.csv) is included. In the selected method, low-frequency
phase determines the integer HF cycle count; a normalised fourth-degree
polynomial of unwrapped HF phase computes the precise distance.

Implementation: [distance.py](../app/desktop_app/distance.py), regression checks:
[test_cal2.py](../app/desktop_app/test_cal2.py). Training points cannot be treated
as independent accuracy evidence; that is why the separate series above was
performed. Calibration does not transfer automatically to another DDS bank
or board specimen.

## Phase at different IFs and amplitudes

Simulation checked different IFs over the operating range of approximately
1–20 kHz, unequal pair frequencies, different amplitudes and DC offsets.
The tests use quantised ADC samples, while a separate NumPy calculation
compares the result with an independent least-squares solution.

| Check | Source and result |
|---|---|
| Analogue path | [tb_variable_phase.sv](../fpga/tb/tb_variable_phase.sv), [log](verification/hdl-variable_phase.txt) |
| Independent least-squares check | [80 windows](verification/phase-reference.json), maximum HDL difference 0.002427578° |
| Digital path | [tb_variable_digital.sv](../fpga/tb/tb_variable_digital.sv), [log](verification/hdl-variable_digital.txt) |
| Atomic DDS changes | [tb_config.sv](../fpga/tb/tb_config.sv), [log](verification/hdl-config.txt) |
| Detector threshold and UART | [tb_link.sv](../fpga/tb/tb_link.sv), [log](verification/hdl-link.txt) |

This verifies the digital implementation for specified signals. It does not
establish the absence of noise, saturation or crosstalk on the real board.

## How we arrived at the current version

Before the latest series, we compared oscilloscope and FPGA phases, investigated
distance-meter response timing, checked AD9959 control, tried FIR, selected
frequencies and amplitudes, and developed the two-phase calculation.

- Distance-meter response time varied; associating a moving target with packet
  arrival time alone proved insufficient. The main distance check therefore
  used stationary target positions.
- The DDS code that was checked contained no periodic command explaining the
  observed jumps. This did not establish their hardware cause.
- FIR produced no noticeable improvement according to the author's observations
  and was removed.
- Selection at a target distance of 1642 mm yielded the current profile with
  different IFs around 4 and 6.75 kHz. This preference applies to the variants
  investigated on that bench, not to all possible frequencies and distances.

This is a brief history of earlier stages. Their complete primary sessions
remain in the author's working archive and are not part of this compact
package. It includes the latest separate series, cal2, current code and
the results of its verification.

## What to investigate next

Repeatability when approaching a point from different directions, temperature
drift, phase-wrap crossings, the appearance of bit2 during movement and
measurements over a long site. For a new experiment, save the initial state
and change one factor so the result can be explained and reproduced.

[Bench](stand.en.md) · [Working with AI](START_WITH_AI.en.md) ·
[Open questions](AI_HANDOFF.en.md)
