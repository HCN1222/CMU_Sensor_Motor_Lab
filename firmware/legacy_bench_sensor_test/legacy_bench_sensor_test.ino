#include <Arduino.h>
#include <math.h>

// ======================================
// Configuration
// ======================================

// Pins
const uint8_t MAXSONAR_PIN = 2;   // MaxSonar PW output -> D2
const uint8_t SHARP_PIN    = A1;  // Sharp IR analog output -> A1
const uint8_t SWITCH_PIN   = 4;   // Omron D3C NO -> D4, COM -> GND

// D3C switch: wired COM->GND, NO->pin with internal pull-up,
// so pressed = LOW. If wired to NC instead, set this to false.
const bool SWITCH_ACTIVE_LOW = true;
const unsigned long SWITCH_DEBOUNCE_MS = 20;

// Sharp IR model selection
#define SHARP_GP2Y0A21 21  // GP2Y0A21YK (10-80 cm)
#define SHARP_GP2Y0A02 2   // GP2Y0A02YK (20-150 cm)

#define SHARP_MODEL SHARP_GP2Y0A02

// ADC reference voltage
const float VREF = 5.0f;

// Timing
const unsigned long SAMPLE_INTERVAL_MS = 100;   // read sensors
const unsigned long REPORT_INTERVAL_MS = 1000;  // print summary
const int SAMPLES_PER_REPORT =
  REPORT_INTERVAL_MS / SAMPLE_INTERVAL_MS;

// MaxSonar (LV-MaxSonar-EZ): 147 us per inch
const float MAXSONAR_US_PER_INCH = 147.0f;
const unsigned long PULSE_TIMEOUT_US = 100000UL;

// ======================================
// Sharp IR Calibration Table
// (voltage must be strictly decreasing)
// ======================================

#if SHARP_MODEL == SHARP_GP2Y0A21

const char SHARP_NAME[] = "GP2Y0A21";
const float sharpDistances[] = { 10,   15,   20,   30,   40,   50,   60,   70,   80   };
const float sharpVoltages[]  = { 2.30, 1.65, 1.25, 0.90, 0.72, 0.60, 0.50, 0.44, 0.40 };

#elif SHARP_MODEL == SHARP_GP2Y0A02

const char SHARP_NAME[] = "GP2Y0A02";
const float sharpDistances[] = { 20,   30,   40,   50,   60,   80,   100,  120,  150  };
const float sharpVoltages[]  = { 2.45, 1.85, 1.40, 1.15, 0.98, 0.76, 0.59, 0.49, 0.40 };

#else
#error "Invalid SHARP_MODEL"
#endif

const int SHARP_TABLE_SIZE =
  sizeof(sharpDistances) / sizeof(sharpDistances[0]);

// ======================================
// Per-window state (reset every report)
// ======================================

// MaxSonar: raw pulses are kept so we can take the median,
// which rejects multipath / noise outliers that skew a mean.
const int PULSE_BUF_SIZE = SAMPLES_PER_REPORT + 5;
unsigned long pulseBuf[PULSE_BUF_SIZE];
int pulseCount = 0;

// Sharp IR: running sums for averaging
float sharpAdcSum = 0;
float sharpVoltageSum = 0;
float sharpDistanceSum = 0;
int sharpValidCount = 0;

int sampleCount = 0;

// D3C switch state (not reset per window)
bool switchPressed = false;        // debounced state
bool switchLastRaw = false;        // last raw reading
unsigned long switchChangeTime = 0;
unsigned long switchPressCount = 0;

unsigned long lastSampleTime = 0;
unsigned long lastReportTime = 0;

// ======================================
// Sensor Helpers
// ======================================

// Read ADC twice and discard the first reading
// (lets the ADC sample-and-hold settle)
int readAnalogStable(uint8_t pin) {
  analogRead(pin);
  delayMicroseconds(200);
  return analogRead(pin);
}

float adcToVoltage(int adc) {
  return adc * VREF / 1024.0f;
}

