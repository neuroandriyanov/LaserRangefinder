# UART v3: atomic DDS configuration and retunable phase meters

[Русский](protocol-v3.md) | **English**

Current implementation as of 3 November 2026. Application 0.5.1 and the
`app/tools/fpga_config.py` CLI support v3. The verified image and the new
verification build are described in the [FPGA section](../fpga/README.en.md).

## Clocks, assignments and limits

- AD9959 nominal SYSCLK 500 MHz; SYNC_CLK 125 MHz; ADCs 250 ksample/s.
- CH0/CH2 are the LF pair, CH1/CH3 the HF pair; outputs are not swapped.
- Positive FTW differences: `delta_low=CH2−CH0`, `delta_high=CH1−CH3`.
  Swapping the local-oscillator side is not supported by this version.
- Each difference may be **8590…171799**, approximately 1…20 kHz.
  Actual limits: 1000.007614…20000.035398 Hz. The upper limit's difference
  from 20 kHz is rounding to the nearest DDS step, not additional bandwidth.
- FTW of each output: 1…`7FFFFFFF`; this is a digital first-Nyquist-zone limit,
  not confirmation of the board's bandwidth, linearity or permissible power.
- POW: 0…16383, `phase_deg=POW*360/16384`. ASF: 0…1023, without conversion to power.
- Analogue and digital phase pairs: channel 3−1 (X11−X9, HF) and channel 4−2
  (X12−X10, LF). Different IFs are not compared against one another.

Startup values were updated on 2026-11-03 from the selected bench profile:

| Output | FTW | POW | ASF |
|---|---:|---:|---:|
| CH0 | 12845056 | 0 | 200 |
| CH1 | 635888254 | 0 | 1000 |
| CH2 | 12879416 | 0 | 1000 |
| CH3 | 635830272 | 0 | 450 |

Startup IFs: LF **4000.030458 Hz**, HF **6749.993190 Hz**.
Initial NCO steps and expected digital periods are derived from the same bank;
DDS settings and phase meters therefore agree after reset.

Settings are temporary: reset restores the startup values. The FPGA does not
write parameters to EPCS4. Saving a desired profile on the PC is the application's
responsibility.

## Request, 12 bytes

All multibyte values are little-endian. Link: 115200, 8N1, 3.3 V TTL, X5.

| Offset | Size | Contents |
|---|---:|---|
| 0 | 2 | `A5 5A` |
| 2 | 1 | Version `03` |
| 3 | 1 | Length `0C` |
| 4 | 1 | `01 SET_PARAMETER` / `02 GET` |
| 5 | 1 | Parameter ID / GET type |
| 6 | 2 | Request ID |
| 8 | 2 | Value |
| 10 | 2 | CRC16 of bytes 2…9 |

CRC-16/MODBUS: initial value `FFFF`, reflected polynomial `A001`, no final XOR;
CRC low byte first. ASCII `123456789` → `4B37`. Invalid CRC, version or length
is not executed and receives no reply. Interbyte timeout for an unfinished
request is 30 ms. One pending command is retained while a reply is being sent.
Only one outstanding request on the PC side is recommended.

There is no unsolicited telemetry. FPGA v3 does not accept v2 requests. The
`fpga_measurements.py` decoder can read both versions, but sends v2 by default
to remain usable with a board that has not yet been updated. The
`fpga_config.py` CLI explicitly uses v3.

## SET: stage a complete bank and apply it

| ID | Value | Action |
|---|---:|---|
| `F0` | `B001` | BEGIN: clear the received-word mask and start a new transaction |
| `10`…`1F` | 16-bit word | Write a word to the temporary M9K bank |
| `F1` | `A55A` | COMMIT: validate the whole bank and apply it atomically |
| `F2` | 0 | ABORT: discard the staged bank without changing the active bank |

For channel `c=0…3`, its words start at ID `10h+4*c`:

| ID offset | Value |
|---|---|
| 0 | FTW[15:0] |
| 1 | FTW[31:16] |
| 2 | POW, top two bits must be zero |
| 3 | ASF, top six bits must be zero |

