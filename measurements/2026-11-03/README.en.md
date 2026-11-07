# Bench series of 3 November 2026

[Русский](README.md) · **English**

10 stationary positions, **762–5635 mm**, 20 oscilloscope screenshots. The series was recorded at 20:53–21:13 Samara (UTC+4). The owner moved the target when instructed and confirmed it had stopped. The series ended upon reaching the room's limit.

[Excel with formulas](Стендовые%20измерения.en.xlsx) contains Vector60 distance, analogue and digital FPGA phases, calculated distances and errors, amplitudes, detector voltages, frequencies, phase standard deviations, diagnostics and screenshot names. The “Расчёт” (Calculation) sheet shows cal2 coefficients and intermediate calculations. [All waveforms](Осциллограммы/README.en.md) are labelled with distance.

## Results

Error = calculated distance − distance-meter reading, mm. Cal2 was fixed **before** the series and was not fitted to these points. Distance was calculated on the PC/in Excel from FPGA phases, not inside the FPGA.

| Point | Distance meter, mm | ADC, mm | Digital, mm | ADC error, mm | Digital error, mm | Screenshots |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 762 | 763.8 | 763.1 | 1.8 | 1.1 | [HF](Осциллограммы/point-01_00762.0mm_ch1-ch3.en.svg) · [LF](Осциллограммы/point-01_00762.0mm_ch2-ch4.en.svg) |
| 2 | 1091 | 1106.2 | 1105.5 | 15.2 | 14.5 | [HF](Осциллограммы/point-02_01091.0mm_ch1-ch3.en.svg) · [LF](Осциллограммы/point-02_01091.0mm_ch2-ch4.en.svg) |
| 3 | 1480 | 1492.2 | 1491.8 | 12.2 | 11.8 | [HF](Осциллограммы/point-03_01480.0mm_ch1-ch3.en.svg) · [LF](Осциллограммы/point-03_01480.0mm_ch2-ch4.en.svg) |
| 4 | 1958 | 1967.4 | 1967.2 | 9.4 | 9.2 | [HF](Осциллограммы/point-04_01958.0mm_ch1-ch3.en.svg) · [LF](Осциллограммы/point-04_01958.0mm_ch2-ch4.en.svg) |
| 5 | 2398 | 2421.0 | 2420.8 | 23.0 | 22.8 | [HF](Осциллограммы/point-05_02398.0mm_ch1-ch3.en.svg) · [LF](Осциллограммы/point-05_02398.0mm_ch2-ch4.en.svg) |
| 6 | 2876 | 2891.1 | 2891.2 | 15.1 | 15.2 | [HF](Осциллограммы/point-06_02876.0mm_ch1-ch3.en.svg) · [LF](Осциллограммы/point-06_02876.0mm_ch2-ch4.en.svg) |
| 7 | 3425 | 3416.5 | 3416.5 | -8.5 | -8.5 | [HF](Осциллограммы/point-07_03425.0mm_ch1-ch3.en.svg) · [LF](Осциллограммы/point-07_03425.0mm_ch2-ch4.en.svg) |
| 8 | 4198 | 4181.3 | 4181.5 | -16.7 | -16.5 | [HF](Осциллограммы/point-08_04198.0mm_ch1-ch3.en.svg) · [LF](Осциллограммы/point-08_04198.0mm_ch2-ch4.en.svg) |
| 9 | 4814 | 4808.3 | 4808.8 | -5.7 | -5.2 | [HF](Осциллограммы/point-09_04814.0mm_ch1-ch3.en.svg) · [LF](Осциллограммы/point-09_04814.0mm_ch2-ch4.en.svg) |
| 10 | 5635 | n/a | n/a | n/a | n/a | [HF](Осциллограммы/point-10_05635.0mm_ch1-ch3.en.svg) · [LF](Осциллограммы/point-10_05635.0mm_ch2-ch4.en.svg) |

For nine points inside cal2:

| Metric | ADC | Digital |
|---|---:|---:|
| Mean difference, mm | 5.08 | 4.93 |
| RMS difference, mm | 13.36 | 13.16 |
| Maximum absolute difference, mm | 22.96 | 22.81 |

These are averaged differences from Vector60 on this bench, not confirmation of absolute accuracy or dynamic rangefinder error. 5635 mm is outside the cal2 domain (638–5583 mm); no extrapolation is performed. This point also recorded a latched digital-overflow flag `diagnostics=4`. Current analog/digital valid flags were set. The event's cause is unknown; the FPGA was not reset, and the flag is retained in the data and workbook.

