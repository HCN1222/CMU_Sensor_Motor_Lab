// Behavioral checks of the ACTUAL shared firmware core and the ACTUAL hardware
// configuration header. Motor behaviour uses a synthetic first-order plant: this
// proves control logic and signs, NOT physical tuning.
#include "../../firmware/controller_core.h"
#include "../../firmware/hardware_config.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>

static int checks = 0;
static void check(bool result, const char *name) {
  ++checks;
  if (!result) { std::fprintf(stderr, "FAIL: %s\n", name); std::exit(1); }
}
static bool near(float a, float b, float tolerance = 0.01f) { return std::fabs(a - b) <= tolerance; }
static lab::Config verifiedConfig() { lab::Config c; c.hardwareVerified = true; return c; }
static lab::Ack send(lab::Controller &c, unsigned seq, const char *verb, float value, unsigned now = 0, int32_t counts = 0) {
  char line[80]; std::snprintf(line, sizeof(line), "CMD,%u,%s,%.7g", seq, verb, double(value)); return c.command(line, now, counts);
}
static lab::Ack raw(lab::Controller &c, const char *input, unsigned now = 0) {
  char line[120]; std::strncpy(line, input, sizeof(line) - 1); line[sizeof(line) - 1] = 0; return c.command(line, now, 0);
}
static std::vector<std::string> tokens(const char *line) {
  std::vector<std::string> out; std::string current;
  for (const char *p = line; *p && *p != '\n'; ++p) { if (*p == ',') { out.push_back(current); current.clear(); } else current += *p; }
  out.push_back(current); return out;
}
// Feed identical sensor inputs for `samples` sensor periods (20 ms each).
static unsigned feed(lab::Controller &c, unsigned now, int samples, int pot, int ir, int sonar, bool slot = false, bool button = false) {
  for (int i = 0; i < samples; ++i) { c.sensors(pot, ir, sonar, slot, button, now); now += 20; }
  return now;
}

static void hardwareConfiguration() {
  const lab::Config hwc = hw::makeHardwareConfig();
  check(lab::configError(hwc) == 0, "hardware_config.h passes configuration validation");
  check(!hwc.hardwareVerified, "hardware gate ships closed: ARM refused until a person verifies wiring");
  check(hwc.calibratedMask == 0, "no subsystem is marked calibrated without measured data");
  check(hwc.irStopCm >= 20 && hwc.irStartCm <= 150 && hwc.irStartCm > hwc.irStopCm, "IR hysteresis lies inside the 20-150 cm GP2Y0A02 range");
  check(near(hwc.irCm[0], 20) && near(hwc.irCm[hwc.irPoints - 1], 150), "IR table spans 20-150 cm (GP2Y0A02, not the 10-80 cm GP2Y0A21)");
  check(near(hwc.stepsPerOutputRev, 200), "stepper full-step mode is 200 steps/rev");
  check(hwc.potTravelDegrees == 0, "pot travel is not assumed (0 = unmeasured)");
  lab::Controller c(hwc);
  check(!send(c, 1, "ARM", 0).ok, "real hardware config refuses ARM while unverified");
  check(!std::strcmp(send(c, 2, "ARM", 0).reason, "CONFIG_REQUIRED"), "refusal reason tells the user what to do");
  feed(c, 0, 1, 512, 287, 100);
  check(c.potDegrees == lab::INVALID && near(c.potPercent, 50.05f, 0.05f), "unmeasured pot reports percentage only, degrees invalid");
  check(near(c.servoDegrees, 30) && near(c.servoMicroseconds(), 1500), "servo starts mid-travel at the 1500 us centre");
  c.servoDegrees = hwc.servoMinDegrees; check(near(c.servoMicroseconds(), hwc.servoMinUs), "servo minimum angle maps to minimum pulse");
  c.servoDegrees = hwc.servoMaxDegrees; check(near(c.servoMicroseconds(), hwc.servoMaxUs), "servo maximum angle maps to maximum pulse");
  lab::Config broken = verifiedConfig(); broken.irStartCm = 30; broken.irStopCm = 40;
  check(lab::configError(broken) != 0, "inverted IR hysteresis is rejected");
  broken = verifiedConfig(); static const int16_t badAdc[] = {100, 200}; static const float badCm[] = {20, 30};
  broken.irAdc = badAdc; broken.irCm = badCm; broken.irPoints = 2;
  check(lab::configError(broken) != 0, "non-monotonic IR table is rejected");
  lab::Controller invalid(broken);
  check(!std::strcmp(send(invalid, 1, "ARM", 0).reason, "CONFIG_INVALID"), "invalid configuration cannot arm");
}

