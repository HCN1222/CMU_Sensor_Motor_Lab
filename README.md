# Four Sensors · Three Motors · Arduino Uno · ROS 2

Five-person Sensors & Motor Control assignment. The goal is a single Arduino Uno firmware that handles 4 sensors and 3 kinds of motors at once, controlled from a PC through a ROS 2 serial bridge and an rqt panel.

## Target behavior

| Mode | Behavior |
|---|---|
| GUI mode | The panel controls servo angle, DC signed RPM and relative angle (encoder closed loop), and bidirectional stepper relative angle |
| Sensor mode | Potentiometer → servo angle; Sharp IR distance → DC start/stop (with hysteresis); each new slot-sensor interruption → stepper turns 90° |
| Shown in both modes | All four sensors, the three motor states, mode, and connection status; the ultrasonic sensor keeps ranging and is plotted |
| Physical switch | Each press of a debounced switch toggles the mode |

**Current status**: the firmware, serial protocol, calibration analysis, wiring documentation, and the ROS 2 bridge and rqt control panel are in the repository. The bridge and panel have been run on ROS 2 Humble without an Uno attached; running them with the real hardware is next.

## Assignment requirements

- 4 different sensors (at least 1 analog), all on one Uno running one program.
- The GUI shows physical quantities; the slot sensor shows its interruption state and count.
- Transfer curves drawn from the team's own measured data.
- At least one sensor is filtered, with the result shown before and after filtering.
- Servo to any angle; DC motor with encoder, PID, bidirectional speed, and relative angle; stepper with bidirectional relative angle and the rounded angle displayed.
- Three sensors each control one of the three motors; switching between GUI and sensor control; a physical switch with debounce.
- Everything goes through ROS 2: a bridge node publishes state and subscribes to commands; the GUI has graphical controls and output.
- Public GitHub repository, with a substantial contribution from every member.
- Final demo of 5–7 minutes, including at least 1 minute on how this lab relates to the team's group project.

## Environment

Windows / Linux / macOS all use the same conda environment; ROS 2 Humble comes from RoboStack conda packages.

```bash
conda env create -f environment.yml
conda activate sensorMotorLab
```

On Ubuntu 22.04 you can instead use a native apt install of ROS 2 Humble. Step-by-step setup is in [TEAM_SETUP.md](TEAM_SETUP.md).

## ROS 2 bridge and control panel

```bash
cd ros2_ws && colcon build --merge-install   # on Linux you can use --symlink-install
call install\setup.bat                        # Linux: source install/setup.bash
ros2 launch sensor_motor_lab lab.launch.py port:=COM5
```

The `lab_bridge` node talks to the Uno over USB serial and the rqt panel sends commands and plots live data. Topics, safety logic, and GUI usage are in [ros2_ws/README.md](ros2_ws/README.md).

## Repository layout

Empty folders hold a `.gitkeep` file; delete it once the folder has real content.

| Folder | Purpose |
|---|---|
| `firmware/` | Arduino Uno firmware |
| `ros2_ws/src/` | ROS 2 workspace: serial bridge node and rqt panel |
| `hardware/` | Wiring documentation and diagrams |
| `calibration/` | Sensor calibration data and analysis |
| `tests/` | Test code and the [test report](tests/TEST_REPORT.md) |
| `tools/` | Helper scripts |
| `docs/` | Project documentation |
| `reference/` | Course assignment material |

## Team division

Each person owns one area and describes their contribution and technical challenges in their PRs.

| Member | Scope |
|---|---|
| ChengNing | ROS 2 nodes and rqt GUI; repository skeleton |
| Zean | Arduino firmware core: mode switching, switch, servo |
| Audrey | Serial protocol, controller tests, DC encoder and PID |
| Yiheng | Hardware wiring tools, integration tests, slot sensor and stepper |
| Aasta | Sensor calibration: IR, ultrasonic, potentiometer |

Contribution workflow: [CONTRIBUTING.md](CONTRIBUTING.md) and [BRANCH_NAMING.md](BRANCH_NAMING.md). Test results are recorded in [tests/TEST_REPORT.md](tests/TEST_REPORT.md).
