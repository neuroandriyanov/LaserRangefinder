# What the bench consists of

[Русский](stand.md) · **English**

The bench compares three things: actual target movement, waveform shape and FPGA computation results. It is a desktop setup with manual movement, not an automated measurement line.

## Equipment

| Subsystem | Purpose |
|---|---|
| Restored LE-200 PROFIBUS optics | Lens, collimator, optical path and receiver assembly |
| Two BPX65 PIN photodiodes | Direct reference light through fibre and reflected target light |
| QL67D7SA | Replacement laser diode, red range around 670 nm according to the author |
| Four SA612 mixers | Shift both frequencies of each photoreceiver channel to IF |
| Custom board with AD9959 and Cyclone IV | Signal generation, control and phase computation |
| Eight ADS8681 devices | Four IF sine waves and four amplitude-detector outputs |
| Comparators | Digital signals for the second phase-measurement method |
| RIGOL DS1104Z | Observe four signals, save screenshots and inspect waveform shape |
| Vector60 with Bluetooth | Reference distance to the same target |
| USB–TTL | UART between FPGA and PC, 115200 8N1, 3.3 V levels |
| USB-Blaster | Load and verify the FPGA / EPCS4 image |
| PC and dedicated Bluetooth USB adapter | Application, logs, calculations and distance-meter communication |
| Target on a tripod | Manual distance changes with stops |

Photographs of the [board, optics and power supply](../hardware/photos/README.en.md), [schematics and BOM](../hardware/README.en.md). The external SA612 path is not fully represented by the main schematic. Optical history and replacement part numbers were supplied by the author; they were not inferred from the main-board PDF.

## Channel connections

The latest analogue series used the following mapping:

| Oscilloscope | Connector | Signal | Comparison |
|---|---|---|---|
| CH1 | X9 | Reference HF | CH3−CH1 |
| CH2 | X10 | Reference LF | CH4−CH2 |
| CH3 | X11 | Reflected HF | CH3−CH1 |
| CH4 | X12 | Reflected LF | CH4−CH2 |

X17–X20 in the corresponding order were previously used to observe the digital path. Record probe changes in a new session: CH1–CH4 labels alone do not identify whether a signal is analogue or digital.

Current DDS CH0/CH2 form the LF pair; CH1/CH3 form the HF pair. Do not confuse them with oscilloscope or ADC input numbers. Exact FTWs and amplitudes are in the [profile](../app/profiles/dds/default.json). LF IF is 4000.030458 Hz, HF IF is 6749.993190 Hz; the nominal AD9959 clock is 500 MHz.

## How the latest series was recorded

1. The author positioned the target and confirmed it was stationary.
2. After settling, distance-meter and FPGA responses were recorded. The latest series used a 3 s settling time, at least 15 s recording and at least six distance-meter responses. Selection criteria are in the [report](../measurements/2026-11-03/README.en.md).
3. Two oscilloscope screens were saved: CH1+CH3 and CH2+CH4. Distance was then checked again with the distance meter.
4. The instruction to move the target was given only after the point was complete. “No room to move” ended the series.

This is a separate verification series. Automatic calibration in the application has a different criterion: **three identical distance-meter responses** and suitable fresh phases. It sounds a confirmation when adding a point. These three responses mean neither three synchronised samples of all instruments nor the criterion for the latest long recording.

The distance meter and oscilloscope have their own clocks and delays. They were compared while the target was stationary. The FPGA synchronises its ADCs; this does not synchronise external instruments to the FPGA. Motion requires a separate measurement-time investigation.

## What is saved

A series benefits from the firmware version/hash, read-back DDS bank, probe mapping, oscilloscope settings, request and response timestamps, original UART packets, distance-meter readings and errors. Compact results include means, spread, validity flags, formulas and labelled screenshots; they do not replace the raw recording.

This package contains FPGA and Vector60 clients, the application and saved waveforms. The author's RIGOL automatic-capture scripts and full raw sessions are not included. Repeating the experiment on another bench requires a suitable SCPI/VISA client or saving screens with the oscilloscope itself.

The application and scripts do not move the target. An external motion controller decides what a real mechanism should do if validity is lost.

## The next scale of testing

So far, testing has used a small room. Checking 100–200 m will require a long space, new reference distances and tests of repeatability, drift and behaviour during movement. The enclosure is intended for subsequent equipment trials; IP68 test results have not yet been provided.
