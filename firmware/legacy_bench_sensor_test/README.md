# Legacy Single-Sensor Bench Test (Historical Reference)

`legacy_bench_sensor_test.ino` is a standalone sensor test program used on November 9, 2026, before integration with the complete firmware.

Originally located in `Arduino/motor_sensor_lab/`, it has since been incorporated into this project.

The program prints a human-readable report to the Serial Monitor once per second.

### Sensor Configuration

- **MaxSonar:** PW (pulse-width) output → D2. Takes 10 samples per second and reports the median.
- **Sharp GP2Y0A02:** Connected to A1. Uses lookup-table interpolation and averaging.
- **Omron D3C Microswitch:** Connected to D4 (COM → GND, internal pull-up enabled, 20 ms debounce).

## ⚠️ Pin Assignments Differ from the Final Wiring

| Component | Legacy Bench Test | Final Wiring ([hardware/WIRING.md](../../hardware/WIRING.md)) |
|---|---|---|
| MaxSonar | PW → D2 | **AN → A2** |
| D3C Microswitch | D4 | **A4** |
| D2 / D4 | Sensor inputs | Encoder channel A / DC motor driver direction pin |

### Important Safety Warning

**Do not upload this program when the complete hardware configuration is connected, especially when motor drivers are connected and the bench power supply is turned on.**

This legacy program does not control motor pins such as D5 and D7. As a result, motor driver inputs may remain floating, potentially causing unintended behavior.

**Only use this program for isolated bench testing with the three sensors connected on a breadboard.**

## Current Firmware Recommendation

The production firmware already provides raw sensor measurements through the `RAW` serial frame.

Sensor data can be collected directly using:

`calibration/capture.py`

Therefore, this legacy test program is generally no longer required for normal operation, calibration, or integration testing.
