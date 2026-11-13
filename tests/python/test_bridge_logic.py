"""Bridge callbacks with import shims; deliberately not a ROS middleware test.

The real ROS 2 graph is exercised by tests/ros/ros_graph_check.py.
"""
import importlib
import json
import sys
import types
import unittest
from unittest.mock import patch

from sensor_motor_lab.operator_lease import OperatorLease


class Message:
    def __init__(self, data=None):
        self.data = data


class Publisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message.data)


class Link:
    def __init__(self):
        self.commands = []
        self.ticks = 0

    def tick(self):
        self.ticks += 1

    def submit(self, verb, value):
        self.commands.append((verb, value))


class BridgeLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy = types.ModuleType('rclpy')
        rclpy.ok = lambda: True
        node = types.ModuleType('rclpy.node')
        node.Node = type('Node', (), {})
        qos = types.ModuleType('rclpy.qos')
        qos.QoSProfile = lambda **kwargs: kwargs
        qos.DurabilityPolicy = types.SimpleNamespace(TRANSIENT_LOCAL='transient_local')
        qos.ReliabilityPolicy = types.SimpleNamespace(RELIABLE='reliable')
        messages = types.ModuleType('std_msgs.msg')
        messages.String = messages.Float32 = Message
        replacements = {'rclpy': rclpy, 'rclpy.node': node, 'rclpy.qos': qos,
                        'std_msgs': types.ModuleType('std_msgs'), 'std_msgs.msg': messages,
                        'serial': types.ModuleType('serial')}
        with patch.dict(sys.modules, replacements):
            sys.modules.pop('sensor_motor_lab.bridge', None)
            cls.module = importlib.import_module('sensor_motor_lab.bridge')
            cls.Bridge = cls.module.LabBridge
        sys.modules.pop('sensor_motor_lab.bridge', None)

    def setUp(self):
        self.now = [0.0]
        self.bridge = object.__new__(self.Bridge)
        self.bridge.operator = OperatorLease(lambda: self.now[0])
        self.bridge.link = Link()
        self.bridge.controller_armed = True
        self.bridge.operator_stop_sent = False
        self.events = []
        self.bridge.on_event = self.events.append

    def test_expired_operator_sends_stop_once(self):
        self.bridge.tick()
        self.bridge.tick()
        self.assertEqual(self.bridge.link.commands, [('STOP', 0)])
        self.assertEqual(self.events[0]['kind'], 'operator_timeout')

    def test_heartbeat_allows_explicit_arm_but_does_not_arm_itself(self):
        self.bridge.on_operator(Message('alive'))
        self.bridge.tick()
        self.assertEqual(self.bridge.link.commands, [])
        self.bridge.on_command(Message(json.dumps(dict(verb='ARM', value=0))))
        self.assertEqual(self.bridge.link.commands, [('ARM', 0.0)])

    def test_no_heartbeat_rejects_motion_but_stop_is_always_allowed(self):
        self.bridge.on_command(Message(json.dumps(dict(verb='DC_MOVE', value=90))))
        self.assertEqual(self.events[-1]['kind'], 'rejected')
        self.assertEqual(self.bridge.link.commands, [])
        self.bridge.on_command(Message(json.dumps(dict(verb='STOP', value=0))))
        self.assertEqual(self.bridge.link.commands, [('STOP', 0.0)])

    def test_heartbeat_loss_after_connection_stops_without_rearming(self):
        self.bridge.on_operator(Message('alive'))
        self.bridge.tick()
        self.now[0] = 1.6
        self.bridge.tick()
        self.assertEqual(self.bridge.link.commands, [('STOP', 0)])
        self.bridge.on_operator(Message('alive'))
        self.bridge.tick()
        self.assertEqual(self.bridge.link.commands, [('STOP', 0)])

    def test_config_event_goes_to_latched_config_topic(self):
        bridge = object.__new__(self.Bridge)
        bridge.config_pub, bridge.event_pub, bridge.raw_pub = Publisher(), Publisher(), Publisher()
        bridge.get_logger = lambda: types.SimpleNamespace(info=lambda *_: None, warning=lambda *_: None)
        with patch.object(self.module, 'rclpy', types.SimpleNamespace(ok=lambda: True)):
            bridge.on_event(dict(kind='config', data={'max_rpm': 30.0}))
            bridge.on_event(dict(kind='raw', data={'enc_counts': 5}))
        self.assertEqual(json.loads(bridge.config_pub.messages[0]), {'max_rpm': 30.0})
        self.assertEqual(json.loads(bridge.raw_pub.messages[0]), {'enc_counts': 5})
        self.assertEqual(self.module.LATCHED['durability'], 'transient_local')

    def test_default_port_matches_platform(self):
        with patch.object(self.module.sys, 'platform', 'win32'):
            self.assertEqual(self.module.default_port(), 'COM5')
        with patch.object(self.module.sys, 'platform', 'linux'):
            self.assertEqual(self.module.default_port(), '/dev/ttyACM0')


if __name__ == '__main__':
    unittest.main()
