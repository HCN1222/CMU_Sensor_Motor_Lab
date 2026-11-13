"""Smoke-test lab.launch.py: both processes start and the bridge node joins the graph.

Run after `colcon build` and sourcing install/setup.(bat|bash). Uses a port that
does not exist, so the bridge just retries; the rqt panel runs offscreen.
    python tests/ros/launch_smoke.py
"""
import os
import subprocess
import sys
import time


def kill_tree(proc):
    if proc.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
    else:
        os.killpg(proc.pid, 9)


def main():
    port = 'COM99' if os.name == 'nt' else '/dev/ttyNOPE'
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUNBUFFERED='1')
    kwargs = {} if os.name == 'nt' else {'start_new_session': True}
    launch = subprocess.Popen(['ros2', 'launch', 'sensor_motor_lab', 'lab.launch.py', f'port:={port}'],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True,
                              encoding='utf-8', errors='replace', shell=(os.name == 'nt'), **kwargs)
    try:
        nodes = ''
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline and launch.poll() is None:
            time.sleep(2)
            result = subprocess.run(['ros2', 'node', 'list', '--no-daemon'], capture_output=True, text=True,
                                    env=env, shell=(os.name == 'nt'), timeout=30)
            nodes = result.stdout
            if '/sensor_motor_bridge' in nodes and 'rqt' in nodes:
                break
        print('ros2 node list:\n' + nodes.strip())
        assert launch.poll() is None, 'launch exited early'
        assert '/sensor_motor_bridge' in nodes, 'bridge node missing'
        assert 'rqt' in nodes, 'rqt panel node missing'
        print('PASS: lab.launch.py starts lab_bridge and the rqt panel (offscreen); no hardware attached.')
    finally:
        kill_tree(launch)
        output = launch.communicate(timeout=10)[0] if launch.stdout else ''
        print('--- launch output (tail) ---\n' + '\n'.join(output.splitlines()[-12:]))


if __name__ == '__main__':
    sys.exit(main())