static void conversions() {
  const lab::Config c;
  check(near(lab::irDistanceFromAdc(c, 502), 20) && near(lab::irDistanceFromAdc(c, 82), 150), "IR table end points convert exactly");
  check(near(lab::irDistanceFromAdc(c, 287), 40), "IR table point converts exactly");
  check(near(lab::irDistanceFromAdc(c, 333), 35), "IR interpolates linearly between points");
  check(lab::irDistanceFromAdc(c, 503) == lab::TOO_CLOSE, "IR above the 20 cm point is TOO_CLOSE, not a distance");
  check(lab::irDistanceFromAdc(c, 81) == lab::INVALID, "IR beyond 150 cm / no target is INVALID, not far away");
  check(lab::irDistanceFromAdc(c, 0) == lab::INVALID, "IR disconnected reads INVALID");
  check(near(lab::sonarDistanceFromAdc(c, 79), 100.33f), "sonar AN: 1.27 cm per count (Vcc/512 per inch)");
  check(lab::sonarDistanceFromAdc(c, 12) == lab::TOO_CLOSE, "sonar at its 6 inch floor reports TOO_CLOSE");
  check(near(lab::sonarDistanceFromAdc(c, 13), 16.51f), "sonar just above the floor is a distance");
  check(lab::sonarDistanceFromAdc(c, 0) == lab::INVALID, "sonar 0 V (disconnected) is INVALID, not too close");
  check(lab::sonarDistanceFromAdc(c, 600) == lab::INVALID, "sonar beyond 645 cm is INVALID");
}

