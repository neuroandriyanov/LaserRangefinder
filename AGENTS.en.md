# For an AI assistant continuing LaserRangefinder

[Русский](AGENTS.md) · **English**

This is a standalone project package. Documentation is published in Russian first and translated into English afterwards; see [the translation workflow](docs/TRANSLATION.en.md). The desktop interface is currently Russian; source comments may be English.

## What to read

1. [README.md](README.en.md) — concept, history, photographs and navigation.
2. [docs/AI_HANDOFF.md](docs/AI_HANDOFF.en.md) — current implementation, confirmed results and open questions. A short entry point for a new conversation.
3. [docs/START_WITH_AI.md](docs/START_WITH_AI.en.md) — getting started and example tasks.
4. [docs/PROJECT_LOG.md](docs/PROJECT_LOG.en.md) — decisions and milestone history.

Read additional material relevant to the task:

| Task | Sources |
|---|---|
| Architecture and connections | [Architecture](docs/architecture.en.md), [bench](docs/stand.en.md), [schematics](hardware/README.en.md) |
| HDL / pins / clocks | [FPGA](fpga/README.en.md), QSF and phase.sdc in fpga/, [UART v3](docs/protocol-v3.en.md) |
| Desktop application | [app/README.md](app/README.en.md), app/desktop_app/ and app/tools/ |
| Distance and calibration | app/desktop_app/distance.py, calibration.py, [experiments](docs/experiments.en.md) |
| Comparing results | [Latest series](measurements/2026-11-03/README.en.md), its calibration.json, measurements.json, Excel and manifest.json |
| Known limitations | [known-limitations.md](docs/known-limitations.en.md), [build checks](docs/build-verification.en.md) |
| Publication / rights | [NOTICE.md](NOTICE.en.md), [website links](docs/website-links.en.md) |

## Where to work

- Application: `app/desktop_app/`; instrument clients: `app/tools/`.
- Current HDL, QSF/QPF/SDC and ROM: `fpga/`; tests: `fpga/tb/`.
- Verified image: `fpga/releases/2026-11-03/`; do not replace it with a new build.
- Save new primary records in a separate `captures/` session and compact results in a new `measurements/` directory. Do not rewrite the historical series.
- `docs/verification/` contains results from a particular verification. After code changes they do not automatically verify the new version.

All paths here are relative to the package root. Do not assume access to the author's working folder, an old HDL archive, COM9, a particular MAC address or local packages. Users select ports and addresses. Demonstration data must not be presented as actual measurements.

## Easy-to-confuse details

- DDS CH0/CH2 are LF; CH1/CH3 are HF. DDS and ADC input numbering differ.
- X9/X11 are the HF pair; X10/X12 are the LF pair. Phase difference is reflected minus reference: channel 3−1 and channel 4−2. Check the actual bench wiring.
- ADC1–4 receive sine waves; ADC5–8 receive detector outputs. For the latter, use **voltage magnitude**, with |U| ≥0.5 V on every channel.
- The analogue algorithm is least squares/CORDIC without FIR. IF is approximately 1–20 kHz.
- The DDS bank is applied by one COMMIT/IO_UPDATE. Do not update channels with separate pulses during a measurement window.
- Distance is currently calculated by the PC; the FPGA does not calculate distance or velocity.
- `diagnostics=4` latches digital overflow. `valid=1` does not erase this event history; the cause of the last observation remains unestablished.

Inspect schematic PDFs visually: text extraction does not prove connectivity. Check pins against QSF and `pin-lock.json`, not photo labels. The external SA612 section is not fully represented by the main schematic.

## Checks

From `app/`, after installing dependencies:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s desktop_app -t . -p "test*.py"
```

From `fpga/`: `python tools/test_phase_hdl.py`; after HDL changes also run a full Quartus compile and timing review according to the [guide](fpga/README.en.md). Protocol tests use UART files produced by HDL simulation:

```powershell
# From app/, after HDL tests:
.\.venv\Scripts\python.exe -m unittest discover -s tools -p "test*.py"
```

For text changes, check links and the integrity of immutable materials; an FPGA rebuild is unnecessary. Running `python tools/verify_bundle.py` from the root checks the saved manifest, not new-code correctness. Before updating the root manifest, preserve the previous version and explain the change in the log. Historical measurement manifests remain unchanged.

## Real instruments

Follow the user's task. Reading files is not an instruction to change DDS, flash a board or start polling. If an experiment has already been assigned, perform authorised steps without asking again about every request; clarify missing connections and limits. Do not assume another bench is in the state of the author's bench.

Record a stationary point first, then ask for movement and wait for confirmation that the target has stopped. “No room to move” ends the series. Retain primary data, communication errors and settings. The author's automatic oscilloscope capture system is not included in this package; do not assume such a driver exists in `app/tools/`.

## Passing on context

After a substantive stage, update `docs/AI_HANDOFF.md` and add an entry to `docs/PROJECT_LOG.md`: date and timezone, task, changes, checks, data links, limitations and next step. After hardware work, record actual settings, firmware hash and the final instrument state.

Distinguish the author's account, implementation, simulation, measurements and hypotheses. A successful build is not a board write; stability is not accuracy; room-scale calibration does not confirm 200 m or IP68. Failed experiments are useful too: retain them and explain what did not work.

Original materials are licensed under MIT and CERN-OHL-P-2.0 as described in [NOTICE.md](NOTICE.en.md). Preserve third-party notices. Preparing files does not imply publication or push; those are separate actions requested by the owner.
