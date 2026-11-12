// Arduino Uno adapter: pins, interrupts, pulses, serial I/O.
// generate_sketches.py concatenates controller_core.h + hardware_config.h + this file
// into firmware/hardware_controller/hardware_controller.ino. Edit the sources, not the .ino.
#include <Servo.h>

// ---- Fixed wiring (hardware/WIRING.md). Changing a pin here means rewiring. ----
const uint8_t POT_PIN = A0, IR_PIN = A1, SONAR_PIN = A2, SLOT_PIN = A3, BUTTON_PIN = A4;
const uint8_t ENC_A = 2, ENC_B = 3;                  // external interrupts INT0 / INT1
const uint8_t DC_IN1 = 4, DC_PWM = 5, DC_IN2 = 7;    // Solarbotics I1, E1-2 (PWM, Timer0), I2
const uint8_t STEP_PIN = 6, DIR_PIN = 8, ENABLE_PIN = 10;  // EasyDriver; ENABLE LOW = enabled
const uint8_t SERVO_PIN = 9;                         // Servo library uses Timer1 (no PWM on D9/D10)
const uint8_t MODE_LED = 13;
const bool SLOT_BLOCKED_HIGH = true;                 // EE-SX1042 C on INPUT_PULLUP: dark -> HIGH

const uint32_t SENSOR_PERIOD_MS = 20;
const uint32_t TELEMETRY_PERIOD_MS = 100;
const uint32_t CONFIG_PERIOD_MS = 1000;

lab::Controller controller(hw::makeHardwareConfig());
Servo servo;
volatile int32_t encoderCounts = 0;
volatile uint8_t previousEncoderBits = 0;

// ---- Non-blocking serial output -------------------------------------------------
// Serial.print blocks once the 64-byte hardware buffer is full, which would
// stall STEP pulses and command handling. Lines are queued here and drained
// only as fast as Serial.availableForWrite() allows. Telemetry is dropped (and
// counted) when the queue is short of space; ACK/INFO lines are never dropped.
const uint16_t TX_SIZE = 256;
const uint16_t TX_RESERVE = 48;  // kept free for ACK lines
char txRing[TX_SIZE];
uint16_t txHead = 0, txTail = 0;
uint32_t droppedTelemetry = 0;
char lineBuffer[192];  // fits the longest STATE line (checked by tests/firmware/test_controller.cpp)

uint16_t txUsed() { return uint16_t((txHead + TX_SIZE - txTail) % TX_SIZE); }
uint16_t txFree() { return uint16_t(TX_SIZE - 1 - txUsed()); }
void txPump() {
  int room = Serial.availableForWrite();
  while (room-- > 0 && txTail != txHead) { Serial.write(txRing[txTail]); txTail = uint16_t((txTail + 1) % TX_SIZE); }
}
bool txQueue(const char *line, size_t length, bool essential) {
  if (length == 0) return false;
  if (!essential && txFree() < length + TX_RESERVE) { ++droppedTelemetry; return false; }
  while (txFree() < length) txPump();  // essential line: wait (rare; bounded by baud rate)
  for (size_t i = 0; i < length; ++i) { txRing[txHead] = line[i]; txHead = uint16_t((txHead + 1) % TX_SIZE); }
  return true;
}
void txInfo(const char *detail) {  // detail: LAB_STR (flash) string
  lab::LineWriter w(lineBuffer, sizeof(lineBuffer));
  w.text(LAB_STR("INFO,")); w.text(detail);
  txQueue(lineBuffer, w.finish(), true);
}

// ---- Encoder: x4 quadrature decoding on both channels. RAW count, no sign. ----
void encoderChanged() {
  const uint8_t bits = uint8_t((digitalRead(ENC_A) << 1) | digitalRead(ENC_B));
  static const int8_t transition[16] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};
  encoderCounts += transition[(previousEncoderBits << 2) | bits];
  previousEncoderBits = bits;
}
int32_t readEncoder() {
  noInterrupts(); const int32_t value = encoderCounts; interrupts(); return value;  // atomic 32-bit read
}

// ---- Commands ----------------------------------------------------------------------
char inputLine[80];
uint8_t inputLength = 0;
bool droppingLine = false;

void readCommands(uint32_t now) {
  // Bound processing per loop so malformed/flooded serial input cannot starve motors.
  for (uint8_t budget = 0; budget < 48 && Serial.available(); ++budget) {
    const char c = char(Serial.read());
    if (c == '\r') continue;
    if (c == '\n') {
      if (droppingLine) {
        const lab::Ack ack = {0, false, LAB_STR("LINE_TOO_LONG")};
        txQueue(lineBuffer, lab::formatAck(ack, lineBuffer, sizeof(lineBuffer)), true);
      } else if (inputLength) {
        inputLine[inputLength] = 0;
        const lab::Ack ack = controller.command(inputLine, now, readEncoder());
        txQueue(lineBuffer, lab::formatAck(ack, lineBuffer, sizeof(lineBuffer)), true);
      }
      inputLength = 0; droppingLine = false;
    } else if (!droppingLine) {
      if (c < 32 || c > 126 || inputLength >= sizeof(inputLine) - 1) { droppingLine = true; inputLength = 0; }
      else inputLine[inputLength++] = c;
    }
  }
}

