"""CloudPaw in Gazebo Harmonic with ros2_control (physics). Joint position controller + trot node via a trajectory bridge.

    ros2 launch cloudpaw_description gazebo.launch.py            # headless server (EC2)
    ros2 launch cloudpaw_description gazebo.launch.py gui:=true  # with a screen
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    share = get_package_share_directory("cloudpaw_description")
    xacro = os.path.join(share, "urdf", "cloudpaw.urdf.xacro")
    robot_description = ParameterValue(Command(["xacro ", xacro, " use_gazebo:=true"]), value_type=str)
    gz = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory("ros_gz_sim"), "launch", "gz_sim.launch.py")),
        launch_arguments={"gz_args": PythonExpression(["'-r empty.sdf' if '", LaunchConfiguration("gui"), "' == 'true' else '-r -s empty.sdf'"])}.items(),
    )
    spawn = Node(package="ros_gz_sim", executable="create", output="screen",
                 arguments=["-topic", "robot_description", "-name", "cloudpaw", "-z", "0.16"])
    clock = Node(package="ros_gz_bridge", executable="parameter_bridge", arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"])
    spawners = [Node(package="controller_manager", executable="spawner", arguments=[c, "--controller-manager-timeout", "60"])
                for c in ("joint_state_broadcaster", "leg_position_controller")]
    return LaunchDescription([
        DeclareLaunchArgument("gui", default_value="false"),
        gz,
        Node(package="robot_state_publisher", executable="robot_state_publisher",
             parameters=[{"robot_description": robot_description, "use_sim_time": True}]),
        clock, spawn,
        TimerAction(period=5.0, actions=spawners),
    ])