static void parserAndCommands() {
  lab::Controller physical;
  check(!send(physical, 1, "ARM", 0).ok, "unverified hardware refuses ARM");
  lab::Config bad = verifiedConfig(); bad.encoderCountsPerOutputRev = 0;
  lab::Controller invalidConfig(bad);
  check(!send(invalidConfig, 1, "ARM", 0).ok, "zero encoder counts/rev cannot arm");
  invalidConfig.control(20, 10);
  check(std::isfinite(invalidConfig.dcDegrees), "invalid config does not produce nonfinite telemetry");
  lab::Config physicalServo = verifiedConfig(); physicalServo.servoMaxDegrees = 80;
  lab::Controller centered(physicalServo);
  check(centered.servoDegrees == 40, "servo initializes at configured travel midpoint");
  lab::Controller c(verifiedConfig());
  check(!send(c, 1, "DC_RPM", 10).ok, "motion rejected while disarmed");
  check(send(c, 2, "ARM", 0).ok && c.armed, "explicit ARM enables");
  check(send(c, 3, "SERVO", 45).ok && c.servoDegrees == 45, "servo target accepted");
  check(!send(c, 4, "SERVO", 181).ok && c.servoDegrees == 45, "servo bounds enforced");
  check(!send(c, 5, "DC_RPM", 121).ok, "speed bounds enforced");
  check(!send(c, 6, "DC_MOVE", 3601).ok, "relative angle bounds enforced");
  const char *invalid[] = {"CMD,7,DC_RPM,nan", "CMD,7,DC_RPM,inf", "CMD,7,DC_RPM,1x", "CMD,7,DC_RPM,",
      "CMD,,DC_RPM,3", "CMD,7,DC_RPM,3,4", "CMD,4294967296,ARM,0", "CMD,-1,ARM,0", "CMD,7,MODE, 1", "CMD,7,,0"};
  for (unsigned i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i) check(!raw(c, invalid[i]).ok, "malformed/nonfinite command rejected");
  check(send(c, 8, "DC_MOVE", 90, 0, 20).ok && c.dcTarget == 110, "DC move uses current encoder position");
  check(send(c, 8, "DC_MOVE", 90, 0, 80).ok && c.dcTarget == 110, "duplicate relative move is not executed again");
  check(send(c, 9, "PING", 0).ok, "heartbeat accepted");
  check(!send(c, 8, "DC_MOVE", 90, 0, 80).ok && c.dcTarget == 110, "old relative move remains rejected after heartbeat");
  check(!send(c, 10, "ZERO", 0).ok, "ZERO cannot alter coordinates while armed");
  check(send(c, 11, "MODE", 1).ok && c.dcTarget == 0 && c.pwm == 0, "mode switch cancels pending DC motion");
  check(!send(c, 12, "DC_RPM", 20).ok, "GUI motion blocked in sensor mode");
  check(send(c, 13, "STOP", 0).ok && !c.armed, "STOP disarms");
  check(send(c, 14, "ZERO", 0, 10, 90).ok && c.encoderZero == 90, "ZERO while disarmed establishes reference");
  check(send(c, 15, "MODE", 0).ok, "MODE may change while disarmed");
  lab::Config tight = verifiedConfig(); tight.moveMaxDegrees = 720; tight.stepMoveMaxDegrees = 360; tight.maxRpm = 30;
  lab::Controller limited(tight); send(limited, 1, "ARM", 0);
  check(!send(limited, 2, "DC_MOVE", 721).ok && !send(limited, 3, "STEP_MOVE", -361).ok && !send(limited, 4, "DC_RPM", -31).ok,
        "configured motion limits are enforced by firmware");
}

static void stepper() {
  lab::Controller c(verifiedConfig());
  send(c, 1, "ARM", 0);
  check(send(c, 2, "STEP_MOVE", 90).ok, "stepper accepts positive relative angle");
  check(c.stepTarget == 50, "90 degrees becomes 50 full steps at 200 steps/rev");
  check(!send(c, 3, "STEP_MOVE", 90).ok, "busy stepper rejects hidden command queue");
  int emitted = 0; for (unsigned us = 0; us <= 300000; us += 1000) emitted += c.step(us);
  check(emitted == 50 && !c.stepBusy() && c.stepDegrees() == 90, "nonblocking pulses execute requested 90 degrees");
  check(send(c, 4, "STEP_MOVE", -90).ok, "negative step request accepted");
  for (unsigned us = 301000; us <= 600000; us += 1000) c.step(us);
  check(c.stepPosition == 0 && c.stepDegrees() == 0, "negative rotation returns to reference");
  check(send(c, 5, "STEP_MOVE", 1).ok && near(c.stepTargetDegrees(), 1.8f, 0.001f), "unachievable angle rounded to a whole step and reported");
  check(send(c, 6, "STOP", 0).ok && c.step(700000) == 0 && !c.stepBusy(), "STOP cancels pending steps");
  send(c, 7, "ARM", 0); send(c, 8, "STEP_MOVE", 180);
  c.step(800000); c.step(806000);
  check(send(c, 9, "MODE", 1).ok && !c.stepBusy() && c.stepPosition == 2, "mode switch cancels the remaining steps immediately");
  lab::Config slow = verifiedConfig(); slow.stepIntervalUs = 10000;
  lab::Controller s(slow); send(s, 1, "ARM", 0); send(s, 2, "STEP_MOVE", 90);
  int pulses = 0; for (unsigned us = 1000; us <= 100000; us += 1000) pulses += s.step(us);
  check(pulses == 10, "configured step interval sets the pulse rate");
}

