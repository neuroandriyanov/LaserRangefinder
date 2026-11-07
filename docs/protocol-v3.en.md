# UART v3: atomic DDS configuration and tunable phase meters

[Русский](protocol-v3.md) · **English**

Current implementation as of 03.11.2026. Application 0.5.1 and CLI `app/tools/fpga_config.py` support v3. The verified image and new verification build are described in the [FPGA section](../fpga/README.en.md).

## Clocks, assignments and limits

- AD9959 SYSCLK is nominally 500 MHz; SYNC_CLK is 125 MHz; ADC rate is 250 ksample/s.
- CH0/CH2 are the LF pair; CH1/CH3 are the HF pair; outputs are not swapped.
- Positive FTW differences: `delta_low=CH2−CH0`, `delta_high=CH1−CH3`. This version does not support swapping the local-oscillator side.
- Each difference must be **8590…171799**, approximately 1…20 kHz. Actual limits: 1000.007614…20000.035398 Hz. The upper limit exceeds 20 kHz because of rounding to the nearest DDS step, not extra bandwidth.
- Each output FTW is 1…`7FFFFFFF`; this is a digital first-Nyquist-zone limit, not confirmation of board bandwidth, linearity or allowable power.
- POW: 0…16383, `phase_deg=POW*360/16384`. ASF: 0…1023, without conversion to power.
- Analogue and digital phase pairs: channel 3−1 (X11−X9, HF) and channel 4−2 (X12−X10, LF). Different IFs are not compared to one another.

Startup values were updated on 2026-11-03 to the selected bench profile:

| Output | FTW | POW | ASF |
|---|---:|---:|---:|
| CH0 | 12845056 | 0 | 200 |
| CH1 | 635888254 | 0 | 1000 |
| CH2 | 12879416 | 0 | 1000 |
| CH3 | 635830272 | 0 | 450 |

Startup IFs: LF **4000.030458 Hz**, HF **6749.993190 Hz**. Initial NCO steps and expected digital periods derive from the same bank; DDS settings and phase meters do not disagree at reset.

Settings are temporary: reset restores startup values. The FPGA does not write parameters to EPCS4. Saving a desired profile on the PC is the application's responsibility.

## Request, 12 bytes

All multibyte values are little-endian. Link: 115200, 8N1, TTL 3.3 V, X5.

| Offset | Size | Contents |
|---|---:|---|
| 0 | 2 | `A5 5A` |
| 2 | 1 | Version `03` |
| 3 | 1 | Length `0C` |
| 4 | 1 | `01 SET_PARAMETER` / `02 GET` |
| 5 | 1 | Parameter identifier / GET type |
| 6 | 2 | Request ID |
| 8 | 2 | Value |
| 10 | 2 | CRC16 of bytes 2…9 |

CRC-16/MODBUS: initial `FFFF`, reflected polynomial `A001`, no final XOR; CRC least-significant byte first. ASCII `123456789` → `4B37`. Invalid CRC, version or length causes no execution and no response. An incomplete request has a 30 ms interbyte timeout. One pending command is retained while a response is being transmitted. Only one outstanding request on the PC side is recommended.

There is no unsolicited telemetry. FPGA v3 does not accept v2 requests. The `fpga_measurements.py` decoder reads both versions but sends v2 by default to retain compatibility with a board not yet updated. CLI `fpga_config.py` explicitly uses v3.

## SET: stage a complete bank and apply it

| ID | Value | Action |
|---|---:|---|
| `F0` | `B001` | BEGIN: clear the received-word mask and start a new transaction |
| `10`…`1F` | 16-bit word | Write a word to the temporary M9K bank |
| `F1` | `A55A` | COMMIT: validate the entire bank and apply it simultaneously |
| `F2` | 0 | ABORT: discard the staged bank, leaving the active bank unchanged |

For channel `c=0…3`, words are located at ID `10h+4*c`:

| ID increment | Value |
|---|---|
| 0 | FTW[15:0] |
| 1 | FTW[31:16] |
| 2 | POW; the upper two bits must be zero |
| 3 | ASF; the upper six bits must be zero |