// Returns HIGH pulse width in us, or 0 on timeout
unsigned long readMaxSonarPulse() {
  return pulseIn(MAXSONAR_PIN, HIGH, PULSE_TIMEOUT_US);
}

// cm = (us / 147) inch * 2.54
float pulseToCm(unsigned long pulseUs) {
  if (pulseUs == 0) {
    return NAN;
  }
  return pulseUs * 2.54f / MAXSONAR_US_PER_INCH;
}

// Linear interpolation over the calibration table.
// Returns NAN outside the calibrated range.
float sharpVoltageToCm(float voltage) {
  if (voltage > sharpVoltages[0] ||
      voltage < sharpVoltages[SHARP_TABLE_SIZE - 1]) {
    return NAN;
  }

  for (int i = 0; i < SHARP_TABLE_SIZE - 1; i++) {
    float v1 = sharpVoltages[i];
    float v2 = sharpVoltages[i + 1];

    if (voltage <= v1 && voltage >= v2) {
      float ratio = (v1 - voltage) / (v1 - v2);
      return sharpDistances[i] +
             ratio * (sharpDistances[i + 1] - sharpDistances[i]);
    }
  }
  return NAN;
}

// Sorts buf in place (insertion sort; n is small) and returns median
unsigned long medianInPlace(unsigned long *buf, int n) {
  for (int i = 1; i < n; i++) {
    unsigned long key = buf[i];
    int j = i - 1;
    while (j >= 0 && buf[j] > key) {
      buf[j + 1] = buf[j];
      j--;
    }
    buf[j + 1] = key;
  }

  if (n % 2 == 1) {
    return buf[n / 2];
  }
  return (buf[n / 2 - 1] + buf[n / 2]) / 2;
}

// ======================================
// Sampling
// ======================================

void resetWindow() {
  pulseCount = 0;

  sharpAdcSum = 0;
  sharpVoltageSum = 0;
  sharpDistanceSum = 0;
  sharpValidCount = 0;

  sampleCount = 0;
}

void sampleSensors() {
  // MaxSonar: store valid pulses
  unsigned long pulse = readMaxSonarPulse();
  if (pulse > 0 && pulseCount < PULSE_BUF_SIZE) {
    pulseBuf[pulseCount++] = pulse;
  }

  // Sharp IR: accumulate ADC/voltage always, distance only if in range
  int adc = readAnalogStable(SHARP_PIN);
  float voltage = adcToVoltage(adc);
  float distance = sharpVoltageToCm(voltage);

  sharpAdcSum += adc;
  sharpVoltageSum += voltage;

  if (!isnan(distance)) {
    sharpDistanceSum += distance;
    sharpValidCount++;
  }

  sampleCount++;
}

// ======================================
// D3C Switch (debounced, event-driven)
// ======================================

bool readSwitchRaw() {
  bool level = digitalRead(SWITCH_PIN);
  return SWITCH_ACTIVE_LOW ? (level == LOW) : (level == HIGH);
}

// Call as often as possible; prints immediately on each change
void updateSwitch() {
  bool raw = readSwitchRaw();
  unsigned long now = millis();

  if (raw != switchLastRaw) {
    switchLastRaw = raw;
    switchChangeTime = now;
  }

  if (raw != switchPressed &&
      now - switchChangeTime >= SWITCH_DEBOUNCE_MS) {
    switchPressed = raw;

    if (switchPressed) {
      switchPressCount++;
    }

    Serial.print("[D3C] ");
    Serial.print(switchPressed ? "PRESSED" : "RELEASED");
    Serial.print("  t=");
    Serial.print(now);
    Serial.print(" ms  presses=");
    Serial.println(switchPressCount);
  }
}

// ======================================
// Reporting
// ======================================

void printSwitch() {
  Serial.println("--- D3C Switch ---");
  Serial.print("State: ");
  Serial.println(switchPressed ? "PRESSED" : "RELEASED");
  Serial.print("Press Count: ");
  Serial.println(switchPressCount);
}

