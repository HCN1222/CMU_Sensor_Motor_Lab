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

## Sensor Calibration — 2026-11-12

Calibration rows were recorded with `calibration/capture.py` on 2026-11-10 (reference distances by tape, angles by protractor). Results: `python calibration/analyze.py --input calibration --output calibration/results_20261112 --filter-reference 50`. Summary tables and figures: [calibration/result_figure](../calibration/result_figure/calibration_summary.md).

### IR Rangefinder (Sharp GP2Y0A02YK)

Converted distance uses the vendor typical table currently in `firmware/hardware_config.h`; the team calibration table has not been applied. 46 samples per point.

| Reference (cm) | Mean ADC | ADC std | Converted (cm) | Error (cm) | Error (%) |
|---:|---:|---:|---:|---:|---:|
| 30 | 450.35 | 13.79 | 24.07 | −5.9 | −19.8% |
| 50 | 278.98 | 15.04 | 41.89 | −8.1 | −16.2% |
| 80 | 179.33 | 15.17 | 70.43 | −9.6 | −12.0% |
| 100 | 144.46 | 15.56 | 87.47 | −12.5 | −12.5% |
| 110 | 132.20 | 15.39 | 94.19 | −15.8 | −14.4% |

The vendor table reads 6–16 cm short over 30–110 cm. [Transfer function](../calibration/results_20261112/ir_transfer.svg). Suggested table: [hardware_config_suggestion.txt](../calibration/results_20261112/hardware_config_suggestion.txt).

### IR Filter (5-sample moving average)

Stationary target at 50 cm, 167 frames over 18.4 s.

| | Mean error (cm) | Std (cm) |
|---|---:|---:|
| Raw | −3.84 | 2.34 |
| Filtered | −3.85 | 1.08 |

Filtering reduces the standard deviation by about 2.2×; the mean offset comes from the vendor table and is not removed by filtering. [Raw vs. filtered plot](../calibration/results_20261112/ir_filter.svg).

### Ultrasonic Rangefinder (LV-MaxSonar-EZ)

Converted distance uses the firmware's 1.27 cm/ADC. Validation rows (stationary flat board) were recorded before the calibration rows (larger flat board).

| Split | Reference (cm) | Mean ADC | ADC std | Converted (cm) | Error (cm) |
|---|---:|---:|---:|---:|---:|
| validation | 50 | 32.13 | 12.82 | 45.55 | −4.45 |
| validation | 80 | 46.67 | 19.70 | 63.94 | −16.06 |
| validation | 100 | 49.42 | 27.54 | 60.19 | −39.81 |
| calibration | 30 | 27.70 | 12.63 | 31.67 | +1.67 |
| calibration | 50 | 34.59 | 11.81 | 44.86 | −5.14 |
| calibration | 80 | 53.04 | 21.25 | 60.88 | −19.12 |
| calibration | 100 | 44.37 | 22.94 | 58.72 | −41.28 |
| calibration | 100 | 45.54 | 21.12 | 56.46 | −43.54 |

Validation error (n = 3, 50–100 cm): mean −20.1 cm, MAE 20.1 cm, RMSE 24.9 cm, max 39.8 cm. The ADC at 80 cm is higher than at 100 cm and the ADC spread grows with distance, consistent with echoes from nearby objects during the setup. [Transfer function](../calibration/results_20261112/sonar_transfer.svg), [validation error](../calibration/results_20261112/sonar_error.svg).

### Potentiometer

Angle converted offline from the measured ADC with the firmware's linear formula (`POT_ADC_MIN` = 6.46, `POT_ADC_MAX` = 629.30, travel 180°).

| Reference | Mean ADC | ADC std | Converted angle | Error |
|---:|---:|---:|---:|---:|
| 0° | 6.46 | 5.79 | 0.0° | 0.0° |
| 90° | 272.02 | 3.07 | 76.7° | −13.3° |
| 180° | 629.30 | 1.04 | 180.0° | 0.0° |