static void sensorMode() {
  lab::Controller c(verifiedConfig());
  unsigned t = feed(c, 0, 1, 512, 156, 100);
  send(c, 1, "ARM", 0, t); send(c, 2, "MODE", 1, t);
  t = feed(c, t, 1, 1023, 156, 100);
  check(c.servoDegrees == 180, "pot full scale maps to configured servo maximum");
  check(c.dcTarget == 0, "DC stays stopped until the IR filter window is full");
  t = feed(c, t, 5, 1023, 156, 100);
  check(c.dcTarget == 20 && c.irMotorRunning(), "far IR (80 cm) starts configured 20 RPM");
  t = feed(c, t, 6, 0, 400, 100);
  check(c.dcTarget == 0 && c.servoDegrees == 0, "near IR (~28 cm) stops DC and pot zero sets minimum");
  t = feed(c, t, 6, 512, 287, 100);
  check(c.dcTarget == 0, "IR hysteresis holds stopped state at 40 cm (between 35 and 45)");
  t = feed(c, t, 6, 512, 156, 100);
  check(c.dcTarget == 20, "IR resumes beyond far threshold");
  t = feed(c, t, 6, 512, 287, 100);
  check(c.dcTarget == 20, "IR hysteresis holds running state at 40 cm");
  t = feed(c, t, 1, 512, 1023, 100);
  check(c.irCm == lab::TOO_CLOSE && c.dcTarget == 0, "too-close IR fails to stopped state");
  t = feed(c, t, 6, 512, 156, 100);
  t = feed(c, t, 1, 512, 40, 100);
  check(c.irCm == lab::INVALID && c.dcTarget == 0, "no-target IR is NOT treated as safe far distance");
  t = feed(c, t, 3, 512, 156, 100);
  check(c.irCm == lab::INVALID && c.dcTarget == 0, "after an invalid sample the filter refills before restarting (no stale value)");
  // Slot sensor -> stepper.
  t = feed(c, t, 2, 512, 156, 100, true);
  check(c.slotCount == 1 && c.stepTarget == 50, "new blocked edge counts once and triggers 90 degrees");
  t = feed(c, t, 15, 512, 156, 100, true);
  check(c.slotCount == 1 && c.stepTarget == 50, "holding the card does not repeat stepper motion");
  t = feed(c, t, 2, 512, 156, 100, false);
  t = feed(c, t, 2, 512, 156, 100, true);
  check(c.slotCount == 2 && c.slotIgnored == 1 && c.stepTarget == 50, "new obstruction while stepper busy is counted as ignored, not queued");
  // Button bounce: shorter than 30 ms in either unstable state.
  c.sensors(512, 156, 100, true, true, t); c.sensors(512, 156, 100, true, false, t + 10);
  c.sensors(512, 156, 100, true, true, t + 20); c.sensors(512, 156, 100, true, true, t + 40);
  check(c.mode == lab::SENSOR, "button bounce does not toggle early");
  c.sensors(512, 156, 100, true, true, t + 60);
  check(c.mode == lab::GUI && !c.stepBusy() && c.dcTarget == 0, "debounced button toggles once and cancels movement");
  feed(c, t + 80, 20, 512, 156, 100, true, true);
  check(c.mode == lab::GUI, "held button never repeatedly toggles");
  check(near(c.sonarCm, 127), "sonar ADC converted using AN scaling");
  check(near(c.potDegrees, 150.1466f), "pot angle reflects its configured travel");
}

