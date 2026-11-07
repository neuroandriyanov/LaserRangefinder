# Materials for website links

[Русский](website-links.md) · **English**

All paths are relative to the root of this directory. Machine-readable catalogue: [site-links.en.json](../site-links.en.json). Links are relative, so the future GitHub repository address and website domain are not hard-coded into documents.

Once a repository is selected, use its ordinary file/directory URL for browsing and GitHub's raw-file URL for downloads. Encode spaces and Cyrillic characters per URL segment (for example, space → `%20`). For reproducible publications, pin a commit/tag rather than a mutable branch. `measurements/2026-11-03/` is the permanent address of this particular series; add new series beside it rather than overwriting historical material.

| Material | Path |
|---|---|
| Application | `app/README.en.md` |
| Quartus project | `fpga/DistanceSensorFpga_v0.qpf` |
| FPGA build | `fpga/README.en.md` |
| Main schematic | `hardware/schematics/main.pdf` |
| Power supply | `hardware/schematics/power.pdf` |
| Bill of materials | `hardware/schematics/bom.xlsx` |
| Board, optics and power-supply photos | `hardware/photos/README.en.md` |
| Latest series | `measurements/2026-11-03/README.en.md` |
| Measurement workbook | `measurements/2026-11-03/Стендовые измерения.en.xlsx` |
| Waveforms | `measurements/2026-11-03/Осциллограммы/README.en.md` |
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

SVG screenshots have an external caption with distance and channel pair; native PNGs are stored beside them. The website can link to SVG or PNG without another screenshot or changes to the measurement traces. PDF schematics and XLSX workbooks are separate files. Board photographs are full resolution, so a website page can display them at reduced width and link to the original.

The project page can use the main README sections: history, AI collaboration, measurements and other projects. Detailed articles have their own permanent paths; measurement material remains in its dated directory.