After BEGIN, **all 16 words** are required. Words may be sent in any order;
repeating a word replaces its staged value. BEGIN cancels a previous unfinished
transaction. Ranges are validated at COMMIT. A failed validation neither changes
active parameters nor triggers IO_UPDATE. After a range error, correct the
words and retry COMMIT. After a successful COMMIT, the next change requires
a new BEGIN.

Normal PC sequence: BEGIN → 16 words, checking each ACK → COMMIT → GET configuration.
ACK `STAGED` only confirms receipt in the temporary bank. COMMIT ACK `OK` is
sent after the actual DDS write sequence, common update and settling delay.
Configuration readback returns the settings applied by the FPGA; it is **not
an electrical SPI read of AD9959 registers**.

If the COMMIT ACK is lost, do not automatically repeat the entire operation:
first read the bank and generation to determine whether the change was applied.

## Short reply, 12 bytes

`A5 5A 03 0C`, followed by:

| Offset | Field |
|---|---|
| 4 | `81` SET, `82` failed GET, `FF` unknown command |
| 5 | Status |
| 6 | Parameter ID from the request |
| 7 | 0 |
| 8…9 | Request ID |
| 10…11 | CRC16 of bytes 2…9 |

Statuses: 0 `OK`, 1 `NOT_IMPLEMENTED` (reserved former IDs 0…15),
2 `UNKNOWN_COMMAND`, 3 `BAD_ARGUMENT`, 4 `STAGED`, 5 `BUSY`, 6 `INCOMPLETE`.

## GET configuration: parameter 1, value 0

48-byte reply:

| Offset | Size | Field |
|---|---:|---|
| 0…3 | 4 | `A5 5A 03 30` |
| 4…5 | 2 | `82 00` |
| 6 | 1 | `80`: configuration-reply marker |
| 7 | 1 | bit0: initialisation/application is not yet complete |
| 8 | 2 | Request ID |
| 10 | 2 | Configuration generation; 0 at startup, +1 per successful COMMIT, modulo 65536 |
| 12 | 32 | Four CH0…CH3 records: FTW uint32, POW uint16, ASF uint16 |
| 44 | 2 | Reserved, 0 |
| 46 | 2 | CRC16 of bytes 2…45 |

## GET measurements: parameter 0, value 0

Reply length: **112 bytes**. Bytes 4…87 retain the v2 field layout:
status, valid/errors, ID, ADCs, counters, eight phases, four I/Q magnitudes,
raw ADC1…8, digital counter and amplitude threshold.
The signature is now `A5 5A 03 70`. The complete table of initial fields is
in the [v2 protocol](protocol-v2-fields.en.md); the v2 CRC at 94…95 is absent in v3.

| Offset | Size | v3 field |
|---|---:|---|
| 88 | 4 | HF period, uint32, 125 MHz clock ticks |
| 92 | 4 | LF period, uint32, 125 MHz clock ticks |
| 96 | 1 | Digital-result age, ms, saturates at 255 |
| 97 | 1 | Diagnostics: RX / queue / digital overflow, bits 0/1/2 |
| 98 | 2 | Configuration generation |
| 100 | 4 | delta_high FTW |
| 104 | 4 | delta_low FTW |
| 108 | 1 | bit0: retuning/initialisation, results invalid |
| 109 | 1 | Reserved, 0 |
| 110 | 2 | CRC16 of bytes 2…109 |

Phases are signed32: `deg=value*360/2^32`, range [−180,180).
Digital phases retain 24 significant bits. Conversion of magnitude to peak ADC
counts remains `2*magnitude/(1000*1.646760258121)`; one count is 0.000375 V.
ADC5…8 transmit raw detector voltages, without power calibration.
The validity threshold for these inputs is **|U| ≥ 0.5 V on every ADC5…8 input**;
negative polarity is permitted, as clarified by the owner.
For offset-binary encoding and 375 µV/count, codes `≤31434` or `≥34102` pass.
Nearest levels: ±0.499875 V fails, ±0.500250 V passes. Here magnitude refers
to detector voltage relative to 0 V, not the sinusoidal amplitude of ADC1…4.
The `min_amplitude_counts` field at bytes 86–87 remains **100** and still
describes the I/Q amplitude threshold for ADC1…4. Packet format and protocol
version are unchanged.

## Synchronisation, windows and validity