static void sensorFilters() {
  lab::Controller c(verifiedConfig());
  float rawVariation = 0, filteredVariation = 0, prevRaw = 0, prevFiltered = 0;
  for (unsigned i = 0; i < 100; ++i) {
    c.sensors(512, (i % 2) ? 120 : 130, 100, false, false, i * 20);
    if (i > 10) { rawVariation += std::fabs(c.irRawCm - prevRaw); filteredVariation += std::fabs(c.irCm - prevFiltered); }
    prevRaw = c.irRawCm; prevFiltered = c.irCm;
  }
  check(filteredVariation < rawVariation * 0.3f, "IR moving average reduces alternating synthetic noise");
  lab::Controller s(verifiedConfig());
  const int sonar[] = {79, 79, 12, 79, 400, 79, 79, 12, 79};  // 3 multipath/short-echo outliers among 9
  for (unsigned i = 0; i < 9; ++i) s.sensors(512, 156, sonar[i], false, false, i * 20);
  check(near(s.sonarCm, 100.33f), "sonar median rejects outliers that would skew a mean");
  for (unsigned i = 9; i < 18; ++i) s.sensors(512, 156, 12, false, false, i * 20);
  check(s.sonarCm == lab::TOO_CLOSE, "sustained 6 inch floor reports TOO_CLOSE");
  lab::Config potCfg = verifiedConfig(); potCfg.potAdcMin = 100; potCfg.potAdcMax = 900; potCfg.potTravelDegrees = 270;
  lab::Controller p(potCfg);
  p.sensors(500, 156, 79, false, false, 0);
  check(near(p.potPercent, 50) && near(p.potDegrees, 135), "pot uses measured ADC end points and travel");
  p.sensors(50, 156, 79, false, false, 20);
  check(near(p.potPercent, 0) && near(p.potDegrees, 0), "pot below its end point clamps to 0");
}

static void encoderSignAndRaw() {
  lab::Config cfg = verifiedConfig(); cfg.encoderSign = -1;
  lab::Controller c(cfg);
  c.control(0, 0); c.control(100, 360);
  check(near(c.dcDegrees, -360) && c.dcRpm < 0, "encoder sign flips degrees and RPM");
  check(c.encoderRaw == 360, "raw encoder count is kept unsigned by CPR/sign for CPR measurement");
  char line[192]; lab::formatRaw(c, 100, line, sizeof(line));
  std::vector<std::string> t = tokens(line);
  check(t.size() == 9 && t[7] == "360", "RAW frame carries the raw x4 encoder count");
  send(c, 1, "ZERO", 0, 100, 360); c.control(200, 360);
  check(near(c.dcDegrees, 0) && c.encoderRaw == 360, "ZERO moves the reference, raw count unchanged");
}

static void watchdogAndWrap() {
  lab::Controller c(verifiedConfig());
  send(c, 1, "ARM", 0, 100); send(c, 2, "DC_RPM", 20, 100);
  c.control(1600, 0); check(c.armed, "watchdog permits exact timeout boundary");
  c.control(1601, 0); check(!c.armed && c.pwm == 0 && !std::strcmp(c.fault, "WATCHDOG"), "watchdog disarms after 1500 ms contact loss and says why");
  check(send(c, 3, "ARM", 0, 1700).ok && !std::strcmp(c.fault, "NONE"), "re-ARM clears the stop reason");
  lab::Controller wrap(verifiedConfig());
  send(wrap, 1, "ARM", 0, UINT32_MAX - 500);
  wrap.control(400, 0); check(wrap.armed, "watchdog elapsed time survives millis wrap");
  wrap.control(1100, 0); check(!wrap.armed, "watchdog expires correctly after wrap");
  lab::Controller seq(verifiedConfig());
  check(raw(seq, "CMD,4294967294,ARM,0").ok, "near-wrap sequence accepted");
  check(raw(seq, "CMD,1,PING,0").ok, "sequence monotonicity survives unsigned wrap");
}

