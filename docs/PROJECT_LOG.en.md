# Project log for continued work

[Русский](PROJECT_LOG.md) · **English**

This is a compact history of the standalone package. Detailed conversations and full primary sessions remain with the author; important data, decisions and limitations are collected here and in the [AI handoff](AI_HANDOFF.en.md).

## 1–3 November 2026, Samara (UTC+4): phase meters and bench work

Synchronous reading of eight ADCs, analogue phase calculation, a digital phase meter, validity checks and UART measurement requests were added in stages. Oscilloscope signals, FPGA responses and Vector60 distances were compared while the target was moved manually with stops. Distance-meter delays were investigated separately.

The application gained port configuration, plots, calibration-point recording and DDS controls. In protocol v3, the DDS bank is applied in one update and phase meters work with different IFs. FIR was removed after the author observed no noticeable improvement. Frequency/amplitude selection at 1642 mm produced the current profile around 4/6.75 kHz. The cause of rare phase jumps remains unproven.

## 3 November 2026, Samara (UTC+4): cal2 and independent series

Cal2 contains 21 points over 638–5583 mm. A normalised fourth-degree polynomial was selected to calculate distance from the unwrapped HF phase; LF selects the cycle. An independent test then covered ten distances over 762–5635 mm without refitting coefficients. Excel, two waveforms per point, means, spread and diagnostics were retained.

For nine points inside the model domain, RMS difference from Vector60 was 13.36/13.16 mm. The final point was outside cal2; a latched digital flag diagnostics=4 was recorded. Its cause is unknown; errors and failed attempts were retained. [Full series report](../measurements/2026-11-03/README.en.md).

## 3 November 2026, 22:13 Samara (UTC+4): portable package

Application 0.5.1, the current Quartus project, schematics, photographs and latest series were prepared. Personal COM/MAC defaults were removed from the copy; adapter VID:PID selection and standalone instructions were added. The working bench sources and original series were not changed.

Clean installation, transfer to a path containing spaces and demo launch were verified. 63 application tests, 22 protocol tests and 9 HDL suites passed. A verification Quartus compile produced a POF matching the bench image; min slack +0.137 ns, unconstrained 0. [Report](build-verification.en.md). No board write was performed at this stage.

## 3 November 2026, Samara (UTC+4): story, AI collaboration and licences

At the author's request, the main README was developed into a project overview for GitHub and a future website. It added the LE-200 PROFIBUS restoration story, bench description, experiment map, gallery and links to FerroDSP and PropValve-RE06MT. The author clarified the PIN-photodiode part number: BPX65. IP68 and 100–200 m are identified as future verification goals, not completed-test results.

AGENTS.md, START_WITH_AI.md, AI_HANDOFF.md and this log were created. The handoff explains what to read, where the code is and how to preserve context for the next AI assistant. MIT and CERN-OHL-P-2.0 were added based on the existing repositories' licences; scope is in NOTICE.md and sources are recorded by Git blob SHA.

224 internal links, 20 website-catalogue paths and checksums of 187 package files (excluding the root manifest itself) were checked. Full licence texts matched the read FerroDSP files byte-for-byte by Git blob SHA. Application, RTL, firmware, photographs and historical measurements were unchanged; no rebuild or new hardware experiment was performed. The next step was the author's publication request or a selected technical experiment.

## 3 November 2026, Samara (UTC+4): first GitHub release

The author created [LaserRangefinder](https://github.com/neuroandriyanov/LaserRangefinder) and requested upload and merge of the package. A separate branch was prepared from the initial main; the original README is retained in Git history. The standalone package contents are placed in the repository root without an extra wrapper directory or the author's working archives.

The exact file list, SHA256, links and correspondence between Git blobs and local files are checked. Code builds and tests refer to the saved version in build-verification.md; this stage changes publication of the materials. The merge result and exact SHAs are recorded in pull-request history.

## 7 November 2026, Samara (UTC+4): Russian and English materials

Prepared parallel English documentation, translated caption layers for the oscilloscope gallery and English spreadsheet labels. Russian remains the primary publication language; translation source hashes are tracked in `i18n/manifest.json`. The workflow is described in [TRANSLATION.md](TRANSLATION.en.md).

Localisation retains primary recordings, calibration, hardware images, HDL and desktop program behaviour. The desktop program still uses a Russian interface. Link, translation-coverage and source-integrity checks apply to these documentation changes; the historical Quartus and hardware tests above were not rerun. No instruments were accessed, and this entry does not claim a push, merge or deployment.

Verification: 20 embedded oscilloscope PNGs are identical, 580 numeric workbook cells and 278 formula expressions preserve their values and logic; chart source ranges, cell styles and layout are retained. English text and the native chart were visually checked; a temporary phase-input change confirmed recalculation and was restored. Redundant backslashes before sheet-reference quotes in the original status formulas were removed in the English copy. Both schematic PDFs and the BOM already use English labels and are shared unchanged. Relative English-document links resolve.
