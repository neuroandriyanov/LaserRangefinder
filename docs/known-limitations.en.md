# Confirmed limitations

[Русский](known-limitations.md) · **English**

- The enclosure was selected with IP68 in mind; the package contains no protection-rating test report for the assembled device.
- Actual indoor measurements extend to 5635 mm. Cal2 covers 638–5583 mm; extending the result to 100–200 m has not been verified.
- Distance on the main tab is calculated by the PC. The FPGA sends phases, amplitudes, raw codes, frequencies and statuses; there is no hardware distance/velocity calculation.
- The final bench point contains `diagnostics=4`: latched bit2 for digital-capture/CDC overflow. The cause remains unknown. Current valid flags can recover while this diagnostic bit persists until reset.
- For a point outside the model, Excel displays “n/a”. Losses and interference are not replaced by interpolated values presented as measurements.
- Independence of the phase algorithm from amplitude scaling was checked by simulation. Real errors remain possible with weak signals, distortion, saturation and channel crosstalk.
- A complete request and response at 115200 8N1 takes at least 10.764 ms; 1000 or even a sustained 100 full responses/s are unattainable at that baud rate.
- The application and WinUSB backend were tested on Windows. A configurable VID:PID does not imply verified compatibility with every Bluetooth adapter.
- The DDS profile was selected on one board at 1642 mm. Saving it does not replace setup and calibration of another unit.
- The FPGA uses 98% of logic elements, leaving little room for new functions.
- This publication build was not written to the board again. The bench series refers to a separately saved, verified POF.
