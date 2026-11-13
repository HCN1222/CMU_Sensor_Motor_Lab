
# Arduino Firmware and Sensor Validation

## Purpose

Validate the Arduino Uno firmware and sensor integration for the CMU Sensor & Motor Control Lab. The objective is to verify firmware compilation, sensor data acquisition, signal processing, serial communication, and basic controller safety before full hardware integration.

## Validation Scope

The validation covers the following components:

- Arduino Uno firmware compilation and memory usage.
- Sharp GP2Y0A02 IR distance sensor.
- LV-MaxSonar-EZ ultrasonic distance sensor.
- Potentiometer input and position conversion.
- Slot sensor and mode button debouncing.
- Serial communication and sensor data reporting.
- Basic motor control and safety mechanisms.

## Hardware Components

| Component | Function | Arduino Connection |
|---|---|---|
| Arduino Uno | Main microcontroller | USB / 5V |
| Sharp GP2Y0A02 IR Sensor | Infrared distance measurement | A1 |
| LV-MaxSonar-EZ | Ultrasonic distance measurement (AN output) | A2 |
| Potentiometer | Analog position measurement | A0 |
| Slot Sensor | Object detection and event counting | A3 |
| Mode Button | Operating mode selection | A4 |

Refer to [hardware/WIRING.md](../../hardware/WIRING.md) for the complete hardware wiring configuration.

## Validation Status

| Validation Item | Status | Notes |
|---|---|---|
| Arduino Uno firmware compilation | Passed | Successfully compiled on November 9, 2026 |
| Flash memory usage | Passed | 21,030 / 32,256 bytes (65%) |
| SRAM usage | Passed | 1,202 / 2,048 bytes (58%) |
| Sharp IR sensor reading | Initial testing | Accuracy depends on calibration |
| MaxSonar ultrasonic reading | Initial testing | Analog output requires validation |
| Potentiometer processing | Pending full calibration | ADC range and travel angle must be verified |
| Slot sensor debouncing | Pending integration testing | 10 ms debounce |
| Mode button debouncing | Pending integration testing | 30 ms debounce |
| Serial communication | Pending full integration testing | Protocol v2, 115200 baud |
| DC motor and stepper control | Pending full integration testing | Requires hardware verification |
| Watchdog and safety mechanisms | Pending hardware validation | Must be tested before deployment |

## Arduino Firmware Compilation

The Arduino Uno firmware was successfully compiled using:

- **Board:** Arduino Uno
- **Board platform:** `arduino:avr 1.8.8`
- **Servo library:** `1.3.0`
- **Compilation date:** November 9, 2026

### Compilation Commands

```bash
arduino-cli lib install Servo

python firmware/generate_sketches.py

python firmware/generate_sketches.py --check

arduino-cli compile \
  --fqbn arduino:avr:uno \
  firmware/hardware_controller
```

### Memory Usage

| Resource | Used | Available | Usage |
|---|---:|---:|---:|
| Flash | 21,030 B | 32,256 B | 65% |
| SRAM | 1,202 B | 2,048 B | 58% |
| Remaining SRAM | 846 B | — | — |

The compilation results confirm that the firmware fits within the Arduino Uno's Flash and SRAM limits.

Successful compilation does not guarantee correct operation on physical hardware.

## Sensor Validation

### 1. Sharp GP2Y0A02 IR Sensor

**Connection:** A1

**Processing method:**

- Read analog sensor voltage through the Arduino ADC.
- Convert ADC measurements into distance using piecewise linear interpolation.
- Apply a moving average over five consecutive valid measurements.
- Reject invalid readings and reset the filter when necessary.

**Expected output:**

- `ir_raw_cm`: Raw converted distance.
- `ir_cm`: Filtered distance.

**Validation procedure:**

1. Place an object at known distances.
2. Record the raw and filtered sensor measurements.
3. Compare measured distances with ground-truth values.
4. Check filtering stability and invalid-distance handling.

**Known limitation:**

The Sharp GP2Y0A02 has a non-monotonic voltage response at very short distances. Measurements below approximately 15 cm may be ambiguous.

### 2. LV-MaxSonar-EZ Ultrasonic Sensor

**Connection:** AN → A2

**Processing method:**

- Acquire analog voltage measurements.
- Apply a nine-sample median filter.
- Convert ADC readings to distance using the configured scale of approximately 1.27 cm/ADC.

**Expected output:**

