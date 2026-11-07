# Getting started with the project and an AI assistant

[Русский](START_WITH_AI.md) · **English**

You can start without a board or measurement instruments. The directory already contains photographs, schematics, source code, tests and recorded measurements. An agent with access to local files can recover the context and help with your chosen task.

## 1. Open the whole project

Download or copy the complete package and open its root directory in the environment used by your AI agent. The root should contain `AGENTS.md`, `README.md` and the `app`, `fpga`, `hardware`, `measurements` and `docs` folders. Instruction paths are relative to this location. Giving the agent a single Verilog file is insufficient to understand connections, clocks, protocol and limitations.

Not every agent reads AGENTS.md automatically, so name it explicitly in your first message. If your assistant cannot access folders, provide these documents and the necessary sources through a method available in your environment.

## 2. Give the first task

You can copy this text:

```text
We are working on LaserRangefinder. First read AGENTS.en.md, README.en.md,
docs/AI_HANDOFF.en.md and docs/START_WITH_AI.en.md. Then examine the file map
and documentation relevant to my task.

Briefly explain the signal path, what is implemented and verified,
which limitations remain, and where the primary data are stored.
Distinguish actual measurements from simulations and hypotheses.
For now, study only: do not change files or instrument settings.
```

This is a useful first step, not a required ritual before every task. Once the agent is familiar with the project, give it a specific task and the appropriate degree of autonomy.

## 3. Choose a small task

| Interest | Example task |
|---|---|
| Desktop application | “Run the demo according to app/README.en.md, examine UART v3 reading and show where validity is displayed” |
| Mathematics | “Plot phase against distance from the latest series. Do not refit cal2 coefficients; compare with the saved result” |
| FPGA | “Explain the ADC → phase_demod → phase_lsq → CORDIC path and variable-IF test. Explain why amplitude scaling should not change ideal phase” |
| Diagnostics | “Study digital_phase_meter and digital_phase_bridge. Propose a test to locate bit2; do not claim a proven cause before testing” |
| Documentation | “Check whether schematics, the connection table and instructions suffice for starting on another PC” |

Installation, launch and test commands are in [app/README.md](../app/README.en.md) and [fpga/README.md](../fpga/README.en.md). Check the original package without instruments:

```powershell
python tools/verify_bundle.py
```

Run this from the root to compare hashes with manifest.json. A deliberately edited file will naturally stop matching; this calls for a new manifest version with a log entry rather than concealment of the change.

## 4. If you have your own bench

First show the agent the [bench description](stand.en.md), your wiring diagram, FPGA model, actual COM port, instruments and experiment task. Addresses from the author's bench are unnecessary: the application lets you select your own devices.

Before retuning DDS, save the read-back bank and check calibration compatibility. Changing frequency changes the analogue-path contribution; previous coefficients cannot automatically be considered suitable. FPGA and Vector60 clients are included. Controlling another distance meter or oscilloscope requires a compatible interface of your own; there is no ready-made universal driver here.

Example of an agreed series:

```text
Record the initial point with a stationary target. After recording,
offer two responses: “Moved; target is stationary” and
“No room to move; finish”. Take the next point only after confirmation.
Save distance-meter readings, FPGA data, two oscilloscope screenshots,
settings and errors. At completion, prepare a table and short report.
```

Agree exact connections and record-acceptance criteria before the series. The distance meter, oscilloscope and FPGA have different delays: matching PC reception times alone does not make measurements synchronous.

## 5. Leave context for the next agent

A useful final task is:

```text
Update docs/AI_HANDOFF.md and add an entry to docs/PROJECT_LOG.md.
State what changed, how it was checked, where results are stored and what comes next.
If instruments were used, record their settings and final state.
Retain original measurements and unsuccessful attempts without substitution.
```

This allows work to continue in a new conversation and with another assistant. Clear data and decisions matter more than the entire conversation: the next participant needs to see what is known, its evidence and what remains open.
