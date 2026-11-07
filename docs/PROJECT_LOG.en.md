# Project log for continued work

[Русский](PROJECT_LOG.md) | **English**

This is a compact history of the standalone package. Detailed conversations
and complete primary sessions remain with the author; the important data,
decisions and limitations are collected here and in the
[AI handoff](AI_HANDOFF.en.md).

## 1–3 November 2026, Samara (UTC+4): phase meters and bench work

Synchronous reading of eight ADCs, analogue-phase calculation, the digital
phase meter, validity checks and measurement requests over UART were added
in stages. Oscilloscope signals, FPGA replies and Vector60 distances were
compared while the target was moved manually with stops. Distance-meter
latencies were investigated separately.

The application gained port configuration, plots, calibration-point
recording and DDS controls. In protocol v3, the DDS bank is applied in
one update, and phase meters operate at different IFs. FIR was removed
after no noticeable improvement according to the author's observations.
Frequency/amplitude selection at 1642 mm produced the current profile
around 4/6.75 kHz. The cause of rare phase jumps remains unproven.

## 3 November 2026, Samara (UTC+4): cal2 and an independent series

Cal2 contains 21 points over 638–5583 mm. Calculation from unwrapped HF
phase using a normalised fourth-degree polynomial was selected; LF chooses
the cycle. A separate check then covered ten distances from 762 to 5635 mm
without coefficient fitting. Excel, two oscilloscope captures per point,
means, spread and diagnostics were saved.

For the nine points inside the model domain, RMS discrepancy against
Vector60 was 13.36/13.16 mm. The last point is outside cal2; a latched
digital flag, diagnostics=4, was recorded. Its cause is unknown, and
errors and failed attempts are preserved.
[Full series report](../measurements/2026-11-03/README.en.md).

## 3 November 2026, 22:13 Samara (UTC+4): portable package

Application 0.5.1, the current Quartus project, schematics, photographs
and the latest series were prepared. Personal COM/MAC values were removed
from the copy's defaults, adapter VID:PID selection and standalone
instructions were added. Working bench sources and the original series
were unchanged.

A clean installation, relocation to a path containing spaces and demo
launch were checked. 63 application tests, 22 protocol tests and 9 HDL
suites passed. A verification Quartus compile produced a POF matching
the bench image; min slack +0.137 ns, unconstrained 0.
[Report](build-verification.en.md). The board was not programmed at this stage.

## 3 November 2026, Samara (UTC+4): history, AI workflow and licences

At the author's request, the main README was written as a project overview
for GitHub and a future website. The LE-200 PROFIBUS restoration story,
bench description, experiment map, gallery and links to FerroDSP and
PropValve-RE06MT were added. The author clarified the PIN photodiode type:
BPX65. IP68 and 100–200 m were identified as future verification goals,
not completed test results.

AGENTS.md, START_WITH_AI.md, AI_HANDOFF.md and this log were created.
The guide explains what to read, where code resides and how to leave
context for the next AI. Following the licences of existing repositories,
MIT and CERN-OHL-P-2.0 were added; scope is described in NOTICE.md,
and source versions are pinned by Git blob SHA.

224 internal links, 20 website catalogue paths and checksums of 187 package
files (excluding the root manifest itself) were checked. Full licence
texts matched the FerroDSP files read by Git blob SHA byte for byte.
Application, RTL, firmware, photographs and historical measurements were
unchanged; neither rebuilding nor a new hardware experiment was performed.
The next step was the author's publication instruction or a selected
technical experiment.

## 3 November 2026, Samara (UTC+4): first GitHub release

The author created [LaserRangefinder](https://github.com/neuroandriyanov/LaserRangefinder)
and requested uploading and merging the package. A separate branch from
the initial main was prepared for publication; the initial README remains
in Git history. The standalone package contents move directly into the
root, without an extra wrapper folder or the author's working archives.

The exact file list, SHA256, links and agreement between Git blobs and
local files are checked. Code builds and tests refer to the saved version
in build-verification.md; the change at this stage is material publication.
The merge result and exact SHAs are recorded in pull-request history.

## 7 November 2026, Samara (UTC+4): English documentation

At the owner's request, complete English versions of the documents, link
catalogue, captions for all 20 oscilloscope SVGs and a separate English
Excel workbook were added. Russian originals remain the source;
the [translation workflow](TRANSLATIONS.en.md) and `translations.json`
allow immediate Russian publication and detect outdated translations
using SHA-256. Current documents now include language links.

Original historical-series files, including both READMEs, Excel, SVG, PNG,
numerical JSON and its manifest.json, remain unchanged. English files are
adjacent additions. The original root manifest is preserved as
[pre-english-2026-11-07.json](manifests/pre-english-2026-11-07.json).
The root manifest.json was deliberately updated for language navigation,
new translations, instructions and verification tools; it does not replace
the measurement manifest.

All 338 numerical input cells in the English workbook were checked, along
with equality of calculation formulas after changing only text and sheet
names. An error-formula dependency test passed, with the original input
restored afterwards. Mean, RMS and maximum absolute error match the source
calculations; the final point remains `n/a` with the FPGA flag. Both sheets
and the chart were rendered and checked. Internal links, series hashes
and unchanged embedded PNGs in all SVGs were verified.

All nine PDF pages were visually reviewed: their labels and designations
are already English or Latin. Visible BOM headers are English too. These
original files are shared, with an additional [reading guide](../hardware/schematics/labels.en.md).
The application, HDL, firmware and hardware were not changed; there was
no rebuild, new measurement or board programming. This entry records
translation preparation; check Git history for publication and commits.
