# Test Report

Each area adds its own checks here as the work lands. Record only what was actually run.

Every result belongs to exactly one of four categories, which cannot substitute for one another:

- **Actually run and passed**: really executed in an environment listed below, and passed.
- **Passed in software model**: real control code + **synthetic** motor/sensor models. Proves the logic and signs are correct, not physical performance.
- **Not run**: not executed.
- **Needs physical parameters**: can only be completed after the team measures the hardware.

## Environment

| | Windows 11 | Linux (Ubuntu 22.04) |
|---|---|---|
| Python | | |
| ROS 2 | | |
| Qt binding | | |
| C++ | | |
| Arduino | | |

## Results

| Check | Windows | Linux | Category |
|---|---|---|---|

## Known limitations

None recorded yet.

## D Update — 2026-11-12

These software checks were run on the supplied sensor_motor_lab.zip project bundle. They have not been rerun on this repository branch; its firmware, protocol and ROS dependencies are still being integrated.

### Software Integration

| Check | Result | Detail |
|---|---|---|
| Generated Uno sketch matches sources | PASS | `firmware/generate_sketches.py --check` |
| C++ controller test compilation | PASS | Test executable compiled |
| C++ controller behaviour | FAIL | `tests/firmware/test_controller.cpp:40` expects `hardwareVerified == false`; current configuration is `true` |
| C++ host simulator compilation | PASS | Host executable compiled |
| Python ↔ C++ E2E | PASS | `tests/python/firmware_bridge_e2e.py`; 42 STATE frames; synthetic inputs |
| ROS graph check | NOT RERUN | `rclpy` unavailable in the audit environment |
| Full test suite | PENDING RERUN | Update configuration-dependent tests with C, then rerun in the project environment |

E2E covers CONFIG limits, ARM, servo, DC speed/position, stepper rounding, STOP, ZERO, sensor mode, RAW telemetry and watchdog behaviour. It runs through the host simulator without physical Uno or ROS hardware integration.

### Slot Sensor Measurements

Source: [slot.csv](../calibration/slot.csv). Both trials used slow beam breaks.

| Recorded time | Reference count | Detected count | Error |
|---|---:|---:|---:|
| 2026-11-10 18:57 | 10 | 11 | +1 |
| 2026-11-10 18:58 | 10 | 10 | 0 |

One trial overcounted by one event. [Slot error plot](../calibration/results_20261111/slot_error.svg).

### Pending Physical Records

| Test | Record to add |
|---|---|
| Slot repeatability | Actual and detected counts for repeated trials |
| Slot → stepper | New obstruction, sustained obstruction and obstruction while busy |
| Stepper direction and angle | Target and measured angle, direction and completion; include +90° and −90° |
| Arduino ↔ ROS | GUI control, physical mode switch and sensor-driven operation |
| STOP during motion | DC/stepper response and restart behaviour |

No physical stepper measurements or completed Uno/ROS integration records were supplied for this update.
