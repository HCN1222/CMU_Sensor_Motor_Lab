"""Serial session; no ROS dependency so the real transport logic is testable."""
import time

from .protocol import (
    MOTION_VERBS, Ack, Config, Info, LineFramer, Raw, State, encode_command, parse_line, validate_command,
)


def time_based_sequence():
    """Start each bridge session above any sequence an un-reset Uno may remember.

    The firmware rejects sequence numbers that do not increase (STALE_SEQ). Opening
    the port normally resets the Uno, but some adapters/OS paths do not toggle DTR.
    Counting from wall-clock centiseconds stays ahead of the ~3 commands/s a session
    sends, so a restarted bridge is still accepted.
    """
    return int(time.time() * 100) % 0xFFFFFFFE + 1


class SerialLink:
    def __init__(self, serial_factory, clock, state_callback, event_callback,
                 state_timeout=1.5, ack_timeout=1.0, initial_seq=None):
        self.serial_factory = serial_factory
        self.clock = clock
        self.state_callback = state_callback
        self.event_callback = event_callback
        self.state_timeout = state_timeout
        self.ack_timeout = ack_timeout
        self.serial = None
        self.next_connect = 0.0
        self.next_ping = 0.0
        self.last_state = None
        self.opened_at = 0.0
        self.seq = (time_based_sequence() if initial_seq is None else initial_seq) - 1
        self.pending = {}
        self.framer = LineFramer()
        self.config = None
        self.closed = False

    @property
    def ready(self):
        return (self.serial is not None and self.last_state is not None
                and self.clock() - self.last_state < self.state_timeout)

    def event(self, kind, **values):
        self.event_callback(dict(kind=kind, **values))

    def _send(self, verb, value=0, tracked=True):
        self.seq = self.seq % 0xFFFFFFFF + 1
        frame = encode_command(self.seq, verb, value)
        written = self.serial.write(frame)
        if written != len(frame):
            raise OSError('partial serial write; command outcome unknown')
        if tracked:
            self.pending[self.seq] = (self.clock(), verb)
        return self.seq

    def submit(self, verb, value=0):
        verb, value = validate_command(verb, value)
        if self.serial is None:
            raise ValueError('serial is disconnected')
        if verb not in ('STOP', 'PING') and not self.ready:
            raise ValueError('waiting for fresh controller telemetry')
        if verb in MOTION_VERBS:
            if self.config is None:
                raise ValueError('waiting for the firmware CONFIG frame (limits unknown)')
            validate_command(verb, value, self.config.limits())
        if len(self.pending) >= 32 and verb != 'STOP':
            raise ValueError('too many unacknowledged commands')
        try:
            seq = self._send(verb, value)
        except (OSError, IOError) as exc:
            self._disconnect(str(exc))
            raise ValueError('serial command failed; outcome unknown') from exc
        self.event('sent', seq=seq, verb=verb, value=value)
        return seq

    def _disconnect(self, reason):
        if self.serial is not None:
            try:
                self._send('STOP', tracked=False)
            except Exception:
                pass
            try:
                self.serial.close()
            except Exception:
                pass
        for seq, (_, verb) in list(self.pending.items()):
            self.event('unconfirmed', seq=seq, verb=verb,
                       detail='Connection lost; inspect state before retrying a relative move.')
        self.serial = None
        self.pending.clear()
        self.last_state = None
        self.config = None  # firmware may be re-flashed while disconnected
        self.next_connect = self.clock() + 2.0
        self.event('disconnected', detail=reason)

    def tick(self):
        if self.closed:
            return
        now = self.clock()
        if self.serial is None:
            if now < self.next_connect:
                return
            try:
                self.serial = self.serial_factory()
                self.framer = LineFramer()
                self.opened_at = now
                self.last_state = None
                self.next_ping = now
                self._send('STOP', tracked=False)
                self.event('connected', detail='Waiting for telemetry; ARM is never automatic.')
            except (OSError, IOError) as exc:
                self._disconnect(str(exc))
                return
        try:
            data = self.serial.read(min(self.serial.in_waiting, 4096))
            for line in self.framer.feed(data):
                try:
                    item = parse_line(line)
                except ValueError as exc:
                    self.event('invalid_frame', detail=str(exc))
                    continue
                if isinstance(item, State):
                    self.last_state = now
                    self.state_callback(item)
                elif isinstance(item, Raw):
                    self.event('raw', data=item.as_dict())
                elif isinstance(item, Config):
                    if item != self.config:
                        self.config = item
                        self.event('config', data=item.as_dict())
                elif isinstance(item, Info):
                    self.event('controller_info', detail=item.detail)
                elif isinstance(item, Ack):
                    command = self.pending.pop(item.seq, None)
                    # Heartbeat ACKs are intentionally not displayed at 2 Hz.
                    if command is not None:
                        self.event('ack', seq=item.seq, ok=item.ok,
                                   verb=command[1], reason=item.reason)
            # Uno resets when opening a serial port: allow up to 5 s for boot.
            if ((self.last_state is None and now - self.opened_at > 5.0)
                    or (self.last_state is not None
                        and now - self.last_state > self.state_timeout)):
                self._disconnect('Telemetry timeout; STOP attempted and heartbeat removed.')
                return
            if now >= self.next_ping:
                self._send('PING', tracked=False)
                self.next_ping = now + 0.5
            for seq, (sent_at, verb) in list(self.pending.items()):
                if now - sent_at > self.ack_timeout:
                    self.pending.pop(seq)
                    self.event('unconfirmed', seq=seq, verb=verb,
                               detail='ACK timeout. Not retried; inspect state before repeating.')
        except (OSError, IOError) as exc:
            self._disconnect(str(exc))

    def close(self):
        self.closed = True
        self._disconnect('Bridge stopped')
