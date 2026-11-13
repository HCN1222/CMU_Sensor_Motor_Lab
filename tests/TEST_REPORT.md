# Test Report

Each area adds its own checks here as the work lands. Record only what was actually run.

Every result belongs to exactly one of four categories, which cannot substitute for one another:

- **Actually run and passed**: really executed in an environment listed below, and passed.
- **Passed in software model**: real control code + **synthetic** motor/sensor models. Proves the logic and signs are correct, not physical performance.
- **Not run**: not executed.
- **Needs physical parameters**: can only be completed after the team measures the hardware.

## Environment

| | Windows 11 | Linux (WSL2 Ubuntu 22.04) |
|---|---|---|
| Python | 3.11.18 (conda `sensorMotorLab`) | 3.10.12 (system) |
| ROS 2 | Humble (RoboStack conda packages) | Humble (apt, `/opt/ros/humble`) |
| Qt binding | python_qt_binding → PyQt5 | python_qt_binding → PyQt5 |
| C++ | | |
| Arduino | | |

## Results

| Check | Windows | Linux | Category |
|---|---|---|---|
| Offscreen Qt panel test, `tests/python/dashboard_smoke.py` (real python_qt_binding widgets) | ✅ | ✅ | Actually run and passed (synthetic data) |
| `colcon build`, `ros2 pkg executables`, rqt plugin discovery (`rqt --list-plugins`) | ✅ | ✅ | Actually run and passed |
| `ros2 launch sensor_motor_lab lab.launch.py`, `tests/ros/launch_smoke.py`: bridge node + rqt panel (offscreen) both join the ROS graph | ✅ | ✅ | Actually run and passed (no Uno connected) |
| ROS bridge over USB with a real Uno | Not run | Not run | Next step |

ROS rows were run on 2026-11-09. Reproduce on Windows: `conda activate sensorMotorLab`, build and source `ros2_ws` (see [ros2_ws/README.md](../ros2_ws/README.md)), then run `python tests/ros/launch_smoke.py` and, from the repository root, `PYTHONPATH=ros2_ws/src/sensor_motor_lab python tests/python/dashboard_smoke.py`. On Linux with native ROS, first `source /opt/ros/humble/setup.bash`.

## Known limitations

- WSL cannot see Windows COM ports and needs usbipd-win to reach the Uno. Running the bridge directly in the Windows conda environment does not need it.

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
