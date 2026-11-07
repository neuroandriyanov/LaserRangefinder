# Confirmed limitations

[Русский](known-limitations.md) | **English**

- The enclosure was selected with IP68 in mind; the package contains no
  protection-rating test report for the assembled device.
- Actual room-scale measurements extend to 5635 mm. Cal2 covers 638–5583 mm;
  extrapolation of the result to 100–200 m has not been verified.
- Distance on the main tab is calculated by the PC. The FPGA transmits phases,
  amplitudes, raw codes, frequencies and status flags; it does not calculate
  distance or speed in hardware.
- The last bench point contains `diagnostics=4`: latched bit2 for digital
  capture/CDC overflow. Its cause is unknown. Current valid flags can recover
  while this diagnostic bit remains set until reset.
- Excel displays “n/a” for a point outside the model. Missing or corrupted
  readings are not replaced with interpolation presented as measurement.
- Phase-algorithm independence from amplitude scaling has been tested by
  simulation. Real errors remain possible with low signal levels, distortion,
  saturation and channel crosstalk.
- Sending a full request and reply at 115200 8N1 takes at least 10.764 ms;
  neither 1000 nor even a sustained 100 full replies/s is possible at this rate.
- The application and WinUSB backend were tested on Windows. A configurable
  VID:PID does not establish compatibility with every Bluetooth adapter.
- The DDS profile was selected on a particular board at 1642 mm. Saving it does
  not replace configuration and calibration of another specimen.
- The FPGA uses 98% of its logic elements, leaving little room for new features.
- This publication build was not programmed into the board again. The bench
  series refers to a separately saved, verified POF.
