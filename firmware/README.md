# Arduino Uno Firmware

## Files

| File | Description | Directly Editable |
|---|---|---|
| `controller_core.h` | Hardware-independent control logic: conversions, filtering, debouncing, operating modes, PID, safety protection, protocol parsing, and frame formatting | Yes (also used by host-side tests) |
| `hardware_config.h` | **Single source of truth for all hardware parameters** (encoder, PID, servo, potentiometer, IR lookup table, ultrasonic sensor, debouncing, and safety switches) | Yes (most frequently modified file) |
| `arduino_adapter.inc` | Arduino Uno pin assignments, interrupts, PWM/STEP outputs, Servo, and non-blocking serial communication | Yes |
| `generate_sketches.py` | Combines the three source files above into a single uploadable Arduino sketch | — |
| `hardware_controller/hardware_controller.ino` | **Auto-generated** uploadable sketch | No (will be overwritten) |
| `legacy_tinkercad/` | Previous browser-based demonstration program | No (do not upload) |
| `legacy_bench_sensor_test/` | Early single-sensor bench test (MaxSonar PW → D2, switch → D4; different from the final wiring configuration) | No (do not upload with the complete hardware setup) |

After modifying the source files:

```bash
python firmware/generate_sketches.py           # Regenerate the sketch
python firmware/generate_sketches.py --check   # Verify synchronization (also checked by test scripts)
```

### Uploading to Arduino Uno

Open `hardware_controller/hardware_controller.ino` using VS Code (Arduino Community Edition extension) or Arduino IDE.

- **Board:** Arduino Uno
- **Port:** COM5 (Windows) or `/dev/ttyACM0` (Linux)

Alternatively, use the command line:
```bash
arduino-cli lib install Servo
arduino-cli compile --fqbn arduino:avr:uno firmware/hardware_controller

### Compilation Results

**November 9, 2026** (`arduino:avr 1.8.8`, Servo `1.3.0`):

| Resource | Usage | Percentage |
|---|---|---|
| Flash | 21,030 / 32,256 B | 65% |
| Global RAM | 1,202 / 2,048 B | 58% |
| Remaining RAM for stack | 846 B | — |

---

## Runtime Behavior

| Interval | Operations |
|---|---|
| Every loop iteration | Process serial commands (up to 48 bytes per iteration), DC motor control, PWM, servo control, STEP pulse generation, and transmission queue flushing |
| 20 ms | Read A0/A1/A2 (discard the first ADC conversion for each channel), A3 slot sensor, and A4 button |
| 100 ms | Transmit `STATE` and `RAW` frames with the same timestamp |
| 1000 ms | Transmit `CONFIG` frame |

### Non-blocking Serial Communication

`Serial.print` may block when the 64-byte hardware transmission buffer becomes full, affecting STEP timing and STOP response latency.

To prevent this:

- All outgoing data is placed into a 256-byte transmission queue.
- Data is transmitted incrementally according to `Serial.availableForWrite()`.
- Telemetry frames are dropped when the queue lacks sufficient capacity.
- Dropped telemetry is reported through `INFO,TELEMETRY_DROPPED` at startup and once per second.
- ACK responses are never dropped.

### Memory Optimization

Strings are stored in Flash memory using `LAB_STR` / `PSTR` to reduce RAM consumption.

### Startup State

The controller starts in the **DISARMED** state upon power-up:

- Stepper ENABLE pin: HIGH
- DC motor PWM: 0
- Servo pulses: Disabled

---

## Safety and Protection

| Condition | Response | `fault` |
|---|---|---|
| `HARDWARE_CONFIG_VERIFIED = false` | Reject ARM command (`CONFIG_REQUIRED`) | — |
| Invalid configuration (e.g., non-monotonic IR lookup table or reversed hysteresis thresholds) | Reject ARM command (`CONFIG_INVALID`) and report specific configuration errors through INFO at startup | `CONFIG_INVALID` |
| No accepted command for 1.5 seconds (ROS sends PING every 0.5 seconds) | STOP and disable motor outputs | `WATCHDOG` |
| \|PWM\| >= 120 with no encoder count change for 1 second | STOP and disable motor outputs | `ENCODER_STALL` |
| \|PWM\| >= 120 with measured encoder direction opposite to the commanded output for 1 second | STOP and disable motor outputs | `ENCODER_DIRECTION` |
| `DC_MOVE` fails to reach its target within 15 seconds | Stop DC motor motion while remaining armed | `POSITION_TIMEOUT` |
| Mode switching (button or command) | Cancel DC motion and remaining stepper movement while preserving the current armed state | — |
| STOP command | Set DC PWM to 0, cancel remaining stepper movement, disable stepper, stop servo pulses, and disarm | — |

### Fault Handling

The `fault` field stores the most recent **automatic shutdown reason** since the last ARM command.

- The fault resets to `NONE` after the next successful ARM.
- STOP performs a software shutdown.
- STOP does **not** physically disconnect power.

---

## Sensor Processing

| Sensor | Conversion / Processing | Invalid Values |
|---|---|---|
| Potentiometer | `pot_pct` = normalized ADC position within [`POT_ADC_MIN`, `POT_ADC_MAX`]; `pot_deg` = normalized percentage × `POT_TRAVEL_DEG` | `pot_deg = -1` when `POT_TRAVEL_DEG = 0` (not calibrated) |
| Sharp GP2Y0A02 IR | Piecewise linear interpolation table → `ir_raw_cm`; moving average of 5 consecutive valid samples → `ir_cm` | Above the 20 cm calibration voltage: `-2` (too close); below the 150 cm calibration voltage: `-1`. Invalid samples reset the filter; `ir_cm = -1` until the window is full |
| MaxSonar AN | Median of 9 samples × 1.27 cm/ADC | Approximately <= 16.5 cm: `-2`; ADC < 4 (disconnected) or distance > 645 cm: `-1` |
| Slot Sensor | Count each new obstruction after 10 ms debouncing | — |
| Mode Button | Switch modes on each debounced press edge (30 ms); holding the button does not repeat the action | — |

### Sensor Mode Behavior

**Potentiometer → Servo**

The potentiometer percentage is mapped to the commanded servo angle.

**IR Sensor → DC Motor**

- If the filtered IR distance is below `IR_STOP_CM`, stop the DC motor.
- If the filtered IR distance is above `IR_START_CM`, run the DC motor at `DC_SENSOR_RPM`.
- Between the two thresholds, maintain the previous state.
- Invalid readings, excessively close readings, or incomplete filter windows are treated as STOP conditions.

**Slot Sensor → Stepper Motor**

- Each new obstruction triggers a 90° stepper rotation.
- If the stepper is already moving, the event is recorded in `slot_ignored`.
- Ignored events are not queued for later execution.

### GP2Y0A02 Limitation

At distances below approximately 15 cm, the GP2Y0A02 output voltage becomes non-monotonic and can match the voltage corresponding to a farther distance.

Consequently, a single ADC measurement cannot reliably distinguish these conditions.

The firmware can only identify readings with a voltage higher than the calibrated 20 cm point as **too close**.

---

## Serial Protocol v2

**Communication settings:**

- Baud rate: `115200`
- Encoding: ASCII
- Line termination: LF (`\n`)

### Message Formats

```text
CMD,<seq>,<verb>,<value>
ACK,<seq>,OK|ERR,<reason>
STATE,ms,mode,pot_deg,pot_pct,ir_raw_cm,ir_cm,sonar_cm,slot_count,slot_ignored,servo_cmd_deg,
      dc_deg,dc_rpm,dc_target,dc_control,step_deg,step_target_deg,step_busy,armed,calibrated,fault

