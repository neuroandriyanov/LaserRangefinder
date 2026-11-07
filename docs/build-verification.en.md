# Verification of the publication package

[Русский](build-verification.md) | **English**

3 November 2026, Samara (UTC+4). A standalone copy of application 0.5.1 and
the Quartus project was checked. Working bench sources were unchanged;
no instruments were accessed.

| Check | Result |
|---|---|
| Python 3.14 x64, new venv | requirements-vector60.txt installed, pip check passed |
| Installation after relocation | install.ps1, separate path with spaces, core dependencies only |
| Launch after relocation | Run.cmd --demo --close-after 3, exit code 0 |
| Application tests, including Tk | 63 / 63 |
| Protocol tests, including bytes from HDL | 22 / 22 |
| HDL simulation | 9 / 9 suites, Icarus Verilog |
| Pin assignments | 88 match the verified original project |
| NumPy least-squares check | 80 windows, maximum HDL difference 0.002427578° |
| Quartus Lite 25.1std, build 1129 | Full build successful |
| Logic / M9K / DSP18 / PLL | 6162/6272; 23/30; 5/15; 1/2 |
| Timing | 66 checks, minimum +0.137 ns; all TNS=0 |
| Unconstrained paths | 0 |
| Working-source preservation | 49 files unchanged |
| Original HDL archive | 131 files match baseline SHA256 |
| Latest measurement series | 59 files preserved byte for byte |

The new build's POF **matched byte for byte** the saved image used in
the latest bench series:
`7e652373ae74ca5d1734248706c16cae9fdaf9ef25b28a321869271220e0212d`.
The programmer was not run during this task. The Program+Verify used
on the bench refers to 20:31:09 on that day.

The build contains synthesis warnings, including width truncation,
unused signals and ROM inputs; these are not concealed. The verification
run had no errors or Critical Warnings. Warning review was not replaced
with a “warning-free build” claim; changing working HDL was outside
this stage's scope.

Details: [JSON summary](verification/summary.json),
[Quartus log](verification/quartus-build.txt),
[resources](verification/quartus-fit.txt), [timing](verification/quartus-timing.txt),
[unconstrained paths](verification/quartus-unconstrained.txt),
[application](verification/app-tests.txt), [protocol](verification/protocol-tests.txt),
[HDL](verification/hdl-tests.json), [least-squares check](verification/phase-reference.json),
[package versions](verification/python-packages.txt).

The demo and tests use simulated devices and do not establish hardware
accuracy. Live operation of a newly selected WinUSB adapter was not
tested here. The separate schematics/photos/measurements section was
not recalculated: original PDFs, XLSX, JPEGs, PNGs, SVGs and numerical
data were preserved.

The root `manifest.json` contains publication-file checksums. Verify with:

```powershell
python tools/verify_bundle.py
```

The manifest is unsigned and serves as an integrity check. Temporary
build databases, virtual environments and caches are excluded.
