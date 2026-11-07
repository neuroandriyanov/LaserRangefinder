# Inherited UART v2 fields

[Русский](protocol-v2-fields.md) | **English**

Reference table for the old format, for comparison with v3. **Current firmware
uses v3**, described in the [main document](protocol-v3.en.md). V3 inherits
bytes 4–87; bytes 88–111, length, version, periods, age and CRC are defined
only by v3. Current firmware has no FIR. The ADC5–8 threshold and DDS
retuning are described in v3.

## Measurement frame: 96 bytes

| Offset | Size | Field |
|---|---:|---|
| 0…3 | 4 | `A5 5A 02 60` |
| 4 | 1 | `82` |
| 5 | 1 | 0 — request processed; **this is not a measurement-validity flag** |
| 6 | 1 | Analogue flags, see below |
| 7 | 1 | Digital flags: bit0 HF valid, bit1 LF valid |
| 8 | 2 | Request number |
| 10 | 1 | `adc_ok`: bit0…7 for ADC1…8 |
| 11 | 1 | `channel_valid`: bit0…3 for analogue channels 1…4 |
| 12 | 4 | Analogue-result counter, 1 ms increment, unsigned32 |
| 16 | 4 | ADC sample counter, unsigned32, 250000/s |
| 20, 24 | 4+4 | Analogue HF and LF phases, signed32 |
| 28, 32 | 4+4 | Digital HF and LF phases, signed32, mean of both polarities |
| 36, 40 | 4+4 | Digital HF: rising / falling edges separately |
| 44, 48 | 4+4 | Digital LF: rising / falling edges separately |
| 52, 56, 60, 64 | 4×4 | I/Q magnitudes of channels 1…4 after CORDIC, unsigned32 |
| 68, 70, 72, 74 | 4×2 | Latest raw ADC1…4 codes (sine waves), unsigned16 |
| **76, 78, 80, 82** | **4×2** | **ADC5…8: outputs of four amplitude detectors**, unsigned16 |
| 84 | 2 | Digital-result counter, unsigned16 |
| 86 | 2 | Analogue amplitude threshold, 100 peak counts |
| 88, 90 | 2+2 | Latest HF/LF reference square-wave periods in 125 MHz ticks |
| 92 | 1 | Digital-result age, approximately ms, saturates at 255 |
| 93 | 1 | Diagnostics: bit0 RX error, bit1 request queue overflow, bit2 digital buffer/CDC overflow |
| 94 | 2 | CRC16 of bytes 2…93 |

Analogue flags, byte6: bit0 HF valid; bit1 LF valid; bit2 `beam_lost`
after 100 ms of continuous invalidity; bit3 initialisation error in at
least one ADC; bit4 bad sample/clipping in the window; bit5 window not full;
bit6 RX error; bit7 analogue-processing overflow.
RX/queue/digital-overflow diagnostic bits remain set until reset, but
do not themselves prevent subsequent good measurements from recovering.

Phases: `degrees = signed32 × 360 / 2^32`, range [-180,180).
The digital value inside the FPGA has 24 bits and is padded with eight
zero least-significant bits in the packet. All differences are channel 3
minus 1 (HF), channel 4 minus 2 (LF). The ±180° wrap is normal;
there is no distance unwrapping.

Sinusoidal peak amplitude in ADC counts:
`2 × magnitude / (1000 × 1.646760258121)`; then multiply by 0.000375 V.
For raw ADC codes: `(raw - 32768) × 0.000375 V`.
ADC5…8 transmit detector-output voltages at the ADC inputs, not calibrated
optical/RF power. The packet contains the latest simultaneous sample from
all eight ADCs near the end of the analogue window; these are separate
from the I/Q amplitudes averaged over 4 ms. No detector transfer factor
has been applied here.
