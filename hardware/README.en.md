# Hardware schematics and photographs

[Русский](README.md) · **English**

[Annotated gallery](photos/README.en.md) · [Restoration story](../docs/project-story.en.md) · [Bench equipment and connections](../docs/stand.en.md)

| Material | File |
|---|---|
| Main electrical schematic | [main.pdf](schematics/main.pdf) |
| Power-supply schematic | [power.pdf](schematics/power.pdf) |
| Bill of materials | [bom.xlsx](schematics/bom.xlsx) |
| Rangefinder photographs | [01](photos/rangefinder-01.jpg), [02](photos/rangefinder-02.jpg), [03](photos/rangefinder-03.jpg), [04](photos/rangefinder-04.jpg), [05](photos/rangefinder-05.jpg), [06](photos/rangefinder-06.jpg) |
| Power-supply photographs | [01](photos/power-supply-01.jpg), [02](photos/power-supply-02.jpg) |

Files were copied from the owner's materials without changing their content; names were normalised for stable links. Full-resolution JPEGs are retained without re-encoding. Author information in photo metadata is retained; no GPS coordinates were found in EXIF.

The main schematic does not include the external section with four SA612 devices. The description of their connection to the photodiodes is based on owner confirmation and bench checks. This is a set of schematics and a BOM, not a full manufacturing package: editable CAD/PCB files and Gerbers are absent from this directory.

| Connector | Signal in the latest series |
|---|---|
| X9 / RIGOL CH1 | Reference HF after mixer |
| X10 / CH2 | Reference LF after mixer |
| X11 / CH3 | Reflected HF after mixer |
| X12 / CH4 | Reflected LF after mixer |
| X17–X20 | Corresponding digital signals after comparators |
| X5 | UART to USB–TTL, 3.3 V, 115200 8N1 |

Differences are reflected minus reference: CH3−CH1, CH4−CH2. Analogue-input numbers differ from DDS-output numbers. FPGA pins are defined by the verified [QSF](../fpga/DistanceSensorFpga_v0.qsf).
