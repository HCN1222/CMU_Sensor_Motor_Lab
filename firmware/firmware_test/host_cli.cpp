// Real-time stdin/stdout stand-in for the Uno around the ACTUAL firmware core and
// the ACTUAL frame formatters. Uses a mathematical DC plant and fixed synthetic
// sensor inputs; it is NOT hardware evidence. Portable C++11 (Windows/Linux/macOS).
#include "../../firmware/controller_core.h"
#include <atomic>
#include <chrono>
#include <cstdio>
#include <deque>
#include <mutex>
#include <string>
#include <thread>

static std::mutex inputMutex;
static std::deque<std::string> inputLines;
static std::atomic<bool> inputClosed(false);

static void readStdin() {
  std::string line; bool overflow = false; int ch;
  while ((ch = std::getchar()) != EOF) {
    if (ch == '\r') continue;
    if (ch == '\n') {
      std::lock_guard<std::mutex> lock(inputMutex);
      inputLines.push_back(overflow ? std::string("\x01") : line);
      line.clear(); overflow = false;
    } else if (!overflow) {
      if (ch < 32 || ch > 126 || line.size() >= 79) { overflow = true; line.clear(); }
      else line += char(ch);
    }
  }
  inputClosed = true;
}

static void emit(const char *line, size_t length) { if (length) std::fwrite(line, 1, length, stdout); }

int main() {
  lab::Config cfg; cfg.hardwareVerified = true; cfg.encoderCountsPerOutputRev = 1440;
  cfg.servoMaxDegrees = 60; cfg.servoMinUs = 1200; cfg.servoMaxUs = 1800; cfg.maxRpm = 60;  // hardware-like limits
  lab::Controller c(cfg);
  float plantRpm = 0, plantDegrees = 0;
  int32_t encoder = 0;
  char out[192];
  std::thread reader(readStdin);
  reader.detach();
  const auto start = std::chrono::steady_clock::now();
  unsigned lastTick = 0, lastPrint = 0, lastConfig = 0;
  std::fputs("INFO,HOST_SYNTHETIC_PLANT_NOT_HARDWARE\n", stdout);
  emit(out, lab::formatConfig(c.cfg, out, sizeof(out)));
  std::fflush(stdout);
  while (true) {
    std::this_thread::sleep_for(std::chrono::milliseconds(2));
    const unsigned now = unsigned(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count());
    // Advance old simulation ticks before accepting commands stamped with now.
    while (now - lastTick >= 20) {
      lastTick += 20;
      plantRpm += (c.pwm / 255.0f * 120.0f - plantRpm) * (0.02f / 0.15f);
      plantDegrees += plantRpm * 6.0f * 0.02f;
      encoder = int32_t(plantDegrees * cfg.encoderCountsPerOutputRev / 360.0f);
      // Fixed synthetic inputs: pot mid, IR 60 cm (ADC 201), sonar ~100 cm (ADC 79).
      c.sensors(512, 201, 79, false, false, lastTick);
      c.control(lastTick, encoder);
    }
    std::deque<std::string> pending;
    { std::lock_guard<std::mutex> lock(inputMutex); pending.swap(inputLines); }
    for (std::string &line : pending) {
      if (line == "\x01") { const lab::Ack ack = {0, false, "LINE_TOO_LONG"}; emit(out, lab::formatAck(ack, out, sizeof(out))); continue; }
      if (line.empty()) continue;
      char buffer[80]; line.copy(buffer, sizeof(buffer) - 1); buffer[line.size()] = 0;
      emit(out, lab::formatAck(c.command(buffer, now, encoder), out, sizeof(out)));
    }
    c.step(now * 1000U);
    if (now - lastConfig >= 1000) { lastConfig = now; emit(out, lab::formatConfig(c.cfg, out, sizeof(out))); }
    if (now - lastPrint >= 100) {
      lastPrint = now;
      emit(out, lab::formatState(c, now, out, sizeof(out)));
      emit(out, lab::formatRaw(c, now, out, sizeof(out)));
    }
    std::fflush(stdout);
    if (inputClosed) {
      std::lock_guard<std::mutex> lock(inputMutex);
      if (inputLines.empty()) break;
    }
  }
  return 0;
}
