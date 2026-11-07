# From a faulty rangefinder to a research bench

[Русский](project-story.md) | **English**

This project began with a desire to understand phase-based distance measurement
on a real optical signal path. It required a design that allowed an oscilloscope
to be connected, frequencies and amplitudes to be changed, ADC samples to be
obtained and different phase calculation methods to be compared.

## A second life for the optics

The donor was a faulty **LE-200 PROFIBUS**. According to the author, its original
boards were damaged beyond repair. The new design reused the optical system
with its lens and collimator, and the receiver assembly with SA612 mixers.

The faulty PIN photodiodes were replaced with **BPX65** devices; the author
confirmed that marking separately. The laser diode also needed replacement:
a **QL67D7SA** was fitted, selected for red light around **670 nm**. This replacement
history is the author's account; no spectral measurement was performed in the
published experiments.

![Restored optical assembly, side view](../hardware/photos/rangefinder-03.jpg)

*Optical assembly and its mounting. [Original photograph](../hardware/photos/rangefinder-03.jpg).*

## New electronics for observation and experiments

After restoring the optics, an enclosure was selected and a custom board designed.
Debugging received particular attention: connection points allow observation of
the four analogue signals after the mixers and the corresponding comparator
signals. A single change can thus be followed both on the oscilloscope screen
and in the FPGA numbers.

The AD9959 generates two modulation frequencies and two local oscillators. The
FPGA controls the DDS, reads eight ADCs synchronously and measures phases using
analogue and digital methods. The desktop application configures parameters
and saves results.

![Custom board in the enclosure with the receiver assembly](../hardware/photos/rangefinder-05.jpg)

The enclosure was selected with IP68 protection in mind, for later trials on
equipment under operating conditions. This is a design goal: the package does
not yet contain a separate protection-rating test report for the assembled
rangefinder.

## Human and AI collaboration

Sergey restored, designed and assembled the hardware. He defined the device's
purpose, clarified real connections, connected instruments and moved the target.
AI helped interpret documents and code, work out processing, write Verilog,
and prepare the desktop application, tests and measurement scripts.

The work proceeded through small, verifiable stages. First DDS control, then
synchronous ADC reading and analogue phases, the digital phase meter, COM
requests, frequency and amplitude selection, calibration and a separate
verification series. Settings, source data and build results were saved
between changes.

In experiments with the manual target, the agent recorded a point and issued
the next request. Sergey moved the target, confirmed it had stopped and waited
for recording to finish. The distance meter provided a distance reference,
the oscilloscope showed waveforms, and UART allowed comparison with the FPGA
calculations.

Some approaches were unsuccessful. FIR before phase calculation did not produce
a noticeable improvement according to the author's observations, so it is absent
from the current version. Rare jumps and the digital-overflow flag remain under
investigation; code review and a successful build alone do not establish their cause.

## Why preserve this openly

We want to share the development process: the bench, measurements, checked
decisions and unanswered questions. This package helps the next participant
start from a working foundation and contribute their experience; it also lets
them pass context to their AI through documents rather than retelling the
entire history.

Only a small room is currently available, so the latest series ends at 5635 mm.
Full verification of the intended 100–200 m range requires a long site, such
as a corridor around 200 m long, and a new measurement series. Room-scale
results are not currently extrapolated to that distance.

[Bench equipment](stand.en.md) · [Experiments](experiments.en.md) ·
[Continuing with AI](START_WITH_AI.en.md)

*The hardware history was recorded on 3 November 2026 from the author's account.
The description of current code and results is based on project sources and
saved verification records.*
