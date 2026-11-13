# Field Test Checklist

Record test results in [TEST_REPORT.md](../tests/TEST_REPORT.md).

## 1. Connect and Start

- [ ] Bench outputs off; 12V and fixed 5V connected, with common GND.
- [ ] Connect the Uno by USB. Close other programs using its serial port.
- [ ] Load the project environment:
  - Windows: `conda activate sensorMotorLab`, then `call ros2_ws\install\setup.bat`.
  - Linux: `source /opt/ros/humble/setup.bash && source ros2_ws/install/setup.bash`.
- [ ] Run `ros2 launch sensor_motor_lab lab.launch.py port:=COM5`; replace the port with the Uno's port, such as `/dev/ttyACM0` on Linux.

## 2. Check Inputs While Disarmed

- [ ] GUI shows `LIVE · DISARMED`.
- [ ] Potentiometer and IR ADC values respond to movement.
- [ ] Ultrasonic distance updates; obstructing the slot shows `BLOCKED`.
- [ ] Each switch press changes mode once. Return to GUI mode.
- [ ] Turning the DC output shaft changes the raw encoder count.

## 3. Check Configuration and Arm

- [ ] Uploaded configuration has `HARDWARE_CONFIG_VERIFIED = true`; no `ARM DISABLED` message.
- [ ] Displayed servo range, RPM range and IR thresholds match `hardware_config.h`.
- [ ] Note any subsystems marked `PROVISIONAL`.
- [ ] Turn on bench outputs. Select GUI control and press **ARM outputs**; GUI shows `LIVE · ARMED`.

## 4. Test GUI Control

- [ ] Servo: command minimum, middle and maximum angles. The display shows commanded angle.
- [ ] DC speed: command +20, −20 and 0 RPM; compare target and measured speed.
- [ ] DC position: command +90° and −90°; encoder-based remaining angle returns to zero.
- [ ] Stepper: command +90° and −90°. A 91° command rounds to 51 steps / 91.8°; displayed angle is calculated from steps sent.

## 5. Test Sensor Control

- [ ] Press the mode switch: `SENSOR control`, D13 on, GUI motion controls disabled.
- [ ] Potentiometer movement changes servo position.
- [ ] IR: below 35 cm stops the DC motor; above 45 cm runs it at 20 RPM; 35–45 cm retains the previous state.
- [ ] One new slot obstruction commands 90° of stepper motion.
- [ ] Holding the slot blocked does not retrigger motion.
- [ ] A new obstruction while the stepper is moving increments `ignored`.
- [ ] Ultrasonic distance and its plot continue updating.

## 6. Test STOP and Shut Down

- [ ] With DC and stepper moving, press **STOP / DISARM**. GUI shows `DISARMED`; DC drive and stepper motion stop.
- [ ] Motion does not resume until rearmed.
- [ ] STOP, turn off bench outputs, close rqt and launch with Ctrl+C, then disconnect USB.

STOP sets DC PWM to zero, cancels remaining steps, disables the stepper driver and stops servo pulses. Power remains connected.
