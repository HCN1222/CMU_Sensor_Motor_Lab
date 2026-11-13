#!/usr/bin/env python3
"""Run every offline check in one go (Windows, Linux, macOS).

    conda activate sensorMotorLab
    python tools/run_tests.py            # all offline checks
    python tools/run_tests.py --ros      # also start real ROS 2 nodes (needs ROS 2 in the env)
    python tools/run_tests.py --no-avr   # skip the arduino-cli Uno compile

Each step prints PASS/FAIL/SKIP and the script exits non-zero if anything failed.
Nothing here touches the Uno or moves a motor.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'ros2_ws' / 'src' / 'sensor_motor_lab'
EXE = '.exe' if os.name == 'nt' else ''
ARDUINO_CLI_CANDIDATES = (
    r'C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe',
    '/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli',
)


def find_cxx():
    for name in (os.environ.get('CXX'), 'c++', 'g++', 'clang++'):
        if name and shutil.which(name):
            return shutil.which(name)
    return None


def find_arduino_cli():
    found = shutil.which('arduino-cli')
    if found:
        return found
    return next((p for p in ARDUINO_CLI_CANDIDATES if Path(p).exists()), None)


class Runner:
    def __init__(self):
        self.results = []

    def run(self, name, command, env=None, cwd=ROOT, timeout=300):
        print(f'\n=== {name}\n$ {" ".join(str(c) for c in command)}', flush=True)
        merged = dict(os.environ, **(env or {}))
        try:
            proc = subprocess.run([str(c) for c in command], cwd=cwd, env=merged, timeout=timeout,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                  encoding='utf-8', errors='replace')
            output, ok = proc.stdout, proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired) as exc:
            output, ok = str(exc), False
        print(output.rstrip())
        self.results.append((name, 'PASS' if ok else 'FAIL', output.strip().splitlines()[-1:] or ['']))
        return ok, output

    def skip(self, name, reason):
        print(f'\n=== {name}\nSKIP: {reason}')
        self.results.append((name, 'SKIP', [reason]))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--ros', action='store_true', help='also run the real ROS 2 graph check')
    parser.add_argument('--no-avr', action='store_true', help='skip the arduino-cli compile')
    args = parser.parse_args()
    r = Runner()
    py = sys.executable
    pypath = {'PYTHONPATH': str(PKG) + os.pathsep + os.environ.get('PYTHONPATH', '')}
    tmp = Path(tempfile.mkdtemp(prefix='sensor_motor_lab_tests_'))

    r.run('Generated Uno sketch matches shared sources', [py, ROOT / 'firmware' / 'generate_sketches.py', '--check'])

    cxx = find_cxx()
    if cxx:
        core = tmp / f'core_tests{EXE}'
        if r.run('Compile C++ core tests', [cxx, '-std=c++11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                                            ROOT / 'tests/firmware/test_controller.cpp', '-o', core])[0]:
            r.run('C++ controller core behaviour', [core])
        host = tmp / f'host_cli{EXE}'
        threads = [] if os.name == 'nt' else ['-pthread']
        if r.run('Compile host firmware simulator', [cxx, '-std=c++11', '-O2', *threads,
                                                     ROOT / 'tests/firmware/host_cli.cpp', '-o', host])[0]:
            r.run('Python link <-> C++ core end-to-end', [py, ROOT / 'tests/python/firmware_bridge_e2e.py', host],
                  env=pypath, timeout=120)
    else:
        r.skip('C++ tests', 'no C++ compiler (set CXX or install one; see README "Environment")')

    r.run('Python protocol / link / bridge unit tests',
          [py, '-m', 'unittest', 'discover', '-s', ROOT / 'tests/python', '-p', 'test_*.py', '-v'], env=pypath)
    r.run('Qt dashboard offscreen smoke', [py, ROOT / 'tests/python/dashboard_smoke.py', tmp / 'dashboard_preview.png'],
          env=dict(pypath, QT_QPA_PLATFORM='offscreen'))
    r.run('Calibration analysis tests', [py, '-m', 'unittest', 'test_analysis.py', '-v'], cwd=ROOT / 'calibration')

    cli = None if args.no_avr else find_arduino_cli()
    if cli:
        ok, out = r.run('Arduino Uno compile (arduino:avr:uno)',
                        [cli, 'compile', '--fqbn', 'arduino:avr:uno', '--warnings', 'all',
                         '--build-path', tmp / 'avr', ROOT / 'firmware' / 'hardware_controller'])
    else:
        r.skip('Arduino Uno compile', 'arduino-cli not found' if not args.no_avr else '--no-avr')

    if args.ros:
        host = tmp / f'host_cli{EXE}'
        r.run('ROS 2 graph: bridge node, topics, latched CONFIG, command path',
              [py, ROOT / 'tests/ros/ros_graph_check.py', *([host] if host.exists() else [])], env=pypath, timeout=180)

    shutil.rmtree(tmp, ignore_errors=True)
    print('\n=== Summary')
    for name, status, last in r.results:
        print(f'{status:4}  {name}  {"| " + last[0] if last and last[0] else ""}')
    failed = [name for name, status, _ in r.results if status == 'FAIL']
    print('\nScope: software only. Motor plants and sensor inputs in these tests are synthetic;'
          ' no physical calibration, PID tuning or wiring is verified here.')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
