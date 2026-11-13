"""Real ROS 2 graph check: actual rclpy LabBridge node + actual topics/QoS.

The bridge's serial port is replaced by the C++ firmware simulator
(tests/firmware/host_cli.cpp, real controller core + synthetic plant), so this
needs no Uno. An "operator" node talks to the bridge only through ROS topics:
it must receive the latched /lab/config even though it subscribes late, send
the operator heartbeat, ARM, command the servo, and see the ACK + new state.

Usage (sensorMotorLab env or a sourced ROS 2 install):
    python tests/ros/ros_graph_check.py [path/to/host_cli]
If no simulator path is given it is compiled into a temp dir with $CXX/c++/g++.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ros2_ws' / 'src' / 'sensor_motor_lab'))
sys.path.insert(0, str(ROOT / 'tests' / 'python'))

import rclpy  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from std_msgs.msg import Float32, String  # noqa: E402

from firmware_bridge_e2e import ProcessSerial  # noqa: E402
from sensor_motor_lab import bridge as bridge_module  # noqa: E402


def simulator_path():
    if len(sys.argv) > 1:
        return sys.argv[1]
    cxx = next((shutil.which(n) for n in (os.environ.get('CXX'), 'c++', 'g++', 'clang++') if n and shutil.which(n)), None)
    if not cxx:
        raise SystemExit('No C++ compiler to build tests/firmware/host_cli.cpp; pass its path instead.')
    out = Path(tempfile.mkdtemp()) / ('host_cli.exe' if os.name == 'nt' else 'host_cli')
    threads = [] if os.name == 'nt' else ['-pthread']
    subprocess.run([cxx, '-std=c++11', '-O2', *threads, str(ROOT / 'tests/firmware/host_cli.cpp'), '-o', str(out)], check=True)
    return str(out)


class Operator(Node):
    def __init__(self):
        super().__init__('lab_graph_check_operator')
        self.states, self.events, self.raws, self.configs, self.plots = [], [], [], [], []
        self.command_pub = self.create_publisher(String, '/lab/command', 10)
        self.alive_pub = self.create_publisher(String, '/lab/operator_alive', 10)
        self.create_subscription(String, '/lab/state', lambda m: self.states.append(json.loads(m.data)), 10)
        self.create_subscription(String, '/lab/event', lambda m: self.events.append(json.loads(m.data)), 10)
        self.create_subscription(String, '/lab/raw', lambda m: self.raws.append(json.loads(m.data)), 10)
        self.create_subscription(Float32, '/lab/sonar_cm', lambda m: self.plots.append(m.data), 10)

    def subscribe_config_late(self):
        self.create_subscription(String, '/lab/config', lambda m: self.configs.append(json.loads(m.data)),
                                 bridge_module.LATCHED)

    def send(self, verb, value=0):
        self.command_pub.publish(String(data=json.dumps(dict(verb=verb, value=value))))

    def alive(self):
        self.alive_pub.publish(String(data='alive'))


def main():
    simulator = simulator_path()
    devices = []

    def open_simulator(port, baud):
        devices.append(ProcessSerial(simulator))
        return devices[-1]

    bridge_module.open_uno = open_simulator
    rclpy.init()
    bridge = bridge_module.LabBridge()
    operator = Operator()
    executor = SingleThreadedExecutor()
    executor.add_node(bridge)
    executor.add_node(operator)
    checks = []

    def spin_until(predicate, seconds, what, heartbeat=False):
        deadline = time.monotonic() + seconds
        next_alive = 0.0
        while time.monotonic() < deadline:
            if heartbeat and time.monotonic() >= next_alive:
                operator.alive()
                next_alive = time.monotonic() + 0.3
            executor.spin_once(timeout_sec=0.02)
            if predicate():
                checks.append(what)
                print('ok  ', what, flush=True)
                return
        raise AssertionError(f'timed out waiting for: {what}; last events={operator.events[-5:]}')

    try:
        topics = dict(bridge.get_topic_names_and_types())
        for name in ('/lab/state', '/lab/raw', '/lab/event', '/lab/config', '/lab/command', '/lab/operator_alive', '/lab/ir_cm'):
            assert name in topics, f'{name} missing from the ROS graph: {sorted(topics)}'
        checks.append('bridge advertises/subscribes all /lab topics')
        spin_until(lambda: operator.states and operator.raws, 8, '/lab/state and /lab/raw arrive over DDS')
        spin_until(lambda: bridge.link.config is not None, 3, 'bridge received firmware CONFIG')
        operator.subscribe_config_late()
        spin_until(lambda: operator.configs, 3, 'late subscriber gets latched /lab/config (TRANSIENT_LOCAL)')
        assert operator.configs[-1]['protocol'] == 2
        spin_until(lambda: operator.plots, 2, 'Float32 plot topic /lab/sonar_cm publishes')
        assert not operator.states[-1]['armed'], 'bridge must never auto-ARM'
        operator.send('ARM')
        spin_until(lambda: any(e['kind'] == 'rejected' for e in operator.events), 2,
                   'ARM without operator heartbeat is rejected by the bridge')
        started = time.monotonic()
        spin_until(lambda: time.monotonic() - started > 0.6, 2, 'operator heartbeat published for 0.6 s', heartbeat=True)
        operator.send('ARM')
        spin_until(lambda: operator.states[-1]['armed'], 3, 'ARM accepted via /lab/command -> serial -> firmware', heartbeat=True)
        operator.send('SERVO', 45)
        spin_until(lambda: operator.states[-1]['servo_cmd_deg'] == 45, 3, 'SERVO 45 executed and reported on /lab/state', heartbeat=True)
        operator.send('SERVO', 70)  # inside the protocol's outer 0..180, outside the firmware CONFIG 0..60
        spin_until(lambda: any(e['kind'] == 'rejected' and 'SERVO' in e.get('detail', '') for e in operator.events), 2,
                   'out-of-CONFIG-range command rejected before reaching the Uno', heartbeat=True)
        spin_until(lambda: not operator.states[-1]['armed'], 4,
                   'operator heartbeat loss -> bridge requests STOP -> disarmed')
        print(f'PASS: {len(checks)} real ROS 2 graph checks (rclpy {os.environ.get("ROS_DISTRO", "?")}); '
              'serial endpoint was the C++ firmware simulator, not a physical Uno.')
    finally:
        executor.shutdown()
        bridge.destroy_node()
        operator.destroy_node()
        rclpy.try_shutdown()
        for device in devices:
            device.close()


if __name__ == '__main__':
    main()
