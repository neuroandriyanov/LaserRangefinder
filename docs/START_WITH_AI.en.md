# Getting started with the project and AI

[Русский](START_WITH_AI.md) | **English**

You can start without a board or measuring instruments. The folder already contains
photographs, schematics, source code, tests and recorded measurements. An agent
with local-file access can recover the context and help with your chosen task.

## 1. Open the complete project

Download or copy the complete package and open its root folder in the environment
where your AI agent works. The root should contain `AGENTS.md`, `README.md` and
the `app`, `fpga`, `hardware`, `measurements` and `docs` folders. Instruction paths
are relative to this root. Giving the agent only one Verilog file is insufficient
to understand connections, clocks, the protocol and limitations.

Not all agents read AGENTS.md automatically, so name it explicitly in your first
message. The English version is AGENTS.en.md. If your assistant cannot access folders,
provide these documents and the relevant source files using your environment's
available method.

## 2. Give the first task

You can copy this text:

```text
We are working on LaserRangefinder. First read AGENTS.en.md, README.en.md,
docs/AI_HANDOFF.en.md and docs/START_WITH_AI.en.md. Then study the file map
and the documents relevant to my task.

Briefly explain the signal path, what is already implemented and verified,
which limitations remain and where the source data is stored.
Distinguish real measurements from simulations and hypotheses.
For now, study only: do not change files or instrument settings.
```

This is a convenient first step, not a required ceremony before every task.
Once the agent is familiar with the project, give it a specific assignment and
the appropriate degree of autonomy.

## 3. Choose a small task

| Interest | Example assignment |
|---|---|
| Desktop application | “Start demo mode using app/README.en.md, study UART v3 reading and show where validity is displayed.” |
| Mathematics | “Plot phase against distance from the latest series. Do not refit cal2 coefficients; compare with the saved result.” |
| FPGA | “Trace ADC → phase_demod → phase_lsq → CORDIC and the variable-IF test. Explain why amplitude scaling should not change ideal phase.” |
| Diagnostics | “Study digital_phase_meter and digital_phase_bridge. Propose a test for the source of bit2; do not claim the cause is proven before testing.” |
| Documentation | “Check whether the schematics, connection table and instructions are sufficient to start on another PC.” |

Installation, launch and test commands are in [app/README.en.md](../app/README.en.md)
and [fpga/README.en.md](../fpga/README.en.md). To check the original package without
instruments:

```powershell
python tools/verify_bundle.py
```

Run the command from the root; it compares hashes with manifest.json. After a
deliberate edit, a file will naturally no longer match: save a new manifest version
with a log entry, rather than concealing the change.

## 4. If you have your own bench

First show the agent the [bench description](stand.en.md), your wiring diagram,
FPGA model, actual COM port, instruments and experiment task. Addresses from the
author's bench are unnecessary: the application is designed to select your devices.

Before changing DDS settings, save the read-back bank and check the calibration
match. Changing frequency changes the analogue path's contribution; previous
coefficients cannot automatically be assumed suitable. The package includes FPGA
and Vector60 clients. A different distance meter or oscilloscope requires a
compatible interface of your own; no universal driver is provided here.

Example of an authorised series:

```text
Record the initial point with the target stationary. After recording, offer
two replies: “Moved, target is stationary” and “No room to move, finish”.
Record the next point after confirmation. Save the distance-meter reading,
FPGA data, two oscilloscope screenshots, settings and errors.
At the end, prepare a table and a short report.
```

Agree on exact wiring and record-acceptance criteria before the series. The
distance meter, oscilloscope and FPGA have different latencies: matching PC
receipt times alone does not make their measurements synchronous.

## 5. Leave context for the next agent

A useful final assignment is:

```text
Update docs/AI_HANDOFF.md and its English translation, and add an entry
to docs/PROJECT_LOG.md and its English translation.
State what changed, how it was checked, where the results are and what comes next.
If instruments were used, record settings and the state in which they were left.
Preserve original measurements and failed attempts without substituting results.
```

This allows the project to continue in a new chat with another assistant. Clear
data and decisions matter more than preserving the entire conversation: the next
participant should see what is known, what supports it and what remains unresolved.