- `sonar_cm`: Estimated ultrasonic distance.

**Validation procedure:**

1. Position a target at several known distances.
2. Collect ultrasonic sensor measurements.
3. Compare measured values against actual distances.
4. Evaluate measurement consistency and noise.
5. Verify handling of invalid or out-of-range measurements.

**Note:**

The legacy sensor bench test used the MaxSonar pulse-width output on D2. The integrated firmware uses the analog output on A2.

### 3. Potentiometer

**Connection:** A0

**Processing method:**

- Read the analog position value.
- Normalize the ADC measurement using `POT_ADC_MIN` and `POT_ADC_MAX`.
- Convert the normalized percentage into an angle using `POT_TRAVEL_DEG`.

**Expected outputs:**

- `pot_pct`: Normalized potentiometer position.
- `pot_deg`: Estimated potentiometer angle.

**Validation procedure:**

1. Record ADC values at both mechanical endpoints.
2. Configure the minimum and maximum ADC limits.
3. Measure the actual mechanical travel angle.
4. Verify position-to-angle conversion.

### 4. Slot Sensor

**Connection:** A3

The firmware applies a 10 ms debounce interval.

Each new obstruction should increment the slot counter once.

Validation should verify:

- Correct obstruction detection.
- No duplicate counting during a sustained obstruction.
- Stable detection during repeated transitions.

### 5. Mode Button

**Connection:** A4

The firmware applies a 30 ms debounce interval.

Each valid button press should trigger one mode change.

Validation should verify:

- One mode transition per press.
- No repeated switching while the button remains pressed.
- Stable behavior during mechanical contact bounce.

## Serial Communication Validation

The firmware uses Serial Protocol v2.

**Configuration:**

- Baud rate: `115200`
- Encoding: ASCII
- Line ending: LF

### Manual Communication Test

Open Arduino Serial Monitor and send:

```text
CMD,1,PING,0
```

The controller should return an ACK response indicating whether the command was accepted.

### Telemetry Frames

The firmware provides the following frame types:

| Frame | Purpose |
|---|---|
| `STATE` | Processed sensor measurements and controller status |
| `RAW` | Raw ADC readings and sensor states |
| `CONFIG` | Hardware configuration and calibration parameters |
| `ACK` | Command acknowledgment |
| `INFO` | Diagnostic information |

### Expected Reporting Intervals

| Frame | Interval |
|---|---|
| `STATE` | 100 ms |
| `RAW` | 100 ms |
| `CONFIG` | 1000 ms |

Serial validation should confirm correct message formatting, sequence handling, and telemetry reporting.

## Safety Validation

The controller includes the following safety mechanisms:

| Safety Mechanism | Expected Behavior |
|---|---|
| Startup disarmed state | Motor outputs remain disabled |
| Hardware configuration verification | Reject ARM when configuration is unverified |
| Watchdog timeout | Stop and disarm after 1.5 seconds without an accepted command |
| Encoder stall protection | Stop when encoder movement is absent during sufficient motor output |
| Encoder direction protection | Stop when measured encoder direction disagrees with commanded direction |
| Position timeout | Stop DC position movement after 15 seconds without reaching the target |
| STOP command | Stop motor motion and disable outputs |

**Important:** STOP is a software shutdown and does not physically disconnect the power supply.

Do not enable motor control until hardware parameters and wiring have been verified.

## Limitations and Follow-up

The following tasks remain necessary before full deployment:

- Complete IR and ultrasonic sensor calibration.
- Verify sensor measurement accuracy at multiple distances.
- Validate potentiometer endpoint calibration.
- Test slot sensor and button debouncing on physical hardware.
- Verify encoder direction, counts per revolution, and PID parameters.
- Perform integrated DC motor, stepper motor, and servo testing.
- Validate watchdog and automatic fault handling.
- Complete ROS 2 communication and GUI integration testing.

## Related Documentation

- [Firmware Overview](../README.md)
- [Hardware Wiring](../../hardware/WIRING.md)
- [Hardware Configuration](../hardware_config.h)
- [Controller Core](../controller_core.h)
- [Arduino Adapter](../arduino_adapter.inc)

## Summary

The Arduino Uno firmware has successfully passed compilation and memory usage checks. Initial sensor testing has been performed, while comprehensive calibration, motor validation, and end-to-end system integration remain ongoing.

This document records the validation procedures, confirmed results, known limitations, and remaining tasks for the Arduino-based sensor and motor control system.
