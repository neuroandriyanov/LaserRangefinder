# Reading the schematics and bill of materials

[Русский](labels.md) | **English**

All eight pages of [main.pdf](main.pdf) and the single page of
[power.pdf](power.pdf) were visually reviewed. Title-block fields, net names,
pin names and component designations are already in English or Latin
characters. No Russian explanatory labels requiring replacement inside
the drawings were found. The English edition therefore uses the original
PDFs, preserving connections, values and graphics. This is a reading guide,
not a new schematic revision.

Editable EDA sources are absent from this package. Automated text extraction
from these PDFs returns almost no content: review the drawings visually.
The numbers below are PDF page numbers; the Sheet fields in the title blocks
do not provide sequential numbering for the entire file.

| main.pdf page | Content visible on the sheet |
|---|---|
| 1 | X8 input, filtering and power regulators; nets +9V, +5V, +3.3V, +1.8v_ANALOG, +1.8v_DIGIT, +3_CLOCK, PD_OFFSET20V |
| 2 | AD9959, its clock source, four output paths with transformers and filters, control nets and X2 |
| 3 | EP4CE6E22 FPGA pins, configuration memory, external memory, connectors and ADC/DDS control signals |
| 4 | X1 input, analogue and digital power regulators, FPGA power pins |
| 5 | Analogue paths from X6: amplifiers, filter and detector stages, comparators; connections labelled analog out |
| 6 | Analogue paths from X7, amplifiers, detectors, comparators; test points X9–X21 |
| 7 | ADS8681 devices for ADC1–4, ADCPORT interfaces, reference and supply circuits, indicators |
| 8 | ADS8681 devices for ADC5–8, ADCPORT interfaces, reference and supply circuits, indicators |

The power.pdf page shows the transformer, bridge rectifiers, smoothing
capacitors, regulators and output connector X1. In/Out/Gnd mean input,
output and ground. Net names and values remain exactly as in the source;
they are not verification of voltages measured on the assembled bench.

| Label or abbreviation | Meaning |
|---|---|
| GND | Ground |
| IN / OUT | Input / output |
| EN, RESET, CS, SCLK, SDI, SDO | Pin-function names; active levels and requirements are defined by the component documentation |
| analog out | Analogue-signal group name |
| ADCPORT | ADC-interface signal group name |
| DDS | Direct digital synthesizer |
| ADC | Analogue-to-digital converter |
| RevNo / Revision note | Revision number / description |
| Itemref / Quantity | Item reference / quantity |
| Title/Name, designation, material, dimension | Name, designation, material and dimensions |
| Article No./Reference | Part number / reference |
| Designed by / Checked by / Approved by – date | Designer / checker / approver and date |
| File name / Date / Scale / Edition / Sheet | File name / date / drawing scale / edition / sheet |

[bom.xlsx](bom.xlsx) also already has English headers: N is the item number,
RefDes the reference designators, Value the component value, Name the name,
Pcs the quantity, Price the unit price and SumPrice the total. Component
rows, values, formulas and formatting are unchanged. The word “Листы”
(Worksheets) in Excel's internal metadata is not a heading or table datum.

The mapping of X9/X11 to the high-frequency pair and X10/X12 to the
low-frequency pair is confirmed by the [bench description](../../docs/stand.en.md).
The external section containing four SA612 mixers is not fully represented
in the main schematic. Net labels in a drawing do not replace verification
of connections, the QSF and `pin-lock.json`.