static void stallAndTimeout() {
  lab::Controller c(verifiedConfig());
  unsigned seq = 1; send(c, seq++, "ARM", 0); send(c, seq++, "DC_RPM", 20);
  unsigned now = 0;
  for (; now <= 4000 && c.armed; now += 20) { if (now % 500 == 0) send(c, seq++, "PING", 0, now); c.control(now, 0); }
  check(!c.armed && c.pwm == 0 && !std::strcmp(c.fault, "ENCODER_STALL"), "strong drive with a frozen encoder disarms (ENCODER_STALL)");
  lab::Config cfg = verifiedConfig(); cfg.positionTimeoutMs = 2000; cfg.stallPwm = 300;  // stall check off
  lab::Controller p(cfg); seq = 1; send(p, seq++, "ARM", 0); send(p, seq++, "DC_MOVE", 90);
  for (now = 0; now <= 2600; now += 20) { if (now % 500 == 0) send(p, seq++, "PING", 0, now); p.control(now, 0); }
  check(p.armed && p.dcControl == lab::RPM && p.dcTarget == 0 && p.pwm == 0 && !std::strcmp(p.fault, "POSITION_TIMEOUT"),
        "unfinished DC_MOVE times out to a stopped, still-armed state");
  // Wrong encoder sign: positive PWM turns the shaft but the encoder reports the opposite direction.
  lab::Controller w(verifiedConfig()); seq = 1; send(w, seq++, "ARM", 0); send(w, seq++, "DC_RPM", 10);
  float rpm = 0, deg = 0;
  for (now = 0; now <= 4000 && w.armed; now += 20) {
    if (now % 500 == 0) send(w, seq++, "PING", 0, now);
    rpm += (w.pwm / 255.0f * 120 - rpm) * (0.02f / 0.15f); deg += rpm * 6 * 0.02f;
    w.control(now, int32_t(-deg));  // inverted feedback
  }
  check(!w.armed && w.pwm == 0 && !std::strcmp(w.fault, "ENCODER_DIRECTION"), "inverted encoder feedback is caught (ENCODER_DIRECTION) instead of running away");
  check(now < 2500, "runaway is stopped within about stallMs after saturating");
  lab::Config ff = verifiedConfig(); ff.velocityKff = 2.0f;
  lab::Controller f(ff); send(f, 1, "ARM", 0); send(f, 2, "DC_RPM", 20); f.control(0, 0); f.control(20, 0);
  check(f.pwm >= 40, "velocity feed-forward contributes Kff*target immediately");
}

static void formatting() {
  char line[192];
  lab::Controller c(verifiedConfig());
  c.potDegrees = -0.001f; c.irRawCm = 1.25f; c.irCm = NAN; c.sonarCm = 0.999f; c.dcDegrees = -90; c.dcRpm = -12.5f;
  size_t n = lab::formatState(c, 1234, line, sizeof(line));
  std::vector<std::string> t = tokens(line);
  check(n > 0 && t.size() == 21 && t[0] == "STATE", "STATE frame has exactly 21 fields");
  check(t[3] == "0.00" && t[5] == "1.25" && t[6] == "-1" && t[7] == "1.00", "fixed-point text: rounding, no negative zero, NaN never emitted");
  check(t[11] == "-90.00" && t[12] == "-12.50" && t[20] == "NONE", "negative values and fault code formatted");
  // Worst case: every numeric field at an extreme. Must still fit the Uno's 192-byte line buffer.
  c.dcDegrees = -2.0e9f; c.dcTarget = -2.0e9f; c.stepPosition = INT32_MIN + 1; c.stepTarget = INT32_MIN + 2;
  c.slotCount = UINT32_MAX; c.slotIgnored = UINT32_MAX; c.fault = "ENCODER_DIRECTION"; c.dcControl = lab::POSITION; c.dcRpm = -9999.99f;
  n = lab::formatState(c, UINT32_MAX, line, sizeof(line));
  check(n > 0 && n < sizeof(line), "longest possible STATE line fits the 192-byte firmware buffer");
  c.encoderRaw = INT32_MIN; c.potAdc = 1023;
  lab::formatRaw(c, UINT32_MAX, line, sizeof(line)); t = tokens(line);
  check(t.size() == 9 && t[7] == "-2147483648", "RAW handles INT32_MIN encoder counts");
  lab::formatConfig(hw::makeHardwareConfig(), line, sizeof(line)); t = tokens(line);
  check(t.size() == 21 && t[0] == "CONFIG" && t[1] == "2" && t[19] == "0" && t[20] == "0", "CONFIG frame: 21 fields, protocol 2, gate and calibration flags");
  const lab::Ack ack = {7, false, "RANGE"}; lab::formatAck(ack, line, sizeof(line));
  check(!std::strcmp(line, "ACK,7,ERR,RANGE\n"), "ACK frame text");
  char tiny[8]; check(lab::formatState(c, 1, tiny, sizeof(tiny)) == 0 && tiny[0] == 0, "overflow yields an empty line, never a truncated frame");
}

