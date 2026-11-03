"""Compile and run self-checking HDL tests. Never connects to hardware."""
import argparse
import os
import json
from pathlib import Path
import re
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iverilog", type=Path)
    parser.add_argument("--only", nargs="*", help="Run selected suites")
    args = parser.parse_args()
    compiler = args.iverilog or os.environ.get("IVERILOG") or shutil.which("iverilog")
    if not compiler:
        raise SystemExit("Install Icarus Verilog and add it to PATH, or pass --iverilog PATH")
    compiler = Path(compiler).resolve()
    runner = compiler.with_name("vvp.exe" if compiler.suffix == ".exe" else "vvp")
    project = root
    (project / 'test-results').mkdir(exist_ok=True)
    expected_pins = json.loads((project / "pin-lock.json").read_text())
    actual_pins = dict(re.findall(r"set_location_assignment (PIN_\d+) -to (\S+)",
                                (project / "DistanceSensorFpga_v0.qsf").read_text()))
    if actual_pins != expected_pins:
        raise RuntimeError("Pin locations differ from the verified board mapping")
    results = {"pin_locations_unchanged": len(expected_pins), "tests": {}}
    for name, sources in {
        "adc": ["ads8681_bank.sv"],
        "phase": ["phase_demod.sv", "phase_lsq.sv", "cordic_atan.sv"],
        "variable_phase": ["phase_demod.sv", "phase_lsq.sv", "cordic_atan.sv"],
        "variable_digital": ["digital_phase_meter.sv"],
        "config": ["dds_settings.sv", "dds_programmer.sv", "phase_link.sv", "uart_phy.sv"],
        "digital": ["digital_phase_meter.sv"],
        "bridge": ["digital_phase_bridge.sv"],
        "link": ["phase_link.sv", "uart_phy.sv"],
        "top": ["tb/tb_adc.sv", "DistanceSensorFpga_v0.sv", "dds_settings.sv",
                "dds_programmer.sv", "phase_clock.sv", "ads8681_bank.sv", "phase_demod.sv",
                "cordic_atan.sv", "phase_lsq.sv", "phase_link.sv", "uart_phy.sv",
                "digital_phase_meter.sv", "digital_phase_bridge.sv"],
    }.items():
        if args.only and name not in args.only:
            continue
        output = f"test-results/{name}.vvp"
        top = f"tb_{name}"
        options = []
        command = [str(compiler), "-g2012", "-DSIMULATION", *options, "-s", top, "-o", output,
                   f"tb/{top}.sv", *sources]
        build = subprocess.run(command, cwd=project, text=True, capture_output=True, timeout=60)
        (project / f"test-results/{name}-compile.log").write_text(build.stdout + build.stderr)
        build.check_returncode()
        run = subprocess.run([str(runner), output], cwd=project, text=True, capture_output=True, timeout=240)
        (project / f"test-results/{name}.log").write_text(run.stdout + run.stderr)
        print(run.stdout, end="", flush=True)
        run.check_returncode()
        if "PASS" not in run.stdout:
            raise RuntimeError(f"{name} did not complete assertions")
        results["tests"][name] = "PASS"
    (project / "test-results/simulation-summary.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"Verified {len(expected_pins)} pin locations; selected HDL tests PASS")


if __name__ == "__main__":
    main()
