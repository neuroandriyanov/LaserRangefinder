# What the bench consists of

[Русский](stand.md) | **English**

The bench compares three things: actual target movement, signal waveforms and FPGA
calculation results. It is a tabletop setup with manual movement, not an automated
measurement line.

## Equipment

| Component | Purpose |
|---|---|
| Restored LE-200 PROFIBUS optics | Lens, collimator, optical path and receiver assembly |
| Two BPX65 PIN photodiodes | Direct reference light through optical fibre and light reflected from the target |
| QL67D7SA | Replacement laser diode, red region around 670 nm according to the author |
| Four SA612 mixers | Downconversion of the two frequencies in each photoreceiver channel to IF |
| Custom board with AD9959 and Cyclone IV | Signal generation, control and phase calculation |
| Eight ADS8681 devices | Four IF sine waves and four amplitude-detector outputs |
| Comparators | Digital signals for the second phase measurement method |
| RIGOL DS1104Z | Observation of four signals, screen capture and waveform checks |
| Vector60 with Bluetooth | Distance reference for the same target |
| USB–TTL | UART between FPGA and PC, 115200 8N1, 3.3 V levels |
| USB-Blaster | Programming and verification of the FPGA / EPCS4 image |
| PC and dedicated Bluetooth USB adapter | Application, logs, calculations and distance-meter communication |
| Target on a tripod | Manual distance changes with stops |

[Board, optics and power-supply photographs](../hardware/photos/README.en.md),
[schematics and bill of materials](../hardware/README.en.md). The external SA612
path is not fully represented in the main schematic. The optical history and
replacement component types were reported by the author; they were not inferred
from the main-board PDF.

## Channel connections

The latest analogue series used this mapping:

| Oscilloscope | Connector | Signal | Comparison |
|---|---|---|---|
| CH1 | X9 | HF reference | CH3−CH1 |
| CH2 | X10 | LF reference | CH4−CH2 |
| CH3 | X11 | HF reflected | CH3−CH1 |
| CH4 | X12 | LF reflected | CH4−CH2 |

Earlier observations of the digital path used X17–X20 in the corresponding order.
Record any probe rearrangement in a new session: the same CH1–CH4 labels alone
do not identify whether the observed signal is analogue or digital.

The current DDS CH0/CH2 form the LF pair and CH1/CH3 form the HF pair. Do not
confuse them with oscilloscope or ADC input numbers. Exact FTWs and amplitudes
are in the [profile](../app/profiles/dds/default.json). LF IF is 4000.030458 Hz,
HF IF is 6749.993190 Hz; the nominal AD9959 clock is 500 MHz.

## How the latest series was recorded

1. The author positioned the target and confirmed it was stationary.
2. After settling, distance-meter and FPGA replies were recorded. The latest series
   used a 3 s settling period, at least 15 s of recording and at least six
   distance-meter replies. Selection criteria are in the
   [report](../measurements/2026-11-03/README.en.md).
3. Two oscilloscope screens were saved: CH1+CH3 and CH2+CH4. Distance was then
   checked again with the distance meter.
4. Only after the point was complete was the target requested to move.
   “No room to move” ended the series.

This is a separate verification series. Automatic calibration in the application
uses a different criterion: **three identical distance-meter replies** and valid,
fresh phases. It sounds a beep when adding a point. Those three replies mean
neither three synchronous samples from all instruments nor the criterion used
for the latest long recording.

The distance meter and oscilloscope have their own clocks and delays. Their data
were compared while the target was stopped. The FPGA synchronises its own ADCs;
this does not synchronise external instruments with the FPGA. Motion requires
a separate investigation of measurement timing.

## What is saved

A series benefits from the firmware version/hash, read-back DDS bank, probe
connections, oscilloscope settings, request and response timestamps, raw UART
packets, distance-meter readings and errors. The compact result includes means,
spread, validity flags, formulas and captioned captures; it does not replace
the raw recording.

This package contains FPGA and Vector60 clients, the application and saved
oscilloscope captures. The author's RIGOL automatic capture scripts and complete
raw sessions are not included. Repeating the work on another bench requires a
suitable SCPI/VISA client or screen saving through the oscilloscope itself.

The application and scripts do not move the target. An external motion controller
must decide how a real mechanism behaves when measurement validity is lost.

## The next test scale

So far, testing has used a small room. Testing at 100–200 m will require a long
site, new reference distances and checks of repeatability, drift and operation
in motion. The enclosure is intended for later equipment trials; IP68 test
results have not yet been provided.
