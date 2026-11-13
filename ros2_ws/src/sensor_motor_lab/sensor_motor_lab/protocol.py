"""Strict, dependency-free serial protocol shared by the bridge, GUI and tests.

Protocol revision 2 (must match LAB_PROTOCOL_VERSION in firmware/controller_core.h).

Measurement provenance differs per motor and the field names say so:
  * servo_cmd_deg  - COMMANDED servo angle (no position sensor on the servo)
  * step_deg       - angle inferred from STEP pulses already sent (open loop)
  * dc_deg/dc_rpm  - MEASURED from the quadrature encoder
Distances use negative sentinels: -1 = invalid / no target, -2 = closer than the
sensor's minimum range.
"""
from dataclasses import asdict, dataclass, fields
import json
import math

PROTOCOL_VERSION = 2
INVALID = -1.0
TOO_CLOSE = -2.0

# Outer protocol bounds. The firmware's CONFIG frame narrows these to the limits
# that are actually configured for the hardware (see Config.limits()).
LIMITS = {
    'MODE': (0, 1), 'SERVO': (0, 180), 'DC_RPM': (-120, 120),
    'DC_MOVE': (-3600, 3600), 'STEP_MOVE': (-3600, 3600),
    'STOP': (0, 0), 'ARM': (0, 0), 'ZERO': (0, 0), 'PING': (0, 0),
}
MOTION_VERBS = frozenset({'SERVO', 'DC_RPM', 'DC_MOVE', 'STEP_MOVE'})
MAX_LINE = 384
CALIBRATION_BITS = {'pot': 1, 'ir': 2, 'sonar': 4, 'encoder': 8, 'servo': 16}
FAULTS = {'NONE', 'WATCHDOG', 'ENCODER_STALL', 'ENCODER_DIRECTION', 'POSITION_TIMEOUT', 'CONFIG_INVALID'}


def finite(value):
    if isinstance(value, bool):
        raise ValueError('boolean is not a numeric command')
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('expected a finite number') from exc
    if not math.isfinite(result):
        raise ValueError('expected a finite number')
    return result


def validate_command(verb, value, limits=None):
    """Validate against the outer LIMITS and, when known, the firmware CONFIG limits."""
    if not isinstance(verb, str) or verb not in LIMITS:
        raise ValueError('unknown command')
    value = finite(value)
    low, high = LIMITS[verb]
    if limits and verb in limits:
        low, high = limits[verb]
    if not low <= value <= high or (verb == 'MODE' and value not in (0, 1)):
        raise ValueError(f'{verb} requires {low:g}..{high:g}')
    return verb, value


def command_from_json(text):
    if not isinstance(text, str) or len(text) > 160:
        raise ValueError('invalid command JSON length')
    try:
        command = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid command JSON') from exc
    if not isinstance(command, dict) or set(command) != {'verb', 'value'}:
        raise ValueError('expected exactly verb and value')
    return validate_command(command['verb'], command['value'])


def encode_command(seq, verb, value, limits=None):
    if type(seq) is not int or not 1 <= seq <= 0xFFFFFFFF:
        raise ValueError('sequence must be 1..4294967295')
    verb, value = validate_command(verb, value, limits)
    return f'CMD,{seq},{verb},{value:.6g}\n'.encode('ascii')


def integer(text, low=0, high=0xFFFFFFFF):
    if not text or not text.isascii() or not text.isdecimal():
        raise ValueError('expected unsigned decimal integer')
    result = int(text)
    if not low <= result <= high:
        raise ValueError('integer outside range')
    return result


def signed(text, low=-0x80000000, high=0x7FFFFFFF):
    negative = text[:1] == '-'
    body = text[1:] if negative else text
    if not body or not body.isascii() or not body.isdecimal():
        raise ValueError('expected signed decimal integer')
    result = -int(body) if negative else int(body)
    if not low <= result <= high:
        raise ValueError('integer outside range')
    return result


def flag(text):
    return bool(integer(text, 0, 1))


def code(text):
    if not text or not text.isascii() or not all(c.isupper() or c.isdigit() or c == '_' for c in text):
        raise ValueError('invalid code token')
    return text


@dataclass(frozen=True)
class State:
    ms: int
    mode: int
    pot_deg: float
    pot_pct: float
    ir_raw_cm: float
    ir_cm: float
    sonar_cm: float
    slot_count: int
    slot_ignored: int
    servo_cmd_deg: float
    dc_deg: float
    dc_rpm: float
    dc_target: float
    dc_control: str
    step_deg: float
    step_target_deg: float
    step_busy: bool
    armed: bool
    calibrated: bool
    fault: str

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Raw:
    ms: int
    pot_adc: int
    ir_adc: int
    sonar_adc: int
    slot_blocked: bool
    button_pressed: bool
    enc_counts: int
    step_steps: int

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Config:
    protocol: int
    servo_min_deg: float
    servo_max_deg: float
    servo_min_us: int
    servo_max_us: int
    max_rpm: float
    sensor_rpm: float
    dc_move_max_deg: float
    step_move_max_deg: float
    steps_per_rev: float
    enc_cpr: float
    enc_sign: int
    pot_adc_min: int
    pot_adc_max: int
    pot_travel_deg: float
    ir_stop_cm: float
    ir_start_cm: float
    sonar_cm_per_adc: float
    hw_verified: bool
    cal_mask: int

    def as_dict(self):
        return asdict(self)

    def limits(self):
        """Command limits the firmware will actually accept."""
        return {
            'SERVO': (self.servo_min_deg, self.servo_max_deg),
            'DC_RPM': (-self.max_rpm, self.max_rpm),
            'DC_MOVE': (-self.dc_move_max_deg, self.dc_move_max_deg),
            'STEP_MOVE': (-self.step_move_max_deg, self.step_move_max_deg),
        }

    def calibrated(self, name):
        return bool(self.cal_mask & CALIBRATION_BITS[name])

    @property
    def step_deg_per_step(self):
        return 360.0 / self.steps_per_rev


