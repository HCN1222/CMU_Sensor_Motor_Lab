#ifndef SENSOR_MOTOR_HARDWARE_CONFIG_H
#define SENSOR_MOTOR_HARDWARE_CONFIG_H
// =============================================================================
// THE single place for physical parameters of the team's actual hardware.
// Edit here, then run `python firmware/generate_sketches.py` and re-upload.
//
// Every value marked PROVISIONAL is a conservative starting point or a
// manufacturer typical value, NOT a team measurement. See
// docs/HARDWARE_PARAMETERS.md for how to measure each one.
// =============================================================================
#include "controller_core.h"

namespace hw {

// ---- Safety gate ------------------------------------------------------------
// The Uno refuses ARM while this is false. Set true only after the wiring has
// been checked against hardware/WIRING.md and the motor parameters below have
// been reviewed (docs/HARDWARE_PARAMETERS.md, "Before the first ARM").
const bool HARDWARE_CONFIG_VERIFIED = true;

// ---- Per-subsystem calibration evidence --------------------------------------
// Set a flag true only when measured calibration + independent validation data
// exist in calibration/*.csv and the values below were updated from them.
const bool POT_CALIBRATED = false;
const bool IR_CALIBRATED = false;
const bool SONAR_CALIBRATED = false;
const bool ENCODER_CALIBRATED = false;
const bool SERVO_CALIBRATED = false;

// ---- Cytron SPG30-30K DC motor + encoder, Solarbotics L298 CMD ---------------
// x4 counts per OUTPUT shaft revolution. PROVISIONAL placeholder: measure it by
// turning the output shaft one full turn by hand while disarmed (RAW enc_counts).
const float ENCODER_COUNTS_PER_OUTPUT_REV = 360.0f;
// +1 if a positive DC_RPM makes RAW enc_counts increase, otherwise -1. PROVISIONAL.
const int8_t ENCODER_SIGN = -1;  // measured 2026-11-10: +DC_RPM spun clockwise but RAW counts decreased
// Nameplate 103 RPM at 12 V. GUI limit kept low for first tests. PROVISIONAL.
const float DC_MAX_RPM = 30.0f;
const float DC_SENSOR_RPM = 20.0f;           // speed used by the IR sensor rule
const float DC_MOVE_MAX_DEG = 1080.0f;       // largest single relative move
// Feed-forward ~ 255 PWM / 103 RPM = 2.5; start lower so PID closes the gap. PROVISIONAL.
const float DC_VELOCITY_KFF = 1.5f;
const float DC_VELOCITY_KP = 2.0f, DC_VELOCITY_KI = 5.0f, DC_VELOCITY_KD = 0.0f;  // PROVISIONAL
const float DC_POSITION_KP = 0.6f, DC_POSITION_KI = 0.0f, DC_POSITION_KD = 0.02f; // PROVISIONAL
const float DC_POSITION_TOLERANCE_DEG = 2.0f;
const float DC_SETTLE_RPM = 2.0f;
const float DC_STALL_PWM = 120.0f;           // |PWM| above this with no encoder edge...
const uint32_t DC_STALL_MS = 1000;           // ...for this long disarms (ENCODER_STALL)
const uint32_t DC_POSITION_TIMEOUT_MS = 15000;

// ---- Mercury SM-42BYG011-25 stepper + EasyDriver v4.4 -------------------------
const float STEPPER_FULL_STEPS_PER_REV = 200.0f;  // 1.8 deg nominal
const uint8_t STEPPER_MICROSTEPS = 1;             // MS1 = MS2 = GND -> full step
const uint32_t STEPPER_STEP_INTERVAL_US = 5000;   // 200 steps/s = 1 rev/s
const float STEPPER_SENSOR_MOVE_DEG = 90.0f;      // slot-sensor rule
const float STEPPER_MOVE_MAX_DEG = 1080.0f;

// ---- Hitec HS-225BB servo -------------------------------------------------------
// PROVISIONAL conservative window around the 1500 us centre. Measure the real
// end points (docs/HARDWARE_PARAMETERS.md) before widening.
const float SERVO_MIN_DEG = 0.0f, SERVO_MAX_DEG = 60.0f;
const int16_t SERVO_MIN_US = 1200, SERVO_MAX_US = 1800;

// ---- Bourns 3386 potentiometer ----------------------------------------------
// ADC at both ends of the usable travel; full span until measured. PROVISIONAL.
const int16_t POT_ADC_MIN = 0, POT_ADC_MAX = 1023;
// Angle between POT_ADC_MIN and POT_ADC_MAX, measured with a protractor.
// 0 = not measured yet: pot_deg is reported invalid and only pot_pct is shown.
const float POT_TRAVEL_DEG = 0.0f;

// ---- Sharp GP2Y0A02YK0F (20-150 cm) -----------------------------------------
// PROVISIONAL: manufacturer typical curve. Replace with the team's measured
// table (calibration/analyze.py prints a suggestion). ADC strictly decreasing.
const int16_t IR_TABLE_ADC[] = {502, 379, 287, 236, 201, 156, 121, 100, 82};
const float IR_TABLE_CM[] = {20, 30, 40, 50, 60, 80, 100, 120, 150};
// Sensor rule: DC stops below IR_STOP_CM and restarts only above IR_START_CM.
const float IR_STOP_CM = 35.0f;
const float IR_START_CM = 45.0f;

// ---- MaxBotix LV-MaxSonar-EZ0 (AN output) -------------------------------------
// Datasheet: Vcc/512 per inch; with ADC Vref = Vcc -> 2 counts/inch = 1.27 cm/count.
const float SONAR_CM_PER_ADC = 1.27f;
const float SONAR_MIN_CM = 15.24f;   // 6 in: closer targets still read ~6 in
const float SONAR_MAX_CM = 645.0f;   // 254 in

// ---- Inputs and safety -------------------------------------------------------
const uint32_t BUTTON_DEBOUNCE_MS = 30;
const uint32_t SLOT_DEBOUNCE_MS = 10;
const uint32_t WATCHDOG_MS = 1500;   // no accepted command for this long -> STOP

inline lab::Config makeHardwareConfig() {
  lab::Config c;
  c.encoderCountsPerOutputRev = ENCODER_COUNTS_PER_OUTPUT_REV;
  c.encoderSign = ENCODER_SIGN;
  c.maxRpm = DC_MAX_RPM; c.sensorRpm = DC_SENSOR_RPM; c.moveMaxDegrees = DC_MOVE_MAX_DEG;
  c.velocityKff = DC_VELOCITY_KFF;
  c.velocityKp = DC_VELOCITY_KP; c.velocityKi = DC_VELOCITY_KI; c.velocityKd = DC_VELOCITY_KD;
  c.positionKp = DC_POSITION_KP; c.positionKi = DC_POSITION_KI; c.positionKd = DC_POSITION_KD;
  c.positionToleranceDeg = DC_POSITION_TOLERANCE_DEG; c.settleRpm = DC_SETTLE_RPM;
  c.stallPwm = DC_STALL_PWM; c.stallMs = DC_STALL_MS; c.positionTimeoutMs = DC_POSITION_TIMEOUT_MS;
  c.stepsPerOutputRev = STEPPER_FULL_STEPS_PER_REV * STEPPER_MICROSTEPS;
  c.stepIntervalUs = STEPPER_STEP_INTERVAL_US;
  c.sensorStepDegrees = STEPPER_SENSOR_MOVE_DEG; c.stepMoveMaxDegrees = STEPPER_MOVE_MAX_DEG;
  c.servoMinDegrees = SERVO_MIN_DEG; c.servoMaxDegrees = SERVO_MAX_DEG;
  c.servoMinUs = SERVO_MIN_US; c.servoMaxUs = SERVO_MAX_US;
  c.potAdcMin = POT_ADC_MIN; c.potAdcMax = POT_ADC_MAX; c.potTravelDegrees = POT_TRAVEL_DEG;
  c.irAdc = IR_TABLE_ADC; c.irCm = IR_TABLE_CM;
  c.irPoints = uint8_t(sizeof(IR_TABLE_ADC) / sizeof(IR_TABLE_ADC[0]));
  c.irStopCm = IR_STOP_CM; c.irStartCm = IR_START_CM;
  c.sonarCmPerAdc = SONAR_CM_PER_ADC; c.sonarMinCm = SONAR_MIN_CM; c.sonarMaxCm = SONAR_MAX_CM;
  c.buttonDebounceMs = BUTTON_DEBOUNCE_MS; c.slotDebounceMs = SLOT_DEBOUNCE_MS; c.watchdogMs = WATCHDOG_MS;
  c.hardwareVerified = HARDWARE_CONFIG_VERIFIED;
  c.calibratedMask = uint8_t((POT_CALIBRATED ? lab::CAL_POT : 0) | (IR_CALIBRATED ? lab::CAL_IR : 0) |
                             (SONAR_CALIBRATED ? lab::CAL_SONAR : 0) | (ENCODER_CALIBRATED ? lab::CAL_ENCODER : 0) |
                             (SERVO_CALIBRATED ? lab::CAL_SERVO : 0));
  return c;
}

}  // namespace hw
#endif
