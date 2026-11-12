# Four Sensors · Three Motors · Arduino Uno · ROS 2

Five-person Sensors & Motor Control assignment. A single Uno firmware handles 4 sensors and 3 kinds of motors at once; the PC side controls it through a ROS 2 serial bridge and an rqt panel.

| Mode | Behavior |
|---|---|
| GUI mode | The panel controls servo angle, DC signed RPM and relative angle (encoder closed loop), and bidirectional stepper relative angle |
| Sensor mode | Potentiometer → servo angle; Sharp IR distance → DC start/stop (with hysteresis); each new slot-sensor interruption → stepper turns 90° |
| Shown in both modes | All four sensors, the three motor states, mode, connection, ARM, calibration status; the ultrasonic sensor keeps ranging and is plotted |
| Physical switch | Each press of the micro switch toggles the mode (30 ms debounce, holding does not repeat) |

**Current status (2026-11-09)**: The software is complete and has actually been tested on Windows and Linux, including real ROS 2 nodes, topics, and the rqt plugin. The new firmware **has not yet been uploaded to the hardware**; all physical parameters are still placeholders or estimates, and the firmware refuses to ARM by default until the team verifies the wiring. See [tests/TEST_REPORT.md](tests/TEST_REPORT.md).

## Quick start

```bash
# 1. Environment (Windows / Linux / macOS)
conda env create -f environment.yml
conda activate sensorMotorLab
conda install -c conda-forge gxx_win-64      # Windows only, for the C++ tests; on Linux use cxx-compiler

# 2. Offline tests (no Uno required)
python tools/run_tests.py --ros

# 3. Firmware: edit firmware/hardware_config.h → generate → upload
python firmware/generate_sketches.py
arduino-cli compile --fqbn arduino:avr:uno firmware/hardware_controller
arduino-cli upload  --fqbn arduino:avr:uno -p COM5 firmware/hardware_controller

# 4. ROS 2
cd ros2_ws && colcon build --merge-install   # on Linux you can use --symlink-install
call install\setup.bat                        # Linux: source install/setup.bash
ros2 launch sensor_motor_lab lab.launch.py port:=COM5
```

On Ubuntu 22.04 you can also use a native apt install of ROS 2 Humble instead of conda; see [ros2_ws/README.md](ros2_ws/README.md).

## File guide

| Path | Contents |
|---|---|
| [TEAM_SETUP.md](TEAM_SETUP.md) | **Teammates who receive the archive start here**: installation, environment, self-check, and the order of hardware tests |
| [ros2_ws/README.md](ros2_ws/README.md) | Environment, build, launch, topics, GUI usage |
| [tests/TEST_REPORT.md](tests/TEST_REPORT.md) | Test report for this round (separates actually-run passes, software-model passes, not run, and needs physical parameters) |

## Order of work once hardware is connected

1. With power off, wire according to [WIRING.md](hardware/WIRING.md) and check with a multimeter.
2. Connect USB only (bench supply off), upload the firmware, start the GUI, and confirm that the raw values of all four sensors change.
3. Turn the encoder by hand to measure CPR and direction (the GUI's Encoder CPR helper).
4. Check `hardware_config.h`, set `HARDWARE_CONFIG_VERIFIED` to `true`, regenerate, and upload.
5. Turn on the bench supply and test one motor at a time at low speed: DC speed → DC relative angle → servo endpoints → stepper.
6. Run all three motors together, then go through [FIELD_CHECKLIST.md](docs/FIELD_CHECKLIST.md) end to end.
7. Use `calibration/capture.py` to collect calibration and validation data, use `analyze.py` to produce transfer curves and errors, and write the suggested values back into `hardware_config.h`.

## Assignment acceptance checklist

| Requirement | Where it is implemented | Status |
|---|---|---|
| 4 different sensors (at least 1 analog), one Uno running one program | Potentiometer, IR, ultrasonic (analog) + slot sensor; `hardware_controller.ino` | Software complete |
| GUI shows physical quantities; slot sensor shows interruption state and count | rqt panel | Software complete; physical quantities need calibration |
| Transfer curves drawn from the team's own measured data | `calibration/analyze.py` → `*_transfer.svg` | Tool complete; **needs measured data** |
| At least one sensor is filtered, with before/after shown | IR 5-point moving average (GUI plot + `ir_filter.svg`); ultrasonic also has a median filter | Software complete |
| Servo to any angle; DC with encoder + PID + bidirectional speed + relative angle; stepper bidirectional relative angle with the rounded angle displayed | Firmware + GUI | Software complete; **needs tuning on hardware** |
| Three sensors each control one of three motors; GUI/sensor switching; physical switch with debounce | Firmware sensor mode + A4 switch | Software complete |
| Goes through ROS 2: bridge node publishes state and subscribes to commands; GUI has graphical controls and output | `lab_bridge` + rqt plugin | Run and passed on real ROS 2 Humble |
| Public GitHub repository, every member makes a substantial contribution | See next section | Done by the team |

## GitHub and team division of work

The project is managed locally with git (`.gitattributes` enforces LF so it works directly on both Windows and Linux). **It has not been pushed to any remote repository yet.** Creating the public repository, inviting teammates, and committing individual contributions must all be done by team members with their own accounts; the tools will not publish on anyone's behalf or fabricate contribution history.

Suggested division (each person owns one area and describes their contribution and technical challenges in their PR):

1. Firmware mode switching, switch, and servo (mode and button logic in `controller_core.h`, servo endpoint measurement)
2. DC encoder and PID (CPR/direction measurement, PID tuning, protection mechanism verification)
3. Slot sensor and stepper (EE-SX1042 wiring, stepper current limit and coil pairing, rounded display)
4. Distance sensors and calibration (IR/ultrasonic/potentiometer capture, transfer curves and error analysis)
5. ROS/GUI integration (bridge, rqt panel, CSV logging, demo flow)

The final demo is 5–7 minutes, including at least 1 minute explaining how this lab relates to the team's group project.
