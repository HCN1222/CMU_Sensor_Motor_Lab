# Software verification on 29 October 2026

The following checks were executed on the preparation computer. A pass here
does not establish that the supplied physical sensors, motors, drivers, or
ROS 2 installation have been tested.

| Check | Result | What it establishes |
|---|---|---|
| Python unit/integration suite | 21 tests passed | Strict protocol validation, frame fragmentation/overflow handling, ACK matching, no replay of relative moves, serial timeout behavior, operator lease, bridge callback behavior |
| Real pyserial pseudo-terminal test | Passed, included in the 21 tests | Commands and fragmented telemetry traverse an OS pseudo-terminal using the actual SerialLink and pyserial implementations |
| Cross-language firmware/bridge test | Passed; 41 STATE frames on the recorded run | Actual C++ firmware control core interoperates with actual Python link/parser for ARM, servo command, DC velocity and relative position, stepper relative angle, STOP/ZERO, sensor mode, RAW frames and watchdog |
| Qt widget test and render | Passed | Real PySide6 widgets render; control enablement follows telemetry/mode/armed state; ARM/STOP commands are formed correctly; charts draw; CSV rows pair matching STATE/RAW timestamps |
| Python source compilation | Passed | All Python files parse successfully |
| Actual ROS 2 middleware, colcon, and rqt discovery | Not run | ROS 2 is not installed on this computer |
| Physical wiring, sensor accuracy, real PID tuning | Not run | Hardware has not been collected |

The cross-language test uses `tests/firmware/host_cli.cpp`, compiled from the
same `controller_core.h` used by the Uno sketches. It supplies a **synthetic
DC plant and fixed synthetic sensor readings**. It does not emulate real motor
friction, supply transients, sensor noise, encoder wiring, or lost steps.

The Qt test uses actual Qt widgets with small import shims for the unavailable
ROS/rqt packages. Its preview is explicitly labeled synthetic. It does not
validate DDS communication, plugin discovery, or ROS package installation.
The four bridge callback tests also use ROS import shims.

One integration issue was found and fixed during this check: the host
simulator initially processed commands before older catch-up control ticks,
making the unsigned watchdog clock appear to jump backward. The simulator
now advances historical ticks before applying new commands. The Arduino
adapter already used a consistent current timestamp.

## Repeat the checks

Run from the `sensor_motor_lab` output directory. Use a Python environment
with `pyserial`; install `PySide6` only if running the optional offscreen GUI
test. The production ROS 2 environment instead supplies `python_qt_binding`.

```bash
PYTHONPATH=ros2_ws/src/sensor_motor_lab python3 -m unittest discover -s tests/python -p 'test_*.py' -v
g++ -std=c++11 -O2 tests/firmware/host_cli.cpp -o /tmp/lab_host_cli
PYTHONPATH=ros2_ws/src/sensor_motor_lab python3 tests/python/firmware_bridge_e2e.py /tmp/lab_host_cli
PYTHONPATH=ros2_ws/src/sensor_motor_lab python3 tests/python/dashboard_smoke.py /tmp/lab_dashboard_preview.png
```

On the ROS 2 laptop, build and launch using `README.md`, then verify topic
discovery, all GUI commands, rejected ranges, unplug/reconnect behavior, GUI
heartbeat loss, and matching CSV logging before the lab demonstration.
