# LaserRangefinder application 0.5.1

[Русский](README.md) · **English**

The application has a Russian interface: FPGA measurements, plots, Vector60, calibration recording, distance from analogue phases, configuration of four DDS channels and readback of the actual bank. Sources are in `desktop_app/`; protocol and distance-meter clients are in `tools/`.

## Installation and launch

The verified environment is Windows, Python 3.14 x64 with Tcl/Tk. Dependencies require Python ≥3.12; other OS and Python versions were not verified for this package. Install Python separately from the [official downloads](https://www.python.org/downloads/windows/). Quartus, an oscilloscope and a distance meter are not needed for the demonstration.

From this directory:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
.\Run.cmd --demo
```

If Python is not in PATH, supply your interpreter path: `powershell -ExecutionPolicy Bypass -File install.ps1 -Python "D:/Python/python.exe"`. The installer creates a local `.venv` without changing system Python packages. Equivalent manual commands:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m desktop_app --demo
```

For a board, launch `Run.cmd` without `--demo`. Select your port in “Настройки” (Settings). The USB–TTL interface must use 3.3 V levels; electrical RS-232 ±12 V must not be connected directly to X5. The default format is 115200, 8N1. The 10 ms request period is a target: actual speed is limited by the 112-byte response and sequential communication. The port is not opened automatically when the application starts.

## Settings, data and DDS

Settings are saved in `%LOCALAPPDATA%/LaserRangefinder/settings.json`, in the current user's profile. For an isolated run, pass `--settings path/settings.json` and `--capture-dir path/logs`. The demo uses separate settings. A `captures/` directory is created when recording; logs contain primary data and are not automatically added to Git.

The COM port and distance-meter address are empty on first launch. Periods, timeouts, plots and the editable DDS profile are saved. The profile with exact FTWs is [default.json](profiles/dds/default.json), matching the FPGA startup values:

| Output | Frequency, MHz | ASF | Phase |
|---|---:|---:|---:|
| CH0 — LF laser | 1.495361328125 | 200 | 0° |
| CH1 — HF local oscillator | 74.027135735378 | 1000 | 0° |
| CH2 — LF local oscillator | 1.499361358583 | 1000 | 0° |
| CH3 — HF laser | 74.020385742188 | 450 | 0° |

LF IF is 4000.030458 Hz; HF IF is 6749.993190 Hz. IF fields on the DDS tab are read-only. “Отправить в FPGA” (Send to FPGA) validates values, sends the bank and performs a single COMMIT, then reads the bank back. Saving on the PC alone does not change the board. After reset, the FPGA returns to hardware defaults. The profile was selected on one bench at 1642 mm; it is not a universal optimum.

## Vector60 distance meter

This is optional. Install its dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-vector60.txt
```

A dedicated Bluetooth USB adapter with WinUSB and the Bumble stack is used. ASUS USB-BT400, VID:PID `0B05:1D70`, was tested; other adapters were not. Ordinary pairing through Windows Bluetooth is insufficient for this backend. Configure the driver separately using the [Bumble Windows documentation](https://google.github.io/bumble/platforms/windows.html). Use a dedicated adapter: WinUSB does not replace the system Bluetooth stack for keyboards and other devices. The application does not install drivers itself. The experimental UsbDk backend was removed.

Scan after configuring the adapter:

```powershell
.\.venv\Scripts\python.exe tools/vector60_winusb.py scan --usb-transport usb:0B05:1D70
```

Enter the discovered Bluetooth address in application settings; change USB VID:PID if necessary. Enable the distance-meter connection and start polling separately. Requests do not overlap; the default timeout is 3 s, after which the cycle restarts. Distance and an X axis in mm are available in the plot.

## Calibration

A stationary point is accepted after **three identical distance-meter readings**, provided suitable fresh phases are available. A sound confirms the recording. Repeated points at the same distance are not added. The calculation button saves the model; applying it checks data provenance and DDS-bank compatibility. Another board's cal2 is not activated automatically.

The sample cal2 is included for reproducing analysis and tests, not as a universal calibration for all units. LF selects the HF cycle; a fourth-degree polynomial calculates distance from the unwrapped HF phase. No result is returned outside the verified range. Changing frequencies or the analogue path requires a new calibration.

## Tests without instruments

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s desktop_app -t . -p "test*.py"
```

The full suite requires `requirements-vector60.txt` and working Tcl/Tk. Tests use temporary settings and simulated devices rather than COM/Bluetooth. Protocol tests in `tools/` additionally require [HDL simulation](../fpga/README.en.md#simulation) to have been run first:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tools -p "test*.py"
```

Top-level dependencies are pinned in requirements. A full package list for the verified environment is in the [snapshot](../docs/verification/python-packages.txt).