@dataclass(frozen=True)
class Ack:
    seq: int
    ok: bool
    reason: str


@dataclass(frozen=True)
class Info:
    detail: str


FIELD_COUNTS = {'STATE': len(fields(State)) + 1, 'RAW': len(fields(Raw)) + 1, 'CONFIG': len(fields(Config)) + 1}


def config_limits(config_dict):
    """Command limits from a CONFIG dictionary (as published on /lab/config)."""
    return Config(**config_dict).limits()


def parse_line(line):
    if isinstance(line, bytes):
        try:
            line = line.decode('ascii')
        except UnicodeDecodeError as exc:
            raise ValueError('non-ASCII serial frame') from exc
    if not isinstance(line, str) or len(line) > MAX_LINE:
        raise ValueError('invalid frame length')
    parts = line.rstrip('\r\n').split(',')
    kind = parts[0]
    if kind == 'INFO' and len(parts) == 2 and parts[1]:
        return Info(parts[1])
    if kind == 'ACK':
        if len(parts) != 4 or parts[2] not in ('OK', 'ERR') or not parts[3]:
            raise ValueError('invalid ACK')
        return Ack(integer(parts[1]), parts[2] == 'OK', code(parts[3]))
    if kind in FIELD_COUNTS and len(parts) != FIELD_COUNTS[kind]:
        raise ValueError(f'{kind} requires exactly {FIELD_COUNTS[kind]} CSV tokens (protocol {PROTOCOL_VERSION})')
    if kind == 'RAW':
        return Raw(integer(parts[1]), integer(parts[2], 0, 1023), integer(parts[3], 0, 1023),
                   integer(parts[4], 0, 1023), flag(parts[5]), flag(parts[6]),
                   signed(parts[7]), signed(parts[8]))
    if kind == 'CONFIG':
        protocol = integer(parts[1])
        if protocol != PROTOCOL_VERSION:
            raise ValueError(f'firmware protocol {protocol} does not match bridge protocol {PROTOCOL_VERSION}; '
                             're-upload the generated firmware or update the ROS package')
        config = Config(protocol, finite(parts[2]), finite(parts[3]), signed(parts[4]), signed(parts[5]),
                        finite(parts[6]), finite(parts[7]), finite(parts[8]), finite(parts[9]),
                        finite(parts[10]), finite(parts[11]), signed(parts[12], -1, 1),
                        signed(parts[13]), signed(parts[14]), finite(parts[15]), finite(parts[16]),
                        finite(parts[17]), finite(parts[18]), flag(parts[19]), integer(parts[20], 0, 31))
        if (config.servo_max_deg <= config.servo_min_deg or config.max_rpm <= 0
                or config.steps_per_rev <= 0 or config.enc_sign == 0):
            raise ValueError('inconsistent CONFIG limits')
        return config
    if kind != 'STATE':
        raise ValueError('unknown frame type')
    if parts[14] not in ('RPM', 'POSITION'):
        raise ValueError('invalid DC control mode')
    # Negative finite distances are invalid-reading sentinels (-1 invalid, -2 too close).
    return State(
        integer(parts[1]), integer(parts[2], 0, 1),
        finite(parts[3]), finite(parts[4]), finite(parts[5]), finite(parts[6]), finite(parts[7]),
        integer(parts[8]), integer(parts[9]), finite(parts[10]),
        finite(parts[11]), finite(parts[12]), finite(parts[13]), parts[14],
        finite(parts[15]), finite(parts[16]),
        flag(parts[17]), flag(parts[18]), flag(parts[19]), code(parts[20]),
    )


def describe_distance(value):
    """Human-readable distance including sentinel meaning."""
    if value == TOO_CLOSE:
        return 'too close (below minimum range)'
    if value < 0:
        return 'no valid reading'
    return f'{value:.1f} cm'


class LineFramer:
    """Drop the complete overlong frame, including a valid-looking suffix."""
    def __init__(self):
        self.buffer = bytearray()
        self.dropping = False
        self.rejected = 0

    def feed(self, data):
        lines = []
        for byte in data:
            if byte == 10:
                if not self.dropping and self.buffer:
                    lines.append(bytes(self.buffer))
                self.buffer.clear()
                self.dropping = False
            elif not self.dropping:
                self.buffer.append(byte)
                if len(self.buffer) > MAX_LINE:
                    self.buffer.clear()
                    self.dropping = True
                    self.rejected += 1
        return lines
