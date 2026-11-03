"""Independent floating-point LS reference for the HDL's quantized ADC stimuli."""
from pathlib import Path
import json
import numpy as np


def main():
    root = Path(__file__).resolve().parents[1]
    steps = [(206158000, 206158000), (131072000, 81920000),
             (17180000, 343598000), (343598000, 17180000),
             (19018000, 65538000), (314574000, 17344000),
             (77778000, 222222000), (123456000, 234568000)]
    rows = np.loadtxt(root / "test-results/variable-phase.csv", delimiter=",")
    output = []
    for mode, end, h, l in rows:
        mode, end = int(mode), int(end)
        n = np.arange(end-1000, end)
        p = np.array([mode*23.13, mode*23.13+11.1, mode*23.13+179.8, mode*23.13+11.1-73.56])
        amplitudes = [180, 23000, 3500, 250] if mode % 2 == 0 else [4200, 210, 180, 17000]
        phases = []
        for ch in range(4):
            theta = 2*np.pi*steps[mode//2][ch % 2]*n/2**32
            dc = -6000 if ch % 2 else 24000
            x = np.floor(32768+dc+amplitudes[ch]*np.cos(theta+np.deg2rad(p[ch]))+.5)-32768
            design = np.column_stack([np.cos(theta), -np.sin(theta), np.ones(1000)])
            coef = np.linalg.lstsq(design, x, rcond=None)[0]
            phases.append(np.rad2deg(np.arctan2(coef[1], coef[0])))
        reference = (np.array([phases[2]-phases[0], phases[3]-phases[1]])+180) % 360-180
        error = (np.array([h, l])-reference+180) % 360-180
        output.append(dict(mode=mode, sample_index=end, hardware_phase_deg=[h, l],
                           floating_ls_phase_deg=reference.tolist(), difference_deg=error.tolist()))
    worst = max(abs(e) for row in output for e in row["difference_deg"])
    result = dict(windows=len(rows), max_hdl_vs_float_ls_deg=worst, results=output,
                  note="Simulation only; same rounded 16-bit samples, independent NumPy least squares.")
    path = root / "test-results/variable-phase-reference.json"
    path.write_text(json.dumps(result, indent=2)+"\n")
    if len(rows) != 80 or worst > .01:
        raise AssertionError(f"Reference mismatch: {len(rows)} windows, {worst:.9f} degrees")
    print(f"PASS independent float LS: {len(rows)} windows, max HDL difference {worst:.9f} deg")


if __name__ == "__main__":
    main()