FIR has been removed from the project. The analogue phase meter uses ADC1…4
directly: two exact NCOs, a 1000-sample / 4 ms window, output every
250 samples / 1 ms. A three-parameter least-squares fit uses cos, −sin and
DC components; this handles non-integer numbers of periods without FFT or
frequency search. Pure sinusoid amplitude scaling does not change phase in
the ideal model. Quantisation, noise, harmonics, saturation and amplitude
changes within a window remain error sources. Validity requires sufficient
amplitude, a full window, no errors/clipping and sufficient energy at the
required tone.

The digital phase meter uses two 125 MHz NCOs, 18-bit interval counters and
16 edges of each polarity. Period tolerance: approximately ±3.125% and
4 ticks. No edges for more than 1.5 expected periods invalidates the result;
checking all four channels adds up to 128 ns. The latest digital result must
be **less than 20 ms** old. This accommodates a 16 ms window at 1 kHz IF.
A repeated digital counter in adjacent 100 Hz requests is allowed if the
analogue result is fresh and digital valid/age checks pass.

A fault on any digital input clears both digital valid flags. Recovery
requires new edges. ADC and comparator windows have different lengths and
midpoints; they are not guaranteed to represent the same instant of motion.
The delayed 100 ms beam_lost flag is retained; a controller does not need
to wait for it before rejecting a measurement because of valid flags or
a communication timeout.

If any ADC5…8 detector is below the magnitude threshold, both analogue and
both digital validity flags are cleared. The check uses samples from the
same completed block transmitted in the packet; the result updates at 1 ms
intervals. There is no additional 100 ms wait before clearing valid. When
all levels and other conditions recover, validity returns automatically;
beam_lost also clears. Raw detector voltages are transmitted even when
measurements are invalid. The channel_valid field remains a diagnostic for
the ADC1…4 sinusoidal channels, so it alone does not establish overall validity.

At COMMIT, phase accumulations are cleared and valid output is inhibited.
UART and ADCs are not reinitialised. The AD9959 bank is written using single-bit
SPI; after all 20 frames, **one 32 ns IO_UPDATE pulse** is generated.
CFR=`000321`: single tone, matched pipeline, previous DAC mode; automatic
and persistent DDS phase-accumulator reset are disabled. POW is an offset
to the current accumulator phase, not a command to erase its history.
Without COMMIT, there are no repeated writes or updates.

IO_UPDATE uses the second output of the same PLL: 125 MHz, phase −1.25 ns
relative to incoming SYNC_CLK. TimeQuest checks setup and hold relative to
the next selected DDS edge, including tSU=4.8 ns and a **provisional total
SYNC_CLK+IO_UPDATE trace budget of 0.5 ns**. This budget has not yet been
measured on the board. After the DDS ACK, a 2 ms delay is observed before
new measurement windows fill. The 2 ms value is an implemented delay,
not a bench verification of every transient process.

## PC use and throughput

```powershell
# Only generate example JSON; no port is opened.
.\.venv\Scripts\python.exe tools/fpga_config.py --defaults-json
# Run from app; replace COM3 with your own port:
.\.venv\Scripts\python.exe tools/fpga_config.py --port COM3 --read-config
.\.venv\Scripts\python.exe tools/fpga_config.py --port COM3 --request
.\.venv\Scripts\python.exe tools/fpga_config.py --port COM3 --set-config desired.json
# Poll while saving original UART bytes and a table:
.\.venv\Scripts\python.exe tools/fpga_measurements.py --port COM3 --protocol-version 3 --seconds 30 --csv captures/run-v3.csv --raw captures/run-v3.bin
```

A 112-byte reply plus a 12-byte request at 115200 8N1 takes at least
10.764 ms, before result waiting time and USB/OS delays. Therefore 100 full
replies/s cannot be achieved at this rate; the hard theoretical limit is
below 93/s. The GUI and calibration are implemented in the desktop application.
The FPGA does not yet calculate distance or speed. Old calibration must not
be applied automatically to different frequencies or analogue-path conditions.

## Desktop application support

Application 0.5.1 sends v3 and supports the complete DDS bank with a common
COMMIT and readback verification. The application's startup profile matches
the FPGA: LF IF 4000.030458 Hz, HF IF 6749.993190 Hz. Settings are saved
on the PC and sent to the board using the button.
[Application guide](../app/README.en.md).
