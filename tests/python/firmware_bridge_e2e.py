"""Exercise the real Python SerialLink against the real C++ firmware core.

The host executable (tests/firmware/host_cli.cpp) supplies a synthetic motor
plant and fixed sensor inputs, and formats frames with the SAME functions the Uno
uses. This verifies cross-language protocol/control integration, not physical
hardware or ROS 2 middleware. Works on Windows, Linux and macOS.

Usage: python firmware_bridge_e2e.py /path/to/host_cli[.exe]
"""
import queue
import subprocess
import sys
import threading
import time

from sensor_motor_lab.link import SerialLink


class ProcessSerial:
    """Pipe-backed stand-in for pyserial; a reader thread avoids select() on pipes."""

    def __init__(self, executable):
        self.process = subprocess.Popen([executable], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, bufsize=0)
        self.chunks = queue.Queue()
        self.buffer = bytearray()
        self.alive = True
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while True:
            data = self.process.stdout.read(4096)  # unbuffered pipe: returns what is available
            if not data:
                self.alive = False
                return
            self.chunks.put(data)

    @property
    def in_waiting(self):
        while True:
            try:
                self.buffer.extend(self.chunks.get_nowait())
            except queue.Empty:
                break
        if not self.buffer and not self.alive:
            raise OSError('firmware simulator exited')
        return len(self.buffer)

    def read(self, size):
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        return result

    def write(self, data):
        written = self.process.stdin.write(data)
        self.process.stdin.flush()
        return written

    def close(self):
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=2)


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: firmware_bridge_e2e.py /path/to/host_cli')
    states, events = [], []
    device = ProcessSerial(sys.argv[1])
    link = SerialLink(lambda: device, time.monotonic, states.append, events.append)

    def wait_for(predicate, seconds=2):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            link.tick()
            if predicate():
                return
            time.sleep(0.01)
        raise AssertionError(f'timed out; state={states[-1] if states else None}; events={events[-5:]}')

    def command(verb, value=0, ok=True):
        seq = link.submit(verb, value)
        wait_for(lambda: any(e.get('seq') == seq and e['kind'] == 'ack' for e in events))
        ack = next(e for e in events if e.get('seq') == seq and e['kind'] == 'ack')
        assert ack['ok'] == ok, ack
        return ack

    try:
        wait_for(lambda: link.ready and link.config is not None)
        assert not states[-1].armed
        assert not states[-1].calibrated
        assert link.config.protocol == 2 and link.config.hw_verified
        raw_ms = {e['data']['ms'] for e in events if e['kind'] == 'raw'}
        assert any(s.ms in raw_ms for s in states), 'STATE and RAW must share timestamps'
        assert abs(states[-1].ir_cm - 60) < 0.1, states[-1]  # ADC 201 -> 60 cm via the GP2Y0A02 table
        assert abs(states[-1].sonar_cm - 100.33) < 0.01, states[-1]
        command('ARM')
        command('SERVO', 45)
        wait_for(lambda: states[-1].servo_cmd_deg == 45)
        command('DC_RPM', 20)
        wait_for(lambda: abs(states[-1].dc_rpm - 20) < 3, seconds=5)
        command('DC_MOVE', 90)
        wait_for(lambda: states[-1].dc_control == 'POSITION')
        wait_for(lambda: abs(states[-1].dc_deg - states[-1].dc_target) < 4, seconds=6)
        command('STEP_MOVE', -91)  # rounds to -51 steps = -91.8 deg
        wait_for(lambda: not states[-1].step_busy and abs(states[-1].step_deg + 91.8) < 0.01)
        assert abs(states[-1].step_target_deg + 91.8) < 0.01
        command('STOP')
        wait_for(lambda: not states[-1].armed)
        command('ZERO')
        wait_for(lambda: abs(states[-1].step_deg) < 0.01)
        enc_before = [e['data'] for e in events if e['kind'] == 'raw'][-1]['enc_counts']
        assert enc_before != 0, 'RAW enc_counts must stay raw after ZERO'
        command('MODE', 1)
        command('ARM')
        wait_for(lambda: states[-1].mode == 1 and states[-1].dc_target > 0)  # IR 60 cm > 45 cm start
        # Stop servicing the bridge: firmware's own watchdog must disarm.
        time.sleep(1.8)
        wait_for(lambda: not states[-1].armed and states[-1].fault == 'WATCHDOG')
        print(f'Cross-language firmware/bridge test passed ({len(states)} STATE frames): '
              'CONFIG limits, ARM, servo, DC speed and relative position, stepper rounding, '
              'STOP, ZERO with raw encoder count, sensor mode, RAW telemetry, firmware watchdog. '
              'Motor plant and sensor inputs were synthetic; no ROS 2 runtime used.')
    finally:
        link.close()
        device.close()


if __name__ == '__main__':
    main()
