"""Run with PYTHONPATH=ros2_ws/src/sensor_motor_lab python -m unittest discover ..."""
import importlib.util
import os
import select
import time
import unittest

from sensor_motor_lab.link import SerialLink, time_based_sequence
from sensor_motor_lab.operator_lease import OperatorLease
from sensor_motor_lab.protocol import (
    TOO_CLOSE, Ack, Config, Info, LineFramer, Raw, State, command_from_json, config_limits,
    describe_distance, encode_command, parse_line, validate_command,
)

STATE = b'STATE,1000,0,-1,50.0,40,39.5,100,3,0,30,45,-12,20,RPM,-90,-90,0,1,0,NONE\n'
RAW = b'RAW,1000,512,287,79,1,0,-360,50\n'
CONFIG = b'CONFIG,2,0.0,60.0,1200,1800,30.0,20.0,1080.0,1080.0,200.0,360.0,1,0,1023,0.0,35.0,45.0,1.270,0,0\n'


class FakeSerial:
    def __init__(self):
        self.rx = bytearray()
        self.tx = []
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.rx)

    def read(self, count):
        data = bytes(self.rx[:count])
        del self.rx[:count]
        return data

    def write(self, data):
        self.tx.append(data)
        return len(data)

    def close(self):
        self.closed = True