After BEGIN, **all 16 words** are mandatory. Words can arrive in any order; repeating a word replaces its staged value. BEGIN cancels a previous incomplete transaction. Range validation occurs at COMMIT. Failed validation does not change active parameters or cause IO_UPDATE. After a range error, words can be corrected and COMMIT retried. After a successful COMMIT, the next change requires a new BEGIN.

Normal PC cycle: BEGIN → 16 words, checking each ACK → COMMIT → GET configuration. ACK `STAGED` means only acceptance into the temporary bank. ACK `OK` for COMMIT is returned after the actual DDS write sequence, common update and settling interval. Configuration readback returns settings applied by the FPGA; this is **not electrical readback of AD9959 registers over SPI**.

If the COMMIT ACK is lost, do not automatically repeat the entire operation: first read the bank and generation to determine whether the change was applied.

## Short response, 12 bytes

`A5 5A 03 0C`, followed by:

| Offset | Field |
|---|---|
| 4 | `81` SET, `82` failed GET, `FF` unknown command |
| 5 | Status |
| 6 | Parameter ID from the request |
| 7 | 0 |
| 8…9 | Request ID |
| 10…11 | CRC16 of bytes 2…9 |

Statuses: 0 `OK`, 1 `NOT_IMPLEMENTED` (reserved previous IDs 0…15), 2 `UNKNOWN_COMMAND`, 3 `BAD_ARGUMENT`, 4 `STAGED`, 5 `BUSY`, 6 `INCOMPLETE`.

## GET configuration: parameter 1, value 0

48-byte response:

| Offset | Size | Field |
|---|---:|---|
| 0…3 | 4 | `A5 5A 03 30` |
| 4…5 | 2 | `82 00` |
| 6 | 1 | `80`: configuration-response marker |
| 7 | 1 | bit0: initialisation/application not yet complete |
| 8 | 2 | Request ID |
| 10 | 2 | Configuration generation; 0 at startup, +1 for a successful COMMIT, modulo 65536 |
| 12 | 32 | Four CH0…CH3 records: FTW uint32, POW uint16, ASF uint16 |
| 44 | 2 | Reserved, 0 |
| 46 | 2 | CRC16 of bytes 2…45 |

## GET measurements: parameter 0, value 0

**112-byte** response. Bytes 4…87 retain the v2 field layout: status, valid/errors, ID, ADCs, counters, eight phases, four I/Q magnitudes, raw ADC1…8 values, digital counter and amplitude threshold. The signature is now `A5 5A 03 70`. The complete table of initial fields is in the [v2 protocol](protocol-v2-fields.en.md); the v2 CRC at 94…95 is absent in v3.

| Offset | Size | v3 field |
|---|---:|---|
| 88 | 4 | HF period, uint32, 125 MHz ticks |
| 92 | 4 | LF period, uint32, 125 MHz ticks |
| 96 | 1 | Digital-result age, ms, saturates at 255 |
| 97 | 1 | Diagnostics: RX / queue / digital overflow, bits 0/1/2 |
| 98 | 2 | Configuration generation |
| 100 | 4 | delta_high FTW |
| 104 | 4 | delta_low FTW |
| 108 | 1 | bit0: retuning/initialisation, results invalid |
| 109 | 1 | Reserved, 0 |
| 110 | 2 | CRC16 of bytes 2…109 |

Signed32 phases: `deg=value*360/2^32`, range [−180,180). Digital phases retain 24 significant bits. Magnitude-to-peak-ADC-count conversion remains `2*magnitude/(1000*1.646760258121)`; one count is 0.000375 V. ADC5…8 report raw detector voltages without power calibration. Their validity threshold is **|U| ≥ 0.5 V on every ADC5…8**; negative polarity is allowed following the owner's clarification. With offset-binary and 375 μV/count, codes `≤31434` or `≥34102` pass. Nearest levels: ±0.499875 V fails, ±0.500250 V passes. Magnitude here refers to detector voltage relative to 0 V, not the amplitude of ADC1…4 sine waves. The `min_amplitude_counts` field at bytes 86–87 remains **100**, still describing the ADC1…4 I/Q-amplitude threshold. Packet format and protocol version are unchanged.

## Synchronisation, windows and validity