RAW,ms,pot_adc,ir_adc,sonar_adc,slot_blocked,button_pressed,enc_counts,step_steps

CONFIG,protocol,servo_min_deg,servo_max_deg,servo_min_us,servo_max_us,max_rpm,sensor_rpm,
       dc_move_max_deg,step_move_max_deg,steps_per_rev,enc_cpr,enc_sign,pot_adc_min,pot_adc_max,
       pot_travel_deg,ir_stop_cm,ir_start_cm,sonar_cm_per_adc,hw_verified,cal_mask

INFO,<detail>
```

### Message Field Counts

| Message | Fields |
|---|---|
| `STATE` | 21 |
| `RAW` | 9 |
| `CONFIG` | 21 |

### Supported Commands

| Command | Description |
|---|---|
| `ARM` | Arm the controller |
| `STOP` | Stop all motion and disarm |
| `MODE` | Select operating mode (`0` = GUI, `1` = SENSOR) |
| `SERVO` | Set commanded servo angle in degrees |
| `DC_RPM` | Set DC motor speed |
| `DC_MOVE` | Move the DC motor by a relative angle |
| `STEP_MOVE` | Move the stepper motor by a relative angle |
| `ZERO` | Reset the reference position (only allowed while DISARMED) |
| `PING` | Keep-alive command for watchdog communication |

### Sequence Number Handling

Command sequence numbers must increase monotonically.

- A repeated command using the most recently accepted sequence number returns the previous ACK without re-executing the command.
- This prevents duplicate execution of relative movement commands.
- Commands with older sequence numbers return `STALE_SEQ`.

### State Interpretation

| Field | Meaning |
|---|---|
| `servo_cmd_deg` | Commanded servo angle, not measured position |
| `step_deg` | Estimated stepper position calculated from generated STEP pulses |
| `dc_deg` | Encoder-measured DC motor position |
| `dc_rpm` | Encoder-measured DC motor speed |
| `dc_target` | Internal absolute target position in DC position-control mode |
| `enc_counts` | Raw x4 encoder count, independent of CPR, sign configuration, and ZERO; useful for measuring CPR |

### Calibration Mask (`cal_mask`)

| Bit Value | Calibration |
|---|---|
| 1 | Potentiometer |
| 2 | IR sensor |
| 4 | Ultrasonic sensor |
| 8 | Encoder |
| 16 | Servo |

The `calibrated` field becomes true only when **all calibration bits are set**.

### Manual Serial Debugging

Using Arduino Serial Monitor:

1. Set the baud rate to `115200`.
2. Set the line ending to **Newline (LF)**.
3. Send the following command:

```text
CMD,1,PING,0
```

**Note:** The 1.5-second watchdog is active only after the controller has been armed.

## Protocol Version Management

Any change to protocol fields must be applied consistently across the following components:

1. `controller_core.h` — Frame formatting functions
2. `protocol.py` — Protocol parsing and definitions
3. GUI — Communication and display logic
4. `tests/` — Protocol and integration tests

Both version constants must be incremented together:

- `LAB_PROTOCOL_VERSION`
- `PROTOCOL_VERSION`

This ensures consistent communication between the Arduino firmware, ROS interface, GUI, and host-side tests.
