# Hardware schematics and photographs

[Русский](README.md) | **English**

[Captioned gallery](photos/README.en.md) · [Restoration story](../docs/project-story.en.md) ·
[Bench equipment and connections](../docs/stand.en.md)

| Material | File |
|---|---|
| Main electrical schematic | [main.pdf](schematics/main.pdf) · [English label guide](schematics/labels.en.md) |
| Power schematic | [power.pdf](schematics/power.pdf) · [English label guide](schematics/labels.en.md) |
| Bill of materials | [bom.xlsx](schematics/bom.xlsx) |
| Rangefinder photographs | [01](photos/rangefinder-01.jpg), [02](photos/rangefinder-02.jpg), [03](photos/rangefinder-03.jpg), [04](photos/rangefinder-04.jpg), [05](photos/rangefinder-05.jpg), [06](photos/rangefinder-06.jpg) |
| Power-supply photographs | [01](photos/power-supply-01.jpg), [02](photos/power-supply-02.jpg) |

Original files were copied from the owner's materials without changing
their content; names were normalised for stable links. Full-size JPEGs
are preserved without re-encoding. Author information in photo metadata
is retained; no GPS coordinates were found in EXIF.

The main schematic does not include the external section with four SA612
mixers. The description of photodiode connections is based on the owner's
confirmation and bench checks. This is a schematic/BOM package, not a
complete manufacturing package: editable CAD/PCB files and Gerbers are
absent from this folder.

| Connector | Signal in the latest series |
|---|---|
| X9 / RIGOL CH1 | HF reference after the mixer |
| X10 / CH2 | LF reference after the mixer |
| X11 / CH3 | HF reflected after the mixer |
| X12 / CH4 | LF reflected after the mixer |
| X17–X20 | Corresponding digital signals after comparators |
| X5 | UART to USB–TTL, 3.3 V, 115200 8N1 |

Differences are reflected minus reference: CH3−CH1, CH4−CH2.
Analogue input numbers do not match DDS output numbers.
FPGA pins are defined by the verified [QSF](../fpga/DistanceSensorFpga_v0.qsf).
