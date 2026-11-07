# Materials for links from a website

[Русский](website-links.md) | **English**

All paths are relative to the root of this folder. Machine-readable catalogue:
[site-links.json](../site-links.json). Links are relative, so a future GitHub
repository address or website domain is not hardcoded into the documents.
The English catalogue is [site-links.en.json](../site-links.en.json).

After choosing a repository, use its ordinary file/directory link for viewing
and the raw-file URL supplied by GitHub for downloading. Encode spaces and
Cyrillic characters per URL segment (for example, a space becomes `%20`).
For reproducible publications, pin a commit/tag rather than a mutable branch.
`measurements/2026-11-03/` is the permanent address of this particular series;
add new series alongside it without overwriting historical materials.

| Material | Path |
|---|---|
| Application | `app/README.en.md` |
| Quartus project | `fpga/DistanceSensorFpga_v0.qpf` |
| FPGA build | `fpga/README.en.md` |
| Main schematic | `hardware/schematics/main.pdf` |
| Power supply | `hardware/schematics/power.pdf` |
| English schematic label guide | `hardware/schematics/labels.en.md` |
| Bill of materials | `hardware/schematics/bom.xlsx` |
| Board, optics and power photos | `hardware/photos/README.en.md` |
| Latest series | `measurements/2026-11-03/README.en.md` |
| Measurement workbook | `measurements/2026-11-03/Bench measurements.en.xlsx` |
| Oscilloscope captures | `measurements/2026-11-03/Осциллограммы/README.en.md` |
| UART v3 | `docs/protocol-v3.en.md` |
| Verification | `docs/build-verification.en.md` |
| Project overview | `README.en.md` |
| Project story | `docs/project-story.en.md` |
| Bench | `docs/stand.en.md` |
| Experiments | `docs/experiments.en.md` |
| Getting started with AI | `docs/START_WITH_AI.en.md` |
| AI instructions | `AGENTS.en.md` |
| Current status | `docs/AI_HANDOFF.en.md` |
| Licences | `NOTICE.en.md` |

SVG captures have an external distance and channel-pair caption; native
PNGs are stored alongside them. A website can link to SVG or PNG without
taking another screenshot or changing measurement traces. English SVG
derivatives translate only the surrounding caption. Schematic PDFs and
XLSX workbooks are available as separate files. Board photographs are
full-size, so a website can display them smaller and link to the original.

The main README sections can be used for a project page: history, work
with AI, measurements and other projects. Detailed articles have their
own permanent paths; measurement materials remain in their dated folder.
