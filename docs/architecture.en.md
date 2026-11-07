# Architecture and data flow

[Русский](architecture.md) · **English**

Two modulation frequencies are summed in the laser path. The reference PIN photodiode receives part of the emitted light through an optical fibre; the measurement photodiode receives the target reflection. Four external SA612 mixers combine the two received signals with two local oscillators. The measurement inputs receive two reference and two reflected IF sine waves.

```mermaid
flowchart TD
    PC[Desktop application] <-->|UART v3| FPGA[FPGA Cyclone IV]
    FPGA -->|SPI and common IO_UPDATE| DDS[AD9959: four outputs]
    DDS --> TX[Two laser modulation frequencies]
    TX --> REF[Reference PIN through fibre]
    TX --> TARGET[Target]
    TARGET --> RX[Measurement PIN]
    DDS -->|Two local oscillators| MIX[Four SA612 mixers]
    REF --> MIX
    RX --> MIX
    MIX --> ADC[Four ADC channels: sine waves]
    MIX --> COMP[Four comparators]
    DET[Four detector outputs] --> ADC8[ADC5–8]
    ADC --> FPGA
    COMP --> FPGA
    ADC8 --> FPGA
    V60[Vector60] -->|Bluetooth, separate clock| PC
```

The FPGA samples the ADCs synchronously and calculates both analogue phase differences. Least squares estimates the sine, cosine and DC components at the known IF; CORDIC returns phase and amplitude. A separate digital path averages edge phases. IFs and expected digital periods are updated from the same accepted DDS bank. During retuning, data are marked invalid; afterwards the windows are accumulated again.

The application matches stationary intervals to the distance meter and constructs the calibration. Coarse LF phase selects the HF cycle; the fine component comes from HF phase with an experimental correction. Cal2 uses a degree-4 polynomial. Oscilloscope screenshots, distance-meter readings and FPGA packets have different acquisition times: these three instruments have no shared hardware synchronisation.
