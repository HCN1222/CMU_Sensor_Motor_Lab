# Test Report (2026-11-09)

This report records only the actual results for **this** code (protocol v2). For records of older versions see [legacy_results/](legacy_results/README.md).

Conclusions fall into four categories that cannot substitute for one another:

- **Actually run and passed**: really executed in the environments listed below, and passed.
- **Passed in software model**: real control code + **synthetic** motor/sensor models. Proves the logic and signs are correct, not physical performance.
- **Not run**: not executed this time.
- **Needs physical parameters**: can only be completed after the team measures the hardware.

## Environment

| | Windows 11 | Linux (WSL2 Ubuntu 22.04) |
|---|---|---|
| Python | 3.11.18 (conda `sensorMotorLab`) | 3.10.12 (system) |
| ROS 2 | Humble (RoboStack conda packages) | Humble (apt, `/opt/ros/humble`) |
| Qt binding | python_qt_binding → PyQt5 | python_qt_binding → PyQt5 |
| C++ | conda-forge GCC 16.2.0 (mingw-w64) | GCC 11.4.0 |
| Arduino | arduino-cli 1.5.1, arduino:avr 1.8.8, Servo 1.3.0 | (AVR not compiled on Linux) |

Reproduce: `conda activate sensorMotorLab && python tools/run_tests.py --ros` (native Linux ROS: first `source /opt/ros/humble/setup.bash`, then run `python3 tools/run_tests.py --ros --no-avr`).

## Results

| Check | Windows | Linux | Category |
|---|---|---|---|
| Generated `hardware_controller.ino` matches the three source files (`--check`) | ✅ | ✅ | Actually run and passed |
| Uno AVR compile: Flash 21 030 B (65%), RAM 1 202 B (58%), no warnings in project code | ✅ | Not run | Actually run and passed |
| **125** C++ control-core behavior checks (`-Wall -Wextra -Werror -pedantic`) | ✅ | ✅ | Logic: actually run and passed; PID/closed-loop parts: passed in software model |
| Python ↔ C++ firmware end-to-end (real SerialLink + real core and frame formatting + synthetic motor) | ✅ | ✅ | Passed in software model |
| 29 Python protocol/link/bridge unit tests | ✅ 28 + 1 skipped (PTY is POSIX only) | ✅ 29 (including a real pyserial pseudo-terminal) | Actually run and passed |
| Offscreen Qt panel test (real python_qt_binding widgets) | ✅ | ✅ | Actually run and passed (synthetic data) |
| 8 offline tests of calibration analysis + `capture.py` | ✅ | ✅ | Actually run and passed (synthetic data) |
| **11 ROS 2 graph checks**: real rclpy bridge node, DDS topics, TRANSIENT_LOCAL `/lab/config`, heartbeat lease, ARM/SERVO executed via `/lab/command`, out-of-range commands rejected at the bridge, heartbeat loss → STOP | ✅ | ✅ | Actually run and passed; the other end of the serial port is the C++ firmware simulator |
| `colcon build`, `ros2 pkg executables`, rqt plugin discovery (`rqt --list-plugins`) | ✅ | ✅ | Actually run and passed |
| `ros2 launch sensor_motor_lab lab.launch.py`: bridge node + rqt panel (offscreen) both join the ROS graph | ✅ | ✅ | Actually run and passed (no Uno connected) |
| Upload new firmware to a real Uno, ROS over USB with the hardware | Not run | Not run | Next step |
| Sensor calibration, measured error, PID tuning, servo endpoints, encoder CPR/direction | — | — | **Needs physical parameters** |
| Motors powered, mechanical motion, power supply and wiring | — | — | **Needs physical parameters** |

## C++ core check coverage

- **Hardware config**: `hardware_config.h` passes the self-consistency check; safety switches ship turned off; no subsystem is marked as calibrated; the IR table spans 20–150 cm with hysteresis inside the range; potentiometer angle is not assumed.
- **Conversion**: GP2Y0A02 table endpoints and interpolation; too close → `-2`, no target → `-1`; ultrasonic 1.27 cm/ADC, 6-inch saturation, disconnection; potentiometer ADC endpoints and angle.
- **Filtering**: IR moving average reduces alternating noise; invalid samples clear the filter instead of keeping old values; ultrasonic median rejects 3/9 outliers.
- **Commands**: rejection of bad format / non-finite values / injection; sequence-number deduplication and wraparound; configured motion limits; ZERO only usable while disarmed.
- **Sensor mode**: DC does not start before the filter window is full; 35/45 cm hysteresis in both directions; too close and no target both count as stop; a new interruption triggers once, holding does not repeat, and interruptions while the stepper is busy are counted as ignored; button debounce, holding does not repeat the toggle.
- **Stepper**: full-step rounding, positive and negative directions, rejection while busy, STOP and mode switch cancel remaining steps, configurable pulse interval.
- **Protection**: watchdog (including millis wraparound), encoder stall, **reversed encoder direction** (PID runaway when feedback is reversed), DC_MOVE timeout; re-ARM clears the fault.
- **Encoder**: sign applies to angle and RPM; RAW counts are unaffected by CPR/sign/ZERO.
- **Frame format**: STATE/RAW/CONFIG/ACK field counts; fixed-point rounding, no `-0.00`, never outputs nan; the longest STATE line under extreme values still fits the firmware's 192-byte buffer; on overflow an empty line is emitted instead of a truncated frame.
- **Closed loop (synthetic model)**: both generic gains and the `hardware_config.h` gains (encoder sign −1) settle at ±30 RPM and complete ±90° relative moves. **This does not mean the physical PID has been tuned.**

## Known limitations

- The encoder uses the Uno's internal pull-ups; signal quality must be checked on hardware.
- The GP2Y0A02 output folds back within about 15 cm, which a single ADC value cannot distinguish.
- When the telemetry send queue is full, telemetry frames are dropped and reported via `INFO,TELEMETRY_DROPPED`. At the current bandwidth (about 2 kB/s, versus about 11.5 kB/s available at 115200 baud) this should not happen, but it still needs to be observed on hardware.
- WSL cannot see Windows COM ports and needs usbipd-win. Running directly in the Windows conda environment does not need it.
