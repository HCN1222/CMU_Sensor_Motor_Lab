"""ROS 2 serial bridge. The Uno runs motor control locally; this node relays."""
import json
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Float32, String
import serial

from .link import SerialLink
from .protocol import command_from_json
from .operator_lease import OperatorLease

# Latched topic: a GUI started after the bridge still receives the last CONFIG.
LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     reliability=ReliabilityPolicy.RELIABLE)
PLOT_FIELDS = ('pot_deg', 'pot_pct', 'ir_raw_cm', 'ir_cm', 'sonar_cm',
               'dc_deg', 'dc_rpm', 'dc_target', 'step_deg', 'step_target_deg')


def default_port():
    if sys.platform.startswith('win'):
        return 'COM5'
    if sys.platform == 'darwin':
        return '/dev/cu.usbmodem101'
    return '/dev/ttyACM0'


class LabBridge(Node):
    def __init__(self):
        super().__init__('sensor_motor_bridge')
        self.declare_parameter('port', default_port())
        self.declare_parameter('baud', 115200)
        port = self.get_parameter('port').value
        baud = int(self.get_parameter('baud').value)
        self.state_pub = self.create_publisher(String, '/lab/state', 10)
        self.raw_pub = self.create_publisher(String, '/lab/raw', 10)
        self.event_pub = self.create_publisher(String, '/lab/event', 10)
        self.config_pub = self.create_publisher(String, '/lab/config', LATCHED)
        self.plots = {name: self.create_publisher(Float32, '/lab/' + name, 10) for name in PLOT_FIELDS}
        self.link = SerialLink(
            lambda: open_uno(port, baud),
            time.monotonic, self.on_state, self.on_event)
        self.operator = OperatorLease(time.monotonic)
        self.controller_armed = False
        self.operator_stop_sent = False
        self.create_subscription(String, '/lab/command', self.on_command, 10)
        self.create_subscription(String, '/lab/operator_alive', self.on_operator, 10)
        self.create_timer(0.02, self.tick)
        self.get_logger().info(f'Opening {port} at {baud}; controller starts disarmed.')

    def on_state(self, state):
        self.controller_armed = state.armed
        values = state.as_dict()
        self.state_pub.publish(String(data=json.dumps(values, allow_nan=False)))
        for name, publisher in self.plots.items():
            publisher.publish(Float32(data=float(values[name])))

    def on_event(self, event):
        if not rclpy.ok():
            return
        if event['kind'] == 'raw':
            self.raw_pub.publish(String(data=json.dumps(event['data'], allow_nan=False)))
            return
        if event['kind'] == 'config':
            self.config_pub.publish(String(data=json.dumps(event['data'], allow_nan=False)))
            self.get_logger().info(f"Firmware CONFIG: {event['data']}")
        self.event_pub.publish(String(data=json.dumps(event, allow_nan=False)))
        if event['kind'] in ('disconnected', 'unconfirmed', 'invalid_frame'):
            self.get_logger().warning(str(event))

    def on_command(self, message):
        try:
            verb, value = command_from_json(message.data)
            if not self.operator.permits(verb):
                raise ValueError('control-panel heartbeat missing; open the lab rqt panel')
            self.link.submit(verb, value)
        except ValueError as exc:
            self.on_event(dict(kind='rejected', detail=str(exc)))

    def on_operator(self, message):
        if message.data == 'alive':
            self.operator.heartbeat()
            self.operator_stop_sent = False

    def tick(self):
        self.link.tick()
        if self.controller_armed and not self.operator.fresh and not self.operator_stop_sent:
            try:
                self.link.submit('STOP', 0)
                self.operator_stop_sent = True
                self.on_event(dict(kind='operator_timeout',
                                   detail='Control-panel heartbeat expired; STOP requested.'))
            except ValueError:
                # SerialLink has already removed the serial heartbeat on failure.
                pass

    def destroy_node(self):
        self.link.close()
        return super().destroy_node()


def open_uno(port, baud):
    connection = serial.Serial(port, baud, timeout=0, write_timeout=0.1)
    try:
        # Pulse DTR to reset a physical Uno so a new sequence-number session begins.
        # (The link also starts from a time-based sequence in case no reset happens.)
        connection.dtr = False
        time.sleep(0.05)
        connection.dtr = True
    except Exception:
        connection.close()
        raise
    return connection


def main(args=None):
    rclpy.init(args=args)
    node = LabBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
