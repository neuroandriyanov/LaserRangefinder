# For AI assistants continuing LaserRangefinder

[Русский](AGENTS.md) | **English**

This is a standalone project package. Russian is the source language of
documentation, with adjacent `.en.md` English translations. The desktop
interface remains Russian; code comments may be English.

## What to read

1. [README.en.md](README.en.md) — idea, history, photographs and navigation.
2. [docs/AI_HANDOFF.en.md](docs/AI_HANDOFF.en.md) — current implementation,
   confirmed results and open questions. A short entry point for a new chat.
3. [docs/START_WITH_AI.en.md](docs/START_WITH_AI.en.md) — getting started and example tasks.
4. [docs/PROJECT_LOG.en.md](docs/PROJECT_LOG.en.md) — decisions and stage history.

Read these additional sources as the task requires:

| Task | Sources |
|---|---|
| Architecture and connections | [Architecture](docs/architecture.en.md), [bench](docs/stand.en.md), [schematics](hardware/README.en.md) |
| HDL / pins / clocks | [FPGA](fpga/README.en.md), QSF and phase.sdc in fpga/, [UART v3](docs/protocol-v3.en.md) |
| Desktop application | [app/README.en.md](app/README.en.md), app/desktop_app/ and app/tools/ |
| Distance and calibration | app/desktop_app/distance.py, calibration.py, [experiments](docs/experiments.en.md) |
| Result comparison | [Latest series](measurements/2026-11-03/README.en.md), its calibration.json, measurements.json, Excel and manifest.json |
| Known limitations | [known-limitations.en.md](docs/known-limitations.en.md), [build verification](docs/build-verification.en.md) |
| Publication / rights | [NOTICE.en.md](NOTICE.en.md), [website links](docs/website-links.en.md) |

## Where to work

- Application: `app/desktop_app/`; device clients: `app/tools/`.
- Current HDL, QSF/QPF/SDC and ROM: `fpga/`; tests: `fpga/tb/`.
- Verified image: `fpga/releases/2026-11-03/`; do not replace it with a new build.
- Save new primary recordings in a separate `captures/` session, and compact
  results in a new `measurements/` folder. Do not rewrite a historical series.
- `docs/verification/` contains results of a particular check; changing code
  does not automatically make them verification of the new version.

All paths here are relative to this package's root. Do not assume the author's
working folder, an old HDL archive, COM9, a particular MAC or local packages
are available. The user selects ports and addresses. Demo data must not be
presented as real measurements.

## Common sources of confusion

- DDS CH0/CH2 are LF, CH1/CH3 are HF. DDS and ADC input numbering differ.
- X9/X11 are the HF pair, X10/X12 the LF pair; phase is reflected minus
  reference: channel 3−1 and channel 4−2. Check the actual bench connections.
- ADC1–4 receive sine waves; ADC5–8 receive detector outputs. The latter
  use **voltage magnitude**, with |U| ≥0.5 V required on every channel.
- The analogue algorithm is least-squares/CORDIC without FIR. IF is
  approximately 1–20 kHz.
- The DDS bank is applied with one COMMIT/IO_UPDATE. Do not update channels
  with separate pulses during a measurement window.
- Distance is currently calculated by the PC; the FPGA has no distance/speed calculation.
- `diagnostics=4` latches digital overflow. `valid=1` does not erase the
  history of that event; the cause of the latest observation is unknown.

Review schematic PDFs visually: text extraction does not prove connections.
Check pins against QSF and `pin-lock.json`, not photograph labels.
The external SA612 section is not fully represented in the main schematic.

## Checks

From `app/`, after installing dependencies:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s desktop_app -t . -p "test*.py"
```

From `fpga/`: `python tools/test_phase_hdl.py`; after HDL changes also run
a full Quartus compile and check timing using the [guide](fpga/README.en.md).
Protocol tests use UART files produced by HDL simulation:

```powershell
# From app/, after HDL tests:
.\.venv\Scripts\python.exe -m unittest discover -s tools -p "test*.py"
```

For text edits, check links and the integrity of immutable materials;
an FPGA rebuild is unnecessary. `python tools/verify_bundle.py` from the root
checks the saved manifest, not new code correctness. Before updating the
root manifest, preserve its previous version and describe the change in
the log. Historical measurement manifests remain unchanged.

## Real instruments

Follow the user's assignment. Reading files does not instruct you to change
DDS, reprogram the board or start polling. If an experiment has already been
authorised, perform the agreed actions without asking again about every
request; clarify missing connections and limits. Do not assume another
specimen is in the same state as the author's bench.

First record a stationary point, then request movement and wait for
confirmation that it has stopped. “No room to move” ends the series.
Preserve source data, communication errors and settings. Automatic
oscilloscope capture from the author's bench is not part of this package;
do not assume such a driver is present in `app/tools/`.

## Passing on context

After a substantive stage, update `docs/AI_HANDOFF.md` and add an entry
to `docs/PROJECT_LOG.md`: date and timezone, task, changes, checks,
data links, limitations and next step. Update the English translations
after the Russian originals. After hardware work, state the actual
settings, firmware hash and the state in which instruments were left.

Separate the author's account, implementation, simulation, measurements
and hypotheses. A successful build is not board programming; stability
is not accuracy; room-temperature calibration does not confirm 200 m
or IP68. Failed experiments are useful too: preserve them and explain
what did not work.

Original-material licences are MIT and CERN-OHL-P-2.0 as described in
[NOTICE.en.md](NOTICE.en.md). Preserve third-party notices. File preparation
does not imply publication or push; that is a separate action at the
owner's request.
