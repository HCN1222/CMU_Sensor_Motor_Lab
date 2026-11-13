#!/usr/bin/env python3
"""Record calibration rows straight from the Uno's telemetry (read-only).

Opens the serial port, waits for STATE/RAW frames, averages them for a few
seconds, and appends ONE row to calibration/<sensor>.csv. It never sends a
command, so the controller stays disarmed. Close the ROS bridge and the Arduino
Serial Monitor first (only one program can own the port).

Examples (the reference value is what YOU measured with a tape/protractor):
    python calibration/capture.py --port COM5 ir --reference 40 --split calibration --notes "white card"
    python calibration/capture.py --port COM5 sonar --reference 100 --split validation
    python calibration/capture.py --port COM5 pot --reference 90 --split calibration
    python calibration/capture.py --port COM5 slot --reference 10 --split validation --seconds 15
    python calibration/capture.py --port COM5 ir-filter --seconds 20       # stationary target
"""
import argparse
import csv
from pathlib import Path
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'ros2_ws' / 'src' / 'sensor_motor_lab'))
from sensor_motor_lab.protocol import Config, Info, LineFramer, Raw, State, parse_line  # noqa: E402

# sensor -> (RAW ADC field, STATE physical field)
FIELDS = {'pot': ('pot_adc', 'pot_deg'), 'ir': ('ir_adc', 'ir_cm'), 'sonar': ('sonar_adc', 'sonar_cm')}


def frames(port, seconds, wait=6.0, boot_grace=3.0, connection=None):
    """Yield (STATE, RAW) pairs that share a timestamp, for `seconds` after the first one.

    Opening the port resets an Uno, but a frame it sent just before that reset can
    still be waiting in the USB-serial buffer. Telemetry is therefore used only after
    the firmware's BOOT_DISARMED line, or after `boot_grace` seconds if the board did
    not reset. A reset during the capture aborts it so old and new data never mix.
    """
    if connection is None:
        import serial
        connection = serial.Serial(port, 115200, timeout=0.05)
    with connection:
        opened = time.monotonic()
        framer, states, start, deadline = LineFramer(), {}, None, opened + wait
        live, last_ms = False, None
        while True:
            now = time.monotonic()
            if start is None and now > deadline:
                raise SystemExit(f'No telemetry from {port} within {wait:.0f} s. Is the lab firmware uploaded '
                                 'and nothing else using the port?')
            if start is not None and now - start > seconds:
                return
            if not live and now - opened > boot_grace:
                live = True  # the board did not reset on open, so what arrives now is current
                states.clear()
            for line in framer.feed(connection.read(4096)):
                try:
                    item = parse_line(line)
                except ValueError as exc:
                    print(f'ignored frame: {exc}', file=sys.stderr)
                    continue
                if isinstance(item, Info):
                    print(f'controller: {item.detail}')
                    if item.detail == 'BOOT_DISARMED':
                        if start is not None:
                            raise SystemExit('The Uno reset during the capture; nothing was saved. Capture again.')
                        live, last_ms = True, None
                        states.clear()  # anything buffered before the reset is stale
                elif isinstance(item, Config):
                    print(f'firmware CONFIG: hw_verified={item.hw_verified} cal_mask={item.cal_mask}')
                elif isinstance(item, State) and live:
                    if last_ms is not None and item.ms < last_ms:
                        raise SystemExit('The Uno clock went backwards (reset during the capture); '
                                         'nothing was saved. Capture again.')
                    last_ms = item.ms
                    states[item.ms] = item
                elif isinstance(item, Raw) and live and item.ms in states:
                    if start is None:
                        start = time.monotonic()
                    yield states.pop(item.ms), item


def append_row(path, row):
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        columns = next(csv.reader(handle))
    with path.open('a', encoding='utf-8', newline='') as handle:
        csv.DictWriter(handle, columns).writerow({key: row.get(key, '') for key in columns})