FIR is removed from the project. The analogue phase meter uses ADC1…4 directly: two exact NCOs, a 1000-sample / 4 ms window, output every 250 samples / 1 ms. Three-parameter least squares fits cos, −sin and a DC component; this handles a noninteger number of periods without FFT or frequency searching. Pure sine-wave scaling does not change phase in the ideal model. Quantisation, noise, harmonics, clipping and amplitude changes within the window remain error sources. Validity requires sufficient amplitude, a filled window, no errors/clipping and sufficient energy in the required tone.

The digital phase meter uses two NCOs at 125 MHz, 18-bit interval counters and 16 edges of each polarity. Period tolerance is approximately ±3.125% and 4 ticks. Missing edges for more than 1.5 expected periods clears validity; checking all four channels takes up to another 128 ns. The last digital result must be **less than 20 ms old**. This supports a 16 ms window at 1 kHz IF. Repeated digital counters in neighbouring 100 Hz requests are acceptable if the analogue result is fresh and digital valid/age are acceptable.

A fault on any digital input clears both digital valid flags. Recovery requires fresh edges. ADC and comparator windows have different lengths/midpoints; they are not guaranteed to represent the same instant of motion. The delayed 100 ms beam_lost flag is retained; a controller need not wait for it before rejecting data based on valid or a communication timeout.

If any ADC5…8 detector falls below the magnitude threshold, both analogue and both digital validity flags are cleared. The check uses the samples from the same completed block sent in the packet; it updates every 1 ms. There is no additional 100 ms wait before clearing valid. When all levels and other conditions recover, validity recovers automatically and beam_lost clears. Raw detector voltages are transmitted even when invalid. The channel_valid field remains a diagnostic for ADC1…4 sine-wave channels and therefore does not by itself mean overall valid.

COMMIT resets phase accumulations and inhibits valid output. UART and ADCs are not reinitialised. The AD9959 bank is written using single-bit SPI; after all 20 frames, **one 32 ns IO_UPDATE pulse** is generated. CFR=`000321`: single tone, matched pipeline, previous DAC mode; automatic and continuous DDS phase-accumulator clearing are disabled. POW adds to the accumulator's current phase rather than clearing its history. Without COMMIT there are no repeated writes or updates.

IO_UPDATE uses the second output of the same PLL: 125 MHz with phase −1.25 ns relative to input SYNC_CLK. TimeQuest checks setup and hold relative to the next selected DDS edge, including tSU=4.8 ns and a **preliminary total SYNC_CLK+IO_UPDATE trace budget of 0.5 ns**. This budget has not yet been measured on the board. After DDS ACK there is a 2 ms wait, then new measurement windows fill. The 2 ms is an implemented delay, not bench verification of every transient.

## PC use and throughput

```powershell
# Only generate example JSON; do not open a port.
.\.venv\Scripts\python.exe tools/fpga_config.py --defaults-json
# Commands from app; replace COM3 with your own port:
.\.venv\Scripts\python.exe tools/fpga_config.py --port COM3 --read-config
.\.venv\Scripts\python.exe tools/fpga_config.py --port COM3 --request
.\.venv\Scripts\python.exe tools/fpga_config.py --port COM3 --set-config desired.json
# Repeated reading with original UART bytes and a table saved:
.\.venv\Scripts\python.exe tools/fpga_measurements.py --port COM3 --protocol-version 3 --seconds 30 --csv captures/run-v3.csv --raw captures/run-v3.bin
```

A 112-byte response plus a 12-byte request at 115200 8N1 requires at least 10.764 ms before result waiting and USB/OS delays. Therefore 100 full responses/s cannot be reached at this speed; the strict theoretical limit is below 93/s. GUI and calibration are implemented in the desktop application. Distance/velocity calculation is not yet in the FPGA. Old calibration cannot automatically be applied to other frequencies and analogue-path operating conditions.

## Desktop application support

Application 0.5.1 sends v3 and supports the complete DDS bank with one COMMIT and readback verification. Application and FPGA startup profiles match: LF IF 4000.030458 Hz, HF IF 6749.993190 Hz. Settings are saved on the PC and sent to the board using a button. [Application guide](../app/README.en.md).