## Bench and settings

The FPGA controls AD9959, digitises four sine-wave signals after SA612 and four detector outputs using ADS8681 devices, and also measures digital-signal phases after comparators. The reference PIN photodiode receives light from the emitter through fibre; the second receives reflection from a target on a tripod.

| RIGOL DS1104Z | Connector | Purpose |
|---|---|---|
| CH1 | X9 | Reference HF |
| CH2 | X10 | Reference LF |
| CH3 | X11 | Reflected HF |
| CH4 | X12 | Reflected LF |

Phase is reflected minus reference: CH3−CH1 and CH4−CH2. Vector60 measures distance to the same stationary target via Bluetooth. COM9: 115200, 8N1, UART v3 with CRC, one outstanding request. The target polling interval was 20 ms; actual intervals are retained in the primary data. FPGA: 125 MHz, ADCs 250 ksample/s, analogue window 1000 samples (4 ms), digital accumulation 16 periods. Detectors must have |U| ≥0.5 V on ADC5–8.

| DDS | FTW | Frequency, Hz | ASF | POW |
|---|---:|---:|---:|---:|
| CH0 | 12845056 | 1495361.328125 | 200 | 0 |
| CH1 | 635888254 | 74027135.735378 | 1000 | 0 |
| CH2 | 12879416 | 1499361.358583 | 1000 | 0 |
| CH3 | 635830272 | 74020385.742188 | 450 | 0 |

HF IF **6749.993190 Hz**, LF IF **4000.030458 Hz**. The bank was read before every point and matched the cal2 bank, generation=0. DDS and firmware were unchanged during the series. POF SHA256: `7e652373ae74ca5d1734248706c16cae9fdaf9ef25b28a321869271220e0212d`.

## Selection and processing

After stopping: 3 s settling, then ≥15 s and ≥6 distance-meter responses; after two screenshots, one further distance check. Allowed Vector60 spread ≤3 mm; fresh valid UART packets ≥98%; no UART CRC errors or timeouts. Read gaps >200 ms reject an attempt; initial points were checked against the same rule after recording. All selected packets in accepted points are valid/fresh. Phases are averaged circularly; amplitudes and detectors arithmetically. Instruments have independent clocks: stationary intervals are compared, without claiming synchronisation between distance meter, screenshot and FPGA.

Failed attempts are retained: USB timeout during point 2's screenshot; BLE disconnections at points 3 and 8; a 0.403 s UART gap in the first point 10 attempt; a repeated point 10 attempt rejected by the strict diagnostics=0 rule. HDL inspection established that bit2 latches a past event until reset. The third point 10 attempt is stored separately with an explicit `sticky_digital_overflow` note, without relaxing checks of the other diagnostic bits or replacing the original failed intervals. Point selection was independent of error relative to the model.

LF phase selects the integer HF cycle; a degree-4 polynomial calculates distance from unwrapped HF phase. Branch margin ≥90° and the x range are checked. Coefficients: [calibration.json](calibration.json), ID `6c959d57db56d0397e0618d8026c43604e38874606a59c39262eb9daf9059de6`. Only the source path was normalised in the publication copy; numerical coefficients and ID are unchanged. The exact original file is retained in the primary session.

## Screenshots and verification

PNGs are native 800×480 screens. Only known incorrect CRCs in RIGOL service tEXt chunks were repaired; pixel data are unchanged. SVG adds an external distance/channel-pair caption and embeds the complete original PNG. The instrument's on-screen frequency counter showed unstable/invalid values; its display **is not used** as an IF measurement. Caption IFs are calculated from the read-back DDS bank. Volts/div were adapted to each pair's amplitude. After capture, original scales, offsets and all four traces were restored; the oscilloscope was left in RUN, 50 μs/div. COM9 and BLE were released.

All 20 images were visually reviewed. 15001 binary UART packets from accepted attempts were parsed again; every field matched JSON and there were no CRC errors. Excel formulas were checked against desktop_app/distance.py, including changing a phase, restoring its original value and re-importing the saved XLSX. The file preserves formulas, cached values, filters, frozen rows/first column and an editable scatter chart with nine point pairs. Microsoft Excel was not launched for this verification.

Primary session: `captures/bench/20261103T165315Z-paired-scope/` (local, outside the publication package). Structured means: [measurements.json](measurements.json); point metadata: `Данные/`; screenshot mapping: [photo-index.json](photo-index.json). SHA256 of compact files and primary sources: [manifest.json](manifest.json). Local preparation does not imply repository publication or push.
