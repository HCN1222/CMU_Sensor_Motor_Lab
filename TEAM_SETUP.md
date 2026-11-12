# Handoff: Rebuilding the Environment and Testing on Hardware

For the teammate who receives the archive and is **responsible for hardware testing**. Complete steps 1–4 in order and you will have, on your own computer, exactly the same self-checked environment as at handoff; then move on to hardware testing in step 5.

## 0. Current status

| Done (actually run and passed) | Not done yet (needs you to connect hardware) |
|---|---|
| Uno firmware compiles (Flash 65%, RAM 58%) | Upload the new firmware to a real Uno |
| 125 C++ control-core checks, Python unit tests, offscreen GUI test | Encoder CPR and direction, servo endpoints, potentiometer angle |
| Real ROS 2 Humble bridge node, topics, rqt plugin, launch file (Windows and Linux) | DC PID tuning, running all three motors under power |
| Calibration analysis tools (tested with synthetic data only) | Measured calibration and error data for IR / ultrasonic / potentiometer |

Motors and sensors are **simulated** in the software tests. All physical parameters are currently placeholders or manufacturer typical values, collected in [firmware/hardware_config.h](firmware/hardware_config.h). The firmware defaults to `HARDWARE_CONFIG_VERIFIED = false` and **refuses to ARM until you verify the wiring and change it to true by hand**. This is intentional.

## 1. Install software (Windows)

