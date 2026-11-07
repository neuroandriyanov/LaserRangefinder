# Experiments and results

[Русский](experiments.md) · **English**

Use this page to choose between real signals and distances, the calibration model and computation checks. Each type of verification has its own purpose: simulation does not replace an optical experiment, and success at one point does not establish performance across the full range.

## Latest independent series: 762–5635 mm

**3 November 2026, 10 stationary target positions.** Cal2 coefficients were fixed before the series and were not fitted to these points.

| Material | Contents |
|---|---|
| [Series report](../measurements/2026-11-03/README.en.md) | Method, selection conditions, results and failed attempts |
| [Excel with formulas](../measurements/2026-11-03/Стендовые%20измерения.en.xlsx) | Distance meter, phases, amplitudes, analogue and digital distances, errors |
| [Waveforms](../measurements/2026-11-03/Осциллограммы/README.en.md) | Two screenshots per point, labelled with distance |
| [Numerical results](../measurements/2026-11-03/measurements.json) | Means, spread and diagnostic fields for independent analysis |
| [Coefficients](../measurements/2026-11-03/calibration.json) | Model, domain limits and identifier |
| [Provenance and SHA256](../measurements/2026-11-03/manifest.json) | Checksums of compact files and references to primary sources |

For nine points within the cal2 domain, RMS difference from Vector60 was 13.36 mm using analogue phases and 13.16 mm using digital phases. At 5635 mm the model is not applied; `diagnostics=4` was additionally recorded. This point is retained rather than removed from the history because its result is inconvenient.

## Cal2 calibration

The source series contains 21 points from 638 to 5583 mm. Its [CSV](../app/desktop_app/cal2.csv) is included. In the selected method, LF phase determines the integer number of HF cycles; a normalised fourth-degree polynomial calculates precise distance from the unwrapped HF phase.

Implementation: [distance.py](../app/desktop_app/distance.py); regression checks: [test_cal2.py](../app/desktop_app/test_cal2.py). Training points cannot be used as independent accuracy evidence: that is why the separate series above was performed. Calibration does not automatically transfer to a different DDS bank or board.

## Phase at different IFs and amplitudes

Simulation checked different IFs over the working range of approximately 1–20 kHz, unequal pair frequencies, different amplitudes and DC components. Tests use quantised ADC samples; a separate NumPy calculation compares the result with independent least squares.

| Check | Source and result |
|---|---|
| Analogue path | [tb_variable_phase.sv](../fpga/tb/tb_variable_phase.sv), [log](verification/hdl-variable_phase.txt) |
| Independent least-squares check | [80 windows](verification/phase-reference.json), maximum difference from HDL 0.002427578° |
| Digital path | [tb_variable_digital.sv](../fpga/tb/tb_variable_digital.sv), [log](verification/hdl-variable_digital.txt) |
| Atomic DDS change | [tb_config.sv](../fpga/tb/tb_config.sv), [log](verification/hdl-config.txt) |
| Detector threshold and UART | [tb_link.sv](../fpga/tb/tb_link.sv), [log](verification/hdl-link.txt) |

This verifies the digital implementation on specified signals. It does not prove that the real board is free of noise, clipping or signal crosstalk.

## How we reached the current version

Before the latest series we compared oscilloscope and FPGA phases, investigated distance-meter response times, checked AD9959 control, tried FIR, selected frequencies and amplitudes, and developed a two-phase distance calculation.

- Distance-meter response time varied; matching a moving target using packet arrival time alone proved insufficient. The main distance check therefore used stationary intervals.
- The checked DDS code contained no periodic command explaining the observed jumps. This did not establish their hardware cause.
- FIR showed no noticeable improvement according to the author's observations and was removed.
- Selection at a 1642 mm target produced the current profile with different IFs around 4 and 6.75 kHz. This preference applies to the variants examined on that bench, not all possible frequencies and distances.

This is a brief history of previous stages. Their complete primary sessions remain in the author's working archive and are not in this compact package. The latest independent series, cal2, current code and its verification results are available here.

## What to investigate next

Repeatability when approaching a point from different directions, temperature drift, phase-cycle transitions, bit2 during movement and long-distance measurements. For a new experiment, save the initial configuration and change one factor at a time so that the result can be explained and repeated.

[Bench](stand.en.md) · [Working with AI](START_WITH_AI.en.md) · [Open questions](AI_HANDOFF.en.md)