// ---- Outputs -----------------------------------------------------------------------
void driveMotor() {
  const float output = controller.armed ? controller.pwm : 0;
  const int magnitude = int(lab::limit(fabsf(output), 0, 255));
  const int8_t direction = output > 0 ? 1 : (output < 0 ? -1 : 0);
  static int8_t previousDirection = 0;
  // Drop enable only when changing bridge direction (not on every loop).
  if (direction != previousDirection) {
    analogWrite(DC_PWM, 0);
    digitalWrite(DC_IN1, direction > 0 ? HIGH : LOW); digitalWrite(DC_IN2, direction < 0 ? HIGH : LOW);
    previousDirection = direction;
  }
  analogWrite(DC_PWM, magnitude);
}

void driveServo() {
  // Pulses only while armed. The pulse width is set BEFORE attach so the first
  // pulse is the commanded (initially mid-travel) value, not the library default.
  if (controller.armed) {
    servo.writeMicroseconds(int(controller.servoMicroseconds() + 0.5f));
    if (!servo.attached()) servo.attach(SERVO_PIN);
  } else if (servo.attached()) {
    servo.detach();
  }
}

int readAnalogSettled(uint8_t pin) {
  analogRead(pin);  // discard: ADC sample-and-hold settles after a channel switch
  return analogRead(pin);
}

void setup() {
  pinMode(DC_PWM, OUTPUT); pinMode(DC_IN1, OUTPUT); pinMode(DC_IN2, OUTPUT);
  analogWrite(DC_PWM, 0); digitalWrite(DC_IN1, LOW); digitalWrite(DC_IN2, LOW);
  pinMode(STEP_PIN, OUTPUT); pinMode(DIR_PIN, OUTPUT); pinMode(ENABLE_PIN, OUTPUT); pinMode(MODE_LED, OUTPUT);
  digitalWrite(STEP_PIN, LOW); digitalWrite(ENABLE_PIN, HIGH);  // stepper driver disabled until ARM
  pinMode(SLOT_PIN, INPUT_PULLUP); pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(ENC_A, INPUT_PULLUP); pinMode(ENC_B, INPUT_PULLUP);
  previousEncoderBits = uint8_t((digitalRead(ENC_A) << 1) | digitalRead(ENC_B));
  attachInterrupt(digitalPinToInterrupt(ENC_A), encoderChanged, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_B), encoderChanged, CHANGE);
  Serial.begin(115200);
  txInfo(LAB_STR("BOOT_DISARMED"));
  const char *error = lab::configError(controller.cfg);
  if (error) txInfo(error);
  if (!controller.cfg.hardwareVerified) txInfo(LAB_STR("HARDWARE_CONFIG_VERIFIED_FALSE_ARM_REFUSED"));
  if (!controller.calibrated()) txInfo(LAB_STR("CALIBRATION_INCOMPLETE"));
}

void loop() {
  static uint32_t lastSensorsMs = 0, lastTelemetryMs = 0, lastConfigMs = 0, reportedDrops = 0;
  static bool configSent = false;
  const uint32_t now = millis();
  readCommands(now);
  if (lab::elapsed(now, lastSensorsMs) >= SENSOR_PERIOD_MS) {
    lastSensorsMs = now;
    const int pot = readAnalogSettled(POT_PIN), ir = readAnalogSettled(IR_PIN), sonar = readAnalogSettled(SONAR_PIN);
    const bool slotBlocked = digitalRead(SLOT_PIN) == (SLOT_BLOCKED_HIGH ? HIGH : LOW);
    controller.sensors(pot, ir, sonar, slotBlocked, digitalRead(BUTTON_PIN) == LOW, now);
  }
  controller.control(now, readEncoder());
  driveMotor();
  driveServo();
  digitalWrite(ENABLE_PIN, controller.armed ? LOW : HIGH);
  const int stepDirection = controller.step(micros());
  if (stepDirection) {
    digitalWrite(DIR_PIN, stepDirection > 0 ? HIGH : LOW);
    delayMicroseconds(2); digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(3); digitalWrite(STEP_PIN, LOW);
  }
  digitalWrite(MODE_LED, controller.mode == lab::SENSOR ? HIGH : LOW);
  if (!configSent || lab::elapsed(now, lastConfigMs) >= CONFIG_PERIOD_MS) {
    lastConfigMs = now; configSent = true;
    txQueue(lineBuffer, lab::formatConfig(controller.cfg, lineBuffer, sizeof(lineBuffer)), true);
    if (droppedTelemetry != reportedDrops) { reportedDrops = droppedTelemetry; txInfo(LAB_STR("TELEMETRY_DROPPED")); }
  }
  if (lab::elapsed(now, lastTelemetryMs) >= TELEMETRY_PERIOD_MS) {
    lastTelemetryMs = now;
    // STATE and RAW share one timestamp so the GUI can pair them in CSV logs.
    if (txQueue(lineBuffer, lab::formatState(controller, now, lineBuffer, sizeof(lineBuffer)), false))
      txQueue(lineBuffer, lab::formatRaw(controller, now, lineBuffer, sizeof(lineBuffer)), false);
  }
  txPump();
}