// Deliberately simple first-order mathematical plant, not a real motor model.
struct Plant {
  float rpm, degrees;
  Plant() : rpm(0), degrees(0) {}
  int32_t counts(const lab::Controller &c) const { return int32_t(degrees * c.cfg.encoderCountsPerOutputRev / 360 * c.cfg.encoderSign); }
  void tick(lab::Controller &c, unsigned ms) {
    const float target = c.pwm / 255.0f * 120;
    rpm += (target - rpm) * (0.02f / 0.15f); degrees += rpm * 6 * 0.02f; c.control(ms, counts(c));
  }
};
static void closedLoop(const lab::Config &config, const char *label) {
  lab::Controller c(config); Plant p; unsigned seq = 1, now = 0;
  send(c, seq++, "ARM", 0); send(c, seq++, "DC_RPM", 30); c.control(0, 0);
  for (now = 20; now <= 6000; now += 20) { if (now % 500 == 0) send(c, seq++, "PING", 0, now, p.counts(c)); p.tick(c, now); }
  check(near(c.dcRpm, 30, 2), "velocity PID settles near +30 RPM with synthetic plant");
  send(c, seq++, "DC_RPM", -30, now, p.counts(c));
  for (; now <= 12000; now += 20) { if (now % 500 == 0) send(c, seq++, "PING", 0, now, p.counts(c)); p.tick(c, now); }
  check(near(c.dcRpm, -30, 2), "velocity PID reverses and settles near -30 RPM");
  send(c, seq++, "DC_RPM", 0, now, p.counts(c));
  for (; now <= 14000; now += 20) { if (now % 500 == 0) send(c, seq++, "PING", 0, now, p.counts(c)); p.tick(c, now); }
  send(c, seq++, "DC_MOVE", 90, now, p.counts(c)); const float target = c.dcTarget;
  for (; now <= 22000; now += 20) { if (now % 500 == 0) send(c, seq++, "PING", 0, now, p.counts(c)); p.tick(c, now); }
  check(std::fabs(c.dcDegrees - target) < 2.5f && std::fabs(c.dcRpm) < 2, "cascaded position/velocity PID settles 90 degree relative move");
  send(c, seq++, "DC_MOVE", -90, now, p.counts(c)); const float reverseTarget = c.dcTarget;
  for (; now <= 30000; now += 20) { if (now % 500 == 0) send(c, seq++, "PING", 0, now, p.counts(c)); p.tick(c, now); }
  check(std::fabs(c.dcDegrees - reverseTarget) < 2.5f, "position PID supports reverse relative move");
  check(c.armed && !std::strcmp(c.fault, "NONE"), "no stall/timeout fault during normal synthetic motion");
  std::printf("Synthetic plant (%s): position_error=%.3f deg, speed=%.3f RPM\n", label, double(c.dcDegrees - reverseTarget), double(c.dcRpm));
}

int main() {
  hardwareConfiguration(); conversions(); parserAndCommands(); stepper(); sensorMode(); sensorFilters();
  encoderSignAndRaw(); watchdogAndWrap(); stallAndTimeout(); formatting();
  lab::Config generic = verifiedConfig(); generic.encoderCountsPerOutputRev = 1440;
  closedLoop(generic, "generic gains");
  lab::Config hardware = hw::makeHardwareConfig(); hardware.hardwareVerified = true; hardware.maxRpm = 120;
  hardware.encoderCountsPerOutputRev = 1440; hardware.encoderSign = -1;
  closedLoop(hardware, "hardware_config gains, sign -1");
  std::printf("PASS: %d behavioral checks of actual shared controller core\n", checks);
  std::printf("Scope: host logic + synthetic plant only; no physical motor/sensor calibration or tuning claimed.\n");
  return 0;
}