class ProtocolTests(unittest.TestCase):
    def test_exact_state_fields_and_signed_motion(self):
        state = parse_line(STATE)
        self.assertIsInstance(state, State)
        self.assertEqual(state.dc_rpm, -12)
        self.assertEqual(state.step_deg, -90)
        self.assertEqual(state.step_target_deg, -90)
        self.assertEqual(state.dc_control, 'RPM')
        self.assertEqual(state.pot_deg, -1)
        self.assertEqual(state.pot_pct, 50)
        self.assertEqual(state.fault, 'NONE')
        self.assertTrue(state.armed)
        self.assertFalse(state.calibrated)

    def test_distance_sentinels_are_accepted_and_described(self):
        state = parse_line(STATE.replace(b',40,39.5,100,', b',-2,-2,-1,'))
        self.assertEqual(state.ir_raw_cm, TOO_CLOSE)
        self.assertEqual(describe_distance(state.ir_cm), 'too close (below minimum range)')
        self.assertEqual(describe_distance(state.sonar_cm), 'no valid reading')
        self.assertEqual(describe_distance(42.25), '42.2 cm')

    def test_raw_counts_and_adc_bounds(self):
        raw = parse_line(RAW)
        self.assertIsInstance(raw, Raw)
        self.assertEqual(raw.pot_adc, 512)
        self.assertTrue(raw.slot_blocked)
        self.assertFalse(raw.button_pressed)
        self.assertEqual(raw.enc_counts, -360)
        self.assertEqual(raw.step_steps, 50)
        for bad in (b'RAW,1000,1024,100,50,1,0,0,0\n', b'RAW,1000,512,100,50,1,0,--3,0\n',
                    b'RAW,1000,512,100,50,1,0,2147483648,0\n', b'RAW,1000,512,100,50,1\n'):
            with self.subTest(frame=bad), self.assertRaises(ValueError):
                parse_line(bad)
        self.assertEqual(parse_line(b'RAW,1,0,0,0,0,0,-2147483648,0\n').enc_counts, -2147483648)

    def test_config_frame_gives_firmware_limits(self):
        config = parse_line(CONFIG)
        self.assertIsInstance(config, Config)
        self.assertFalse(config.hw_verified)
        self.assertFalse(config.calibrated('ir'))
        self.assertEqual(config.limits()['SERVO'], (0.0, 60.0))
        self.assertEqual(config.limits()['DC_RPM'], (-30.0, 30.0))
        self.assertAlmostEqual(config.step_deg_per_step, 1.8)
        self.assertEqual(config_limits(config.as_dict()), config.limits())
        with self.assertRaises(ValueError):
            validate_command('SERVO', 61, config.limits())
        self.assertEqual(validate_command('SERVO', 61), ('SERVO', 61.0))  # outer bound alone allows it

    def test_protocol_version_mismatch_is_reported(self):
        with self.assertRaisesRegex(ValueError, 'protocol 1'):
            parse_line(CONFIG.replace(b'CONFIG,2,', b'CONFIG,1,'))
        with self.assertRaisesRegex(ValueError, 'exactly 21'):
            parse_line(b'STATE,1000,0,150,40,39.5,100,3,90,45,-12,20,RPM,-90,0,0,0\n')  # protocol 1 STATE

    def test_ack_reason_is_not_interpreted(self):
        ack = parse_line('ACK,9,ERR,NOT_CALIBRATED')
        self.assertEqual(ack, Ack(9, False, 'NOT_CALIBRATED'))
        self.assertEqual(parse_line('INFO,BOOT_DISARMED'), Info('BOOT_DISARMED'))

    def test_commands_reject_nonfinite_or_injection(self):
        for value in (float('nan'), float('inf'), -float('inf'), True,
                      '90\nCMD,9,ARM,0'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                encode_command(1, 'DC_MOVE', value)
        for verb, value in (('MODE', 0.5), ('SERVO', 181), ('DC_RPM', 121),
                            ('STOP', 1), ('ARM\n', 0), ('STEP_MOVE', -3601)):
            with self.subTest(verb=verb), self.assertRaises(ValueError):
                encode_command(1, verb, value)

    def test_json_requires_known_shape_and_no_boolean_values(self):
        for payload in ('[]', '{"verb":"ARM","value":true}',
                        '{"verb":"ARM","value":0,"seq":99}',
                        '{"verb":"DC_MOVE","value":NaN}'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                command_from_json(payload)
        self.assertEqual(command_from_json('{"verb":"DC_MOVE","value":-90}'),
                         ('DC_MOVE', -90.0))

    def test_fragmented_and_overlong_frames_recover(self):
        frames = LineFramer()
        self.assertEqual(frames.feed(STATE[:12]), [])
        self.assertEqual(frames.feed(STATE[12:]), [STATE[:-1]])
        # A suffix that looks like a command must not be accepted on overflow.
        self.assertEqual(frames.feed(b'x' * 500 + STATE), [])
        self.assertEqual(frames.feed(STATE), [STATE[:-1]])
        self.assertEqual(frames.rejected, 1)

    def test_bad_telemetry_cannot_refresh_watchdog(self):
        for bad in (STATE.replace(b',39.5,', b',nan,'), STATE.replace(b'NONE\n', b'NONE,extra\n'),
                    STATE.replace(b',RPM,', b',PWM,'),
                    STATE.replace(b',0,1,0,NONE', b',0,2,0,NONE'),
                    STATE.replace(b'NONE', b'none; rm')):
            with self.subTest(frame=bad), self.assertRaises(ValueError):
                parse_line(bad)


class OperatorLeaseTests(unittest.TestCase):
    def test_missing_lease_blocks_arm_and_motion_but_allows_stop(self):
        lease = OperatorLease(lambda: 0.0)
        for verb in ('ARM', 'SERVO', 'DC_RPM', 'DC_MOVE', 'STEP_MOVE'):
            self.assertFalse(lease.permits(verb))
        self.assertTrue(lease.permits('STOP'))
        self.assertTrue(lease.permits('PING'))

    def test_expiration_and_return_do_not_generate_commands(self):
        now = [0.0]
        lease = OperatorLease(lambda: now[0])
        lease.heartbeat()
        now[0] = 1.49
        self.assertTrue(lease.permits('ARM'))
        now[0] = 1.5
        self.assertFalse(lease.permits('ARM'))
        lease.heartbeat()
        self.assertTrue(lease.permits('ARM'))
        # The lease only permits an explicit command; it never issues ARM itself.


class LinkTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.device = FakeSerial()
        self.states, self.events = [], []
        self.link = SerialLink(lambda: self.device, lambda: self.now,
                               self.states.append, self.events.append, initial_seq=1)
        self.link.tick()

    def fresh(self, config=True):
        self.device.rx.extend((CONFIG if config else b'') + STATE)
        self.link.tick()

    def test_boot_has_stop_and_ping_but_never_arm(self):
        self.assertIn(b'CMD,1,STOP,0\n', self.device.tx[0])
        self.assertFalse(any(b',ARM,' in line for line in self.device.tx))
        with self.assertRaises(ValueError):
            self.link.submit('DC_MOVE', 90)

    def test_motion_waits_for_config_then_uses_firmware_limits(self):
        self.fresh(config=False)
        with self.assertRaisesRegex(ValueError, 'CONFIG'):
            self.link.submit('SERVO', 30)
        self.link.submit('ARM', 0)  # non-motion commands do not need CONFIG
        self.fresh()
        self.assertEqual([e['kind'] for e in self.events].count('config'), 1)
        sent = len(self.device.tx)
        with self.assertRaisesRegex(ValueError, '0..60'):
            self.link.submit('SERVO', 90)
        self.assertEqual(len(self.device.tx), sent, 'out-of-range command must not reach the serial port')
        self.link.submit('SERVO', 60)
        self.fresh()  # identical CONFIG is not re-announced
        self.assertEqual([e['kind'] for e in self.events].count('config'), 1)

    def test_fragmented_state_then_command_and_ack(self):
        self.device.rx.extend(CONFIG + STATE[:20])
        self.link.tick()
        self.assertFalse(self.link.ready)
        self.device.rx.extend(STATE[20:])
        self.link.tick()
        seq = self.link.submit('DC_MOVE', -90)
        self.assertIn(b',DC_MOVE,-90\n', self.device.tx[-1])
        self.device.rx.extend(f'ACK,{seq},OK,ACCEPTED\n'.encode())
        self.link.tick()
        self.assertEqual(self.events[-1]['kind'], 'ack')
        self.assertNotIn(seq, self.link.pending)

    def test_lost_ack_never_replays_relative_move(self):
        self.fresh()
        self.link.submit('STEP_MOVE', 90)
        self.now = 1.1
        self.fresh()
        moves = [frame for frame in self.device.tx if b',STEP_MOVE,' in frame]
        self.assertEqual(len(moves), 1)
        self.assertTrue(any(event['kind'] == 'unconfirmed' for event in self.events))

    def test_stale_state_stops_and_removes_heartbeat(self):
        self.fresh()
        self.now = 1.6
        self.link.tick()
        self.assertTrue(self.device.closed)
        self.assertIn(b',STOP,0\n', self.device.tx[-1])
        self.assertIsNone(self.link.config, 'limits must be re-learned after a disconnect')
        count = len(self.device.tx)
        self.now = 2.0
        self.link.tick()
        self.assertEqual(len(self.device.tx), count)

    def test_reconnect_never_arms_or_replays_motion(self):
        self.fresh()
        self.link.submit('DC_MOVE', 45)
        self.now = 1.6
        self.link.tick()  # telemetry timeout -> disconnect
        self.device = FakeSerial()
        self.now = 4.0
        self.link.tick()  # reconnect
        self.assertIn(b',STOP,0\n', self.device.tx[0])
        self.assertFalse(any(b',ARM,' in f or b',DC_MOVE,' in f for f in self.device.tx))

    def test_bad_frames_do_not_make_link_ready(self):
        self.device.rx.extend(b'STATE,garbage\n')
        self.link.tick()
        self.assertFalse(self.link.ready)
        self.assertTrue(any(event['kind'] == 'invalid_frame' for event in self.events))

    def test_optional_raw_frame_is_forwarded_without_affecting_readiness(self):
        self.device.rx.extend(RAW)
        self.link.tick()
        self.assertFalse(self.link.ready)
        self.assertEqual(self.events[-1]['kind'], 'raw')
        self.assertEqual(self.events[-1]['data']['enc_counts'], -360)

    def test_shutdown_requests_stop(self):
        self.link.close()
        self.assertTrue(self.device.closed)
        self.assertIn(b',STOP,0\n', self.device.tx[-1])

    def test_new_session_sequence_starts_above_previous_session(self):
        first = time_based_sequence()
        time.sleep(0.02)
        self.assertGreater(time_based_sequence(), first)
        link = SerialLink(lambda: FakeSerial(), lambda: 0.0, lambda s: None, lambda e: None)
        self.assertGreaterEqual(link.seq + 1, first)


@unittest.skipUnless(importlib.util.find_spec('serial') and hasattr(os, 'openpty'),
                     'needs pyserial and a POSIX pseudo-terminal (Linux/macOS)')
class PtyTransportTests(unittest.TestCase):
    def test_real_pyserial_over_os_pseudo_terminal(self):
        import serial
        master, slave = os.openpty()
        name = os.ttyname(slave)
        states, events = [], []
        connection = serial.Serial(name, 115200, timeout=0, write_timeout=0.1)
        link = SerialLink(lambda: connection, time.monotonic, states.append, events.append)
        try:
            link.tick()
            ready, _, _ = select.select([master], [], [], 0.5)
            self.assertTrue(ready)
            startup = os.read(master, 1024)
            self.assertIn(b',STOP,0\n', startup)
            os.write(master, CONFIG + STATE[:15])
            time.sleep(0.01)
            link.tick()
            self.assertFalse(states)
            os.write(master, STATE[15:])
            for _ in range(20):
                time.sleep(0.005)
                link.tick()
                if states:
                    break
            self.assertTrue(link.ready)
            seq = link.submit('DC_MOVE', -45)
            expected, received = f'CMD,{seq},DC_MOVE,-45\n'.encode(), b''
            deadline = time.monotonic() + 1.0
            while expected not in received and time.monotonic() < deadline:  # PING frames may come first
                if select.select([master], [], [], 0.1)[0]:
                    received += os.read(master, 1024)
            self.assertIn(expected, received)
            os.write(master, f'ACK,{seq},OK,ACCEPTED\n'.encode())
            for _ in range(20):
                time.sleep(0.005)
                link.tick()
                if seq not in link.pending:
                    break
            self.assertNotIn(seq, link.pending)
            self.assertTrue(any(e['kind'] == 'ack' for e in events))
        finally:
            link.close()
            os.close(master)
            os.close(slave)


if __name__ == '__main__':
    unittest.main()
