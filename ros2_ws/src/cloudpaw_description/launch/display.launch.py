"""CloudPaw walking demo without physics: URDF + trot node + robot_state_publisher, viewed in Foxglove (and optionally RViz).

    ros2 launch cloudpaw_description display.launch.py                 # headless (EC2): Foxglove on ws://<host>:8765
    ros2 launch cloudpaw_description display.launch.py rviz:=true      # with a screen
    ros2 launch cloudpaw_description display.launch.py demo:=false     # wait for /cmd_vel instead of walking a square
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    share = get_package_share_directory("cloudpaw_description")
    xacro = os.path.join(share, "urdf", "cloudpaw.urdf.xacro")
    robot_description = ParameterValue(Command(["xacro ", xacro]), value_type=str)
    return LaunchDescription([
        DeclareLaunchArgument("rviz", default_value="false"),
        DeclareLaunchArgument("foxglove", default_value="true"),
        DeclareLaunchArgument("demo", default_value="true"),
        Node(package="robot_state_publisher", executable="robot_state_publisher",
             parameters=[{"robot_description": robot_description}]),
        Node(package="cloudpaw_description", executable="trot_gait.py", name="cloudpaw_trot",
             parameters=[{"demo": LaunchConfiguration("demo")}], output="screen"),
        Node(package="foxglove_bridge", executable="foxglove_bridge", condition=IfCondition(LaunchConfiguration("foxglove")),
             parameters=[{"port": 8765, "address": "127.0.0.1"}]),  # localhost only: reach it through the SSM tunnel
        Node(package="rviz2", executable="rviz2", condition=IfCondition(LaunchConfiguration("rviz")),
             arguments=["-d", os.path.join(share, "config", "cloudpaw.rviz")]),
    ])
