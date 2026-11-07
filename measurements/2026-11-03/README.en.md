# Bench series of 3 November 2026

[Русский](README.md) | **English**

10 stationary positions, **762–5635 mm**, 20 oscilloscope screenshots.
The series was recorded at 20:53–21:13 Samara (UTC+4). The owner moved the
target after a request and confirmed that it had stopped. The series ended
when the room's available distance was exhausted.

The [Excel workbook with formulas](Bench%20measurements.en.xlsx) contains
Vector60 distance, FPGA analogue and digital phases, calculated distances
and errors, amplitudes, detector voltages, frequencies, phase standard
deviations, diagnostics and screenshot names. The “Calculation” sheet shows
cal2 coefficients and intermediate calculations.
[All oscilloscope captures](Осциллограммы/README.en.md) are labelled with distance.
The English workbook and SVG captions are derivatives; original Russian
files and the historical measurement manifest remain unchanged.

## Results

Error = calculated distance − distance-meter reading, mm. The cal2 model
was fixed **before** the series and was not fitted to these points.
Distance was calculated on the PC/in Excel from FPGA phases, not inside the FPGA.

| Point | Distance meter, mm | ADC, mm | Digital, mm | ADC error, mm | Digital error, mm | Captures |
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

For the nine points inside cal2:

| Metric | ADC | Digital |
|---|---:|---:|
| Mean discrepancy, mm | 5.08 | 4.93 |
| RMS discrepancy, mm | 13.36 | 13.16 |
| Maximum absolute discrepancy, mm | 22.96 | 22.81 |

This is discrepancy against Vector60 on this bench after averaging, not
confirmation of the rangefinder's absolute accuracy or dynamic error.
5635 mm lies outside cal2 (638–5583 mm); no extrapolation is performed.
The latched digital-overflow flag `diagnostics=4` was also recorded at
this point. Current analog/digital valid flags were set. The event's
cause is unknown; the FPGA was not reset, and the flag is preserved in
the data and workbook.

## Bench and settings

The FPGA controls AD9959, digitises four sinusoidal signals after SA612
and four detector outputs using ADS8681 devices, and also measures the
phases of comparator-derived digital signals. The reference PIN photodiode
receives emitter light through an optical fibre; the second receives
reflection from the tripod-mounted target.

| RIGOL DS1104Z | Connector | Purpose |
|---|---|---|
| CH1 | X9 | HF reference |
| CH2 | X10 | LF reference |
| CH3 | X11 | HF reflected |
| CH4 | X12 | LF reflected |

Phase is reflected minus reference: CH3−CH1 and CH4−CH2.
Vector60 measures distance to the same stationary target over Bluetooth.
Historical COM9 settings: 115200, 8N1, UART v3 with CRC, one outstanding
request. The target poll interval was 20 ms; the actual interval is saved
in the primary data. FPGA: 125 MHz, ADCs 250 ksample/s, analogue window
1000 samples (4 ms), digital accumulation 16 periods. Detector inputs
ADC5–8 must have |U| ≥0.5 V.

| DDS | FTW | Frequency, Hz | ASF | POW |
|---|---:|---:|---:|---:|
| CH0 | 12845056 | 1495361.328125 | 200 | 0 |
| CH1 | 635888254 | 74027135.735378 | 1000 | 0 |
| CH2 | 12879416 | 1499361.358583 | 1000 | 0 |
| CH3 | 635830272 | 74020385.742188 | 450 | 0 |

HF IF **6749.993190 Hz**, LF IF **4000.030458 Hz**.
The bank was read before every point and matched the cal2 bank, generation=0.
DDS and firmware were unchanged during the series.
POF SHA256: `7e652373ae74ca5d1734248706c16cae9fdaf9ef25b28a321869271220e0212d`.

## Selection and processing

After stopping, allow 3 s to settle, then record for ≥15 s and ≥6
distance-meter replies; after the two screenshots, take another distance
check. Permitted Vector60 spread ≤3 mm, valid fresh UART packets ≥98%,
no CRC errors or UART timeouts. Read gaps >200 ms reject an attempt;
the first points were checked against the same rule after recording.
All selected packets in accepted points are valid/fresh. Phases are
averaged circularly; amplitudes and detectors arithmetically. Instruments
have independent clocks: stationary intervals are compared, with no claim
that the distance meter, screenshot and FPGA are synchronous.

Failed attempts are preserved: a screenshot USB timeout at point 2;
BLE disconnections at points 3 and 8; a 0.403 s UART gap in the first
attempt at point 10; and a second point-10 attempt rejected by the strict
diagnostics=0 rule. HDL review established that bit2 latches a past event
until reset. The third point-10 attempt is preserved separately with
an explicit `sticky_digital_overflow` label, without relaxing checks of
the other diagnostic bits or replacing the original failed intervals.
Point selection did not depend on error relative to the model.

LF phase selects the integer HF cycle count; a fourth-degree polynomial
calculates distance from unwrapped HF phase. Branch margin ≥90° and
the x range are checked. Coefficients: [calibration.json](calibration.json),
ID `6c959d57db56d0397e0618d8026c43604e38874606a59c39262eb9daf9059de6`.
Only the source path was normalised in the publication copy; numerical
coefficients and ID are unchanged. The exact original file remains
in the primary session.

## Captures and verification

PNG files are native 800×480 screens. Only known invalid CRCs in RIGOL
ancillary tEXt chunks were corrected; pixel data were unchanged. SVG adds
an external distance/channel-pair caption and embeds the entire original PNG.
The screen's built-in frequency counter displayed unstable/invalid values;
its display is **not used** as an IF measurement. Caption IFs are calculated
from the read-back DDS bank. Volts/div were adjusted to each pair's amplitude.
After capture, original scales, offsets and all four traces were restored;
the oscilloscope was left in RUN at 50 µs/div. COM9 and BLE were released.

All 20 images were visually reviewed. The 15001 binary UART packets from
accepted attempts were parsed again; every field matched JSON, with no
CRC errors. Excel formulas were compared against desktop_app/distance.py;
changing a phase, restoring the original and reimporting the saved XLSX
were checked. The file retains formulas, cached values, filters, frozen
rows and first column, and an editable scatter chart with nine point pairs.
Microsoft Excel was not launched for that verification.

Primary session: `captures/bench/20261103T165315Z-paired-scope/` (local,
outside the publication package). Structured means:
[measurements.json](measurements.json), point metadata: `Данные/`,
screenshot mapping: [photo-index.json](photo-index.json).
SHA256 of compact files and primary sources: [manifest.json](manifest.json).
Local preparation does not itself mean repository publication or push.