def capture_sensor(args):
    adc_field, value_field = FIELDS[args.sensor]
    input(f'Hold the {args.sensor} target at {args.reference:g} and press Enter to record {args.seconds:g} s... ')
    adc, values, invalid = [], [], 0
    for state, raw in frames(args.port, args.seconds):
        adc.append(getattr(raw, adc_field))
        value = getattr(state, value_field)
        if value >= 0:
            values.append(value)
        else:
            invalid += 1
    if len(adc) < 5:
        raise SystemExit('Too few samples; check the connection and try again.')
    measured = f'{statistics.mean(values):.3f}' if values and not invalid else ''
    if args.split == 'validation' and not measured:
        raise SystemExit(f'{invalid}/{len(adc)} samples had no valid {value_field}; a validation row needs a '
                         'valid converted value (check range, target and calibration).')
    notes = (f'n={len(adc)} adc_std={statistics.pstdev(adc):.2f} invalid={invalid} capture.py '
             f'{time.strftime("%Y-%m-%d %H:%M")}' + (f'; {args.notes}' if args.notes else ''))
    row = dict(reference=f'{args.reference:g}', raw_adc=f'{statistics.mean(adc):.2f}', measured=measured,
               split=args.split, notes=notes)
    append_row(HERE / f'{args.sensor}.csv', row)
    print(f'appended to {args.sensor}.csv: {row}')


def capture_slot(args):
    input(f'Press Enter, then block the slot {args.reference:g} times within {args.seconds:g} s... ')
    counts = [state.slot_count for state, _ in frames(args.port, args.seconds)]
    if not counts:
        raise SystemExit('No telemetry recorded.')
    row = dict(reference=f'{args.reference:g}', measured=str(counts[-1] - counts[0]), split=args.split,
               notes=f'capture.py {time.strftime("%Y-%m-%d %H:%M")}' + (f'; {args.notes}' if args.notes else ''))
    append_row(HERE / 'slot.csv', row)
    print(f'appended to slot.csv: {row}')


def capture_filter(args):
    path = HERE / 'ir_filter.csv'
    with path.open(encoding='utf-8-sig') as handle:
        if sum(1 for line in handle if line.strip()) > 1 and not args.replace:
            raise SystemExit('ir_filter.csv already has data; pass --replace to overwrite it with a new session.')
    input(f'Fix a target in front of the IR sensor and press Enter to record {args.seconds:g} s... ')
    rows, t0 = [], None
    for state, _ in frames(args.port, args.seconds):
        if state.ir_raw_cm < 0 or state.ir_cm < 0:
            continue
        t0 = state.ms if t0 is None else t0
        rows.append(dict(time_s=f'{(state.ms - t0) / 1000:.3f}', raw_cm=f'{state.ir_raw_cm:.2f}',
                         filtered_cm=f'{state.ir_cm:.2f}', notes=args.notes or ''))
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, ['time_s', 'raw_cm', 'filtered_cm', 'notes'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'wrote {len(rows)} rows to ir_filter.csv')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', required=True, help='e.g. COM5 or /dev/ttyACM0')
    parser.add_argument('sensor', choices=['pot', 'ir', 'sonar', 'slot', 'ir-filter'])
    parser.add_argument('--reference', type=float, help='independent measurement: cm, deg, or event count')
    parser.add_argument('--split', choices=['calibration', 'validation'])
    parser.add_argument('--seconds', type=float, default=3.0)
    parser.add_argument('--notes', default='')
    parser.add_argument('--replace', action='store_true', help='ir-filter: overwrite existing data')
    args = parser.parse_args()
    if args.sensor == 'ir-filter':
        capture_filter(args)
        return
    if args.reference is None or args.split is None:
        parser.error('--reference and --split are required for this sensor')
    (capture_slot if args.sensor == 'slot' else capture_sensor)(args)


if __name__ == '__main__':
    main()
