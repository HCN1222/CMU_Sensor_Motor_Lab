"""Start the serial bridge and the rqt control panel.

    ros2 launch sensor_motor_lab lab.launch.py port:=COM5          # Windows
    ros2 launch sensor_motor_lab lab.launch.py port:=/dev/ttyACM0  # Linux
    ros2 launch sensor_motor_lab lab.launch.py gui:=false          # bridge only
"""
import sys

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

if sys.platform.startswith('win'):
    DEFAULT_PORT = 'COM5'
elif sys.platform == 'darwin':
    DEFAULT_PORT = '/dev/cu.usbmodem101'
else:
    DEFAULT_PORT = '/dev/ttyACM0'


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('port', default_value=DEFAULT_PORT,
                              description='Uno serial port (close Arduino Serial Monitor first)'),
        DeclareLaunchArgument('gui', default_value='true', description='also start the rqt panel'),
        Node(package='sensor_motor_lab', executable='lab_bridge',
             parameters=[{'port': LaunchConfiguration('port'), 'baud': 115200}],
             output='screen'),
        # `rqt` exists as an executable on Linux, macOS and Windows (RoboStack);
        # the rqt_gui package's libexec script is not directly runnable on Windows.
        ExecuteProcess(cmd=['rqt', '--standalone', 'sensor_motor_lab.dashboard.LabDashboard'],
                       output='screen', condition=IfCondition(LaunchConfiguration('gui'))),
    ])