void printMaxSonar() {
  Serial.println("--- MaxSonar Ultrasonic (PW) ---");

  // Raw pulses in arrival order (printed before sorting)
  Serial.print("Raw (us): ");
  for (int i = 0; i < pulseCount; i++) {
    Serial.print(pulseBuf[i]);
    Serial.print(' ');
  }
  Serial.println();

  if (pulseCount == 0) {
    Serial.println("Median Distance: No valid reading");
  } else {
    unsigned long median = medianInPlace(pulseBuf, pulseCount);

    Serial.print("Median Pulse Width: ");
    Serial.print(median);
    Serial.println(" us");

    Serial.print("Median Distance: ");
    Serial.print(pulseToCm(median), 2);
    Serial.println(" cm");

    // pulseBuf is now sorted
    Serial.print("Min/Max: ");
    Serial.print(pulseToCm(pulseBuf[0]), 1);
    Serial.print(" / ");
    Serial.print(pulseToCm(pulseBuf[pulseCount - 1]), 1);
    Serial.println(" cm");
  }

  Serial.print("Valid MaxSonar Samples: ");
  Serial.print(pulseCount);
  Serial.print("/");
  Serial.println(sampleCount);
}

void printSharp() {
  Serial.print("--- Sharp IR (");
  Serial.print(SHARP_NAME);
  Serial.println(") ---");

  Serial.print("Average ADC: ");
  Serial.println(sharpAdcSum / sampleCount, 2);

  Serial.print("Average Voltage: ");
  Serial.print(sharpVoltageSum / sampleCount, 3);
  Serial.println(" V");

  Serial.print("Average Distance: ");
  if (sharpValidCount == 0) {
    Serial.println("Out of range");
  } else {
    Serial.print(sharpDistanceSum / sharpValidCount, 2);
    Serial.println(" cm");
  }

  Serial.print("Valid Sharp Samples: ");
  Serial.print(sharpValidCount);
  Serial.print("/");
  Serial.println(sampleCount);
}

void report() {
  if (sampleCount == 0) {
    return;
  }

  Serial.println("================================");

  Serial.print("Time (s): ");
  Serial.println(millis() / 1000.0, 1);

  Serial.print("Samples: ");
  Serial.println(sampleCount);

  printMaxSonar();
  printSharp();
  printSwitch();

  Serial.println();
}

// ======================================
// Setup / Loop
// ======================================

void setup() {
  Serial.begin(115200);
  analogReference(DEFAULT);

  pinMode(MAXSONAR_PIN, INPUT);
  pinMode(SHARP_PIN, INPUT);
  pinMode(SWITCH_PIN, INPUT_PULLUP);

  // Start from the actual switch position (no fake event at boot)
  switchPressed = readSwitchRaw();
  switchLastRaw = switchPressed;

  resetWindow();

  // MaxSonar calibrates itself on power-up
  delay(500);

  lastSampleTime = millis();
  lastReportTime = lastSampleTime;

  Serial.println("Dual Sensor System Started");
  Serial.println("MaxSonar: Pulse Width on D2 (median filter)");
  Serial.print("Sharp IR: ");
  Serial.print(SHARP_NAME);
  Serial.println(" analog on A1");
  Serial.println("D3C Switch: D4 (INPUT_PULLUP, debounced)");
  Serial.print("Sampling: ");
  Serial.print(SAMPLE_INTERVAL_MS);
  Serial.println(" ms");
  Serial.print("Reporting: ");
  Serial.print(REPORT_INTERVAL_MS);
  Serial.println(" ms");
  Serial.println();
}

void loop() {
  updateSwitch();

  unsigned long now = millis();

  if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime += SAMPLE_INTERVAL_MS;
    sampleSensors();
  }

  if (now - lastReportTime >= REPORT_INTERVAL_MS) {
    lastReportTime += REPORT_INTERVAL_MS;
    report();
    resetWindow();
  }
}
