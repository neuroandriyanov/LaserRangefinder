# LaserRangefinder application 0.5.1

[Русский](README.md) | **English**

Russian-language interface: FPGA measurements, plots, Vector60, calibration
recording, distance from analogue phases, four-channel DDS configuration
and readback of the actual bank. Source is in `desktop_app/`; protocol
and distance-meter clients are in `tools/`. This guide translates the
instructions; the downloadable application's interface remains Russian.

## Installation and launch

Verified environment: Windows, Python 3.14 x64 with Tcl/Tk. Dependencies require
Python ≥3.12; other OS and Python versions were not tested for this package.
Install Python separately: [official downloads](https://www.python.org/downloads/windows/).
The application needs neither Quartus, an oscilloscope nor a distance meter
to show its demo.

From this directory:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
.\Run.cmd --demo
```

If Python is not on PATH, supply your interpreter path:
`powershell -ExecutionPolicy Bypass -File install.ps1 -Python "D:/Python/python.exe"`.
The installer creates a local `.venv` and does not change system Python
packages. Equivalent manual commands:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m desktop_app --demo
```

For a board, start `Run.cmd` without `--demo`.
Choose your port under “Настройки” (Settings). USB–TTL must use 3.3 V levels;
electrical RS-232 ±12 V must not be connected directly to X5.
Default format: 115200, 8N1. The 10 ms request interval is a target;
actual throughput is limited by the 112-byte reply and sequential exchange.
The port does not open automatically when the application starts.

## Settings, data and DDS

Settings are saved in `%LOCALAPPDATA%/LaserRangefinder/settings.json`, in the
current user's profile. For an isolated launch, pass
`--settings path/settings.json` and `--capture-dir path/logs`.
Demo mode uses separate settings. The `captures/` folder is created when
recording; logs contain primary data and are not included in Git automatically.

The COM port and distance-meter address are initially empty. Periods,
timeouts, plots and the editable DDS profile are saved. Exact-FTW profile:
[default.json](profiles/dds/default.json). It matches the FPGA startup values:

| Output | Frequency, MHz | ASF | Phase |
|---|---:|---:|---:|
| CH0 — LF laser | 1.495361328125 | 200 | 0° |
| CH1 — HF local oscillator | 74.027135735378 | 1000 | 0° |
| CH2 — LF local oscillator | 1.499361358583 | 1000 | 0° |
| CH3 — HF laser | 74.020385742188 | 450 | 0° |

LF IF: 4000.030458 Hz; HF IF: 6749.993190 Hz. IF fields on the DDS tab
are read-only. “Отправить в FPGA” (Send to FPGA) validates values, sends
the bank and performs a common COMMIT, then reads the bank back.
Saving on the PC does not itself change the board. After reset, the FPGA
returns to hardware defaults. The profile was selected on one bench at
1642 mm; it is not a universal optimum.

## Vector60 distance meter

This is optional. Install its dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-vector60.txt
```

A separate Bluetooth USB adapter with WinUSB and the Bumble stack is used.
ASUS USB-BT400, VID:PID `0B05:1D70`, was tested; other adapters were not.
Ordinary Windows Bluetooth pairing is insufficient for this backend.
Configure the driver separately following the
[Bumble Windows documentation](https://google.github.io/bumble/platforms/windows.html).
Use a dedicated adapter: WinUSB does not replace the system Bluetooth
stack for keyboards and other devices. The application does not install
drivers itself. The experimental UsbDk backend has been excluded.

Scan after configuring the adapter:

```powershell
.\.venv\Scripts\python.exe tools/vector60_winusb.py scan --usb-transport usb:0B05:1D70
```

Enter the discovered Bluetooth address in application settings; change
the USB VID:PID if necessary. Enable the distance-meter connection and
start polling separately. Requests do not overlap; the default timeout
is 3 s, after which the cycle restarts. Distance and an X axis in mm
are available in the plot.

## Calibration

A stationary point is accepted after **three identical distance-meter
readings**, with suitable fresh phases available. A beep confirms recording.
The same distance is not added twice. The calculation button saves the
model; data provenance and DDS-bank agreement are checked before applying it.
Someone else's cal2 is not activated automatically on another board.

The cal2 example is included to reproduce analysis and tests, not as a
general calibration for all specimens. LF selects the HF cycle;
a fourth-degree polynomial calculates distance from unwrapped HF phase.
No result is reported outside the verified range. Changing frequencies
or the analogue path requires a new calibration.

## Checks without instruments

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s desktop_app -t . -p "test*.py"
```

The full suite requires `requirements-vector60.txt` and working Tcl/Tk.
Tests use temporary settings and simulated devices, not COM/Bluetooth.
Protocol tests in `tools/` additionally require prior
[HDL simulation](../fpga/README.en.md#simulation):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tools -p "test*.py"
```

Top-level dependencies are pinned in requirements. Complete package list
for the verified environment:
[snapshot](../docs/verification/python-packages.txt).