| Software | Purpose | Notes |
|---|---|---|
| [Miniforge](https://github.com/conda-forge/miniforge) or Miniconda | Python + ROS 2 Humble + rqt | ROS 2 is provided as conda packages (RoboStack); **no separate ROS install is needed** |
| [Arduino IDE 2.x](https://www.arduino.cc/en/software) | Uploading firmware | Bundles arduino-cli; on first launch let it install **Arduino AVR Boards** |
| Servo library | Firmware dependency | Arduino IDE → Library Manager → search `Servo` (official Arduino, 1.3.0 tested) |
| VS Code (optional) | Editing | |
| Git (optional) | Version control, creating the GitHub repository | |

Linux (Ubuntu 22.04) can also use conda, or an apt install of ROS 2 Humble; see [ros2_ws/README.md](ros2_ws/README.md).

## 2. Extract and create the environment

Extract to a location **outside OneDrive sync with a short path**, for example `C:\lab\sensor_motor_lab` (colcon generates many files, and OneDrive syncing slows things down or even locks files).

Open **Anaconda Prompt / Miniforge Prompt** (or a PowerShell where `conda init powershell` has been run):

```bat
cd C:\lab\sensor_motor_lab
conda env create -f environment.yml
conda activate sensorMotorLab
conda install -c conda-forge gxx_win-64
```

- Creating the environment the first time downloads about 1–2 GB and takes from a few minutes to over ten minutes.
- The last line installs a C++ compiler for the firmware's host-side tests. On Linux use `conda install -c conda-forge cxx-compiler` instead.
- Run `conda activate sensorMotorLab` first in every new terminal.

## 3. Offline self-check (no Uno required)

```bat
python tools/run_tests.py --ros
```

Every line of the final Summary should be `PASS`. On Windows the Python unit tests show 1 `skipped` (the pseudo-terminal test only runs on Linux); this is expected. The script looks for arduino-cli in the Arduino IDE's default install location; if it is not found, the Uno compile item shows `SKIP` without affecting the others.

If anything shows `FAIL`, do not connect hardware yet; send the full terminal output to the person responsible for the software.

## 4. Build the ROS 2 workspace

```bat
cd ros2_ws
colcon build --merge-install
call install\setup.bat
```

In PowerShell use `install\setup.ps1`; on Linux use `colcon build --symlink-install` and `source install/setup.bash`. Run `setup.bat` again in every new terminal.

## 5. Hardware testing

**First read [hardware/WIRING.md](hardware/WIRING.md) (the only valid wiring table) and [docs/HARDWARE_PARAMETERS.md](docs/HARDWARE_PARAMETERS.md) in full.** The old diagrams and programs in the `legacy` folders use different pins; do not wire from them.

### 5.1 Upload the firmware (USB only, bench supply off)

1. Find the Uno's serial port in the Arduino IDE (Tools → Port, e.g. `COM3`; written as `COMx` below).
2. Open `firmware/hardware_controller/hardware_controller.ino` in the Arduino IDE, select Arduino Uno as the board, and upload.
   Command-line alternative:
   ```bat
   arduino-cli compile --fqbn arduino:avr:uno firmware/hardware_controller
   arduino-cli upload  --fqbn arduino:avr:uno -p COMx firmware/hardware_controller
   ```
3. `hardware_controller.ino` is **generated**. To change parameters, edit `firmware/hardware_config.h`, run `python firmware/generate_sketches.py` to regenerate, then upload again.

### 5.2 Start the GUI

First **close the Arduino IDE Serial Monitor** (a serial port can only be opened by one program at a time):

```bat
ros2 launch sensor_motor_lab lab.launch.py port:=COMx
```

If the panel does not appear: run `rqt --force-discover`, then choose Robot Tools → Sensors and Motor Control.

### 5.3 Test order

Follow "Before the first ARM" and §1–§8 in [docs/HARDWARE_PARAMETERS.md](docs/HARDWARE_PARAMETERS.md). In outline:

1. **DISARMED, bench supply off**: confirm that the raw values of all four sensors in the GUI's Raw inputs row change with motion, and that the mode switch toggles modes.
2. **Encoder**: use the GUI's Encoder CPR helper, turn the output shaft one revolution by hand, measure counts per revolution (§1) and direction (§2), and enter them in `hardware_config.h`.
3. After checking `hardware_config.h`, change `HARDWARE_CONFIG_VERIFIED` to `true`, regenerate, and upload.
4. **Turn on the bench supply (set a low current limit first)** and test each motor alone at low speed: DC speed → DC relative angle (§3) → servo endpoints (§4) → stepper.
5. Run all three motors together, then go through [docs/FIELD_CHECKLIST.md](docs/FIELD_CHECKLIST.md) end to end.
6. **Calibration**: with ROS shut down, collect data with `calibration/capture.py` and produce transfer curves and errors with `calibration/analyze.py` (see [calibration/README.md](calibration/README.md)). Write the suggested values back into `hardware_config.h`, and only set the corresponding `*_CALIBRATED` to true once validation data supports it.

### 5.4 Safety rules

- On first power-up, keep your hand near the GUI's STOP button or the power switch. STOP is a software stop and **does not cut power**.
- Stalls, a reversed encoder direction, lost heartbeat, and positioning timeouts all stop the motors automatically, and the GUI's `fault` shows the reason. If `ENCODER_DIRECTION` appears, flip the sign of `ENCODER_SIGN` first and try again; **do not just increase the gains**.
- Do not upload the old programs in `firmware/legacy_*` while the full wiring is connected.

## 6. Common issues

| Symptom | Cause / fix |
|---|---|
| Bridge reports the serial port cannot be opened / Access denied | The Serial Monitor or another program holds the port, or `port:=` is wrong |
| ARM rejected, ACK shows `CONFIG_REQUIRED` | `HARDWARE_CONFIG_VERIFIED` is still false (expected; see 5.3 step 3) |
| ARM rejected, shows `CONFIG_INVALID` | Values in `hardware_config.h` are inconsistent (e.g. the IR table is not monotonic); the INFO line at power-up names the item |
| Panel stays on `Waiting for firmware CONFIG` and motion commands are rejected | The bridge has not received the firmware's CONFIG frame: check the port and whether the **new** firmware has been uploaded |
| `conda activate` does nothing in PowerShell | Run `conda init powershell` once, then reopen the terminal |
| `ros2` command not found | `conda activate sensorMotorLab` was not run, or `install\setup.bat` was not run in the new terminal |
| Serial port not visible in WSL | WSL needs usbipd-win to forward USB; running directly in the Windows conda environment is simpler |

## 7. Recording results and submitting

- Add hardware test results to [tests/TEST_REPORT.md](tests/TEST_REPORT.md), marked "passed on hardware" and kept separate from the existing "passed in software" entries.
- Write calibration data into `calibration/*.csv` (currently headers only). **Record only real measurements.**
- The archive **does not include git history**. To create the GitHub repository:
  ```bat
  git init
  git add .
  git commit -m "Import project snapshot"
  ```
  A teammate creates the public repository with their own account and invites the others; each person commits the part they are responsible for with their own account (see the end of [README.md](README.md) for the suggested division).
