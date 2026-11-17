#!/usr/bin/env python3
"""CloudPaw trot demo node (ROS 2 Jazzy).

Publishes /joint_states at 50 Hz and the odom -> base_link transform, so robot_state_publisher, RViz and Foxglove show the
quadruped walking. Commands:
  /cmd_vel (geometry_msgs/Twist)   linear.x m/s (forward/back), angular.z rad/s (turn). Zero -> stands still.
  /cloudpaw/mode (std_msgs/String) "stand" | "sit" | "walk"
The body pose is the commanded motion integrated (open loop): a visualization, not physics. Physics: Gazebo launch.
"""

import math

import rclpy
from geometry_msgs.msg import TransformStamped, Twist
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from tf2_ros import TransformBroadcaster

from cloudpaw_description.gait import JOINTS, SIT, STAND, TrotParams, trot_angles

MAX_VX, MAX_WZ = 0.25, 1.0  # same command limits as the RL spec


class TrotNode(Node):
    def __init__(self):
        super().__init__("cloudpaw_trot")
        self.declare_parameter("rate_hz", 50.0)
        self.declare_parameter("demo", True)  # without /cmd_vel, walk a square so the robot moves on its own
        self.rate = float(self.get_parameter("rate_hz").value)
        self.demo = bool(self.get_parameter("demo").value)
        self.joints_pub = self.create_publisher(JointState, "joint_states", 10)
        self.tf = TransformBroadcaster(self)
        self.create_subscription(Twist, "cmd_vel", self.on_cmd, 10)
        self.create_subscription(String, "cloudpaw/mode", self.on_mode, 10)
        self.vx = self.wz = 0.0
        self.mode = "walk" if self.demo else "stand"
        self.x = self.y = self.yaw = 0.0
        self.t = 0.0
        self.last_cmd = None
        self.timer = self.create_timer(1.0 / self.rate, self.tick)
        self.get_logger().info(f"CloudPaw trot: {len(JOINTS)} joints at {self.rate:.0f} Hz, demo={self.demo}")

    def on_cmd(self, msg: Twist):
        self.vx = max(-MAX_VX, min(MAX_VX, msg.linear.x))
        self.wz = max(-MAX_WZ, min(MAX_WZ, msg.angular.z))
        self.last_cmd = self.t
        self.demo = False

    def on_mode(self, msg: String):
        if msg.data in ("stand", "sit", "walk"):
            self.mode = msg.data
            self.get_logger().info(f"mode: {self.mode}")

    def demo_command(self):
        """A square: 4 s forward, 1.6 s turning left (~90 degrees at 1 rad/s), repeat."""
        s = self.t % 5.6
        return (0.15, 0.0) if s < 4.0 else (0.0, 1.0)

    def tick(self):
        dt = 1.0 / self.rate
        self.t += dt
        if self.demo:
            self.vx, self.wz = self.demo_command()
        elif self.last_cmd is not None and self.t - self.last_cmd > 0.5:  # no command for 0.5 s: stop (like the ESP32)
            self.vx = self.wz = 0.0
        moving = self.mode == "walk" and (abs(self.vx) > 1e-3 or abs(self.wz) > 1e-3)
        if self.mode == "sit":
            angles = SIT
        elif moving:
            step = self.vx / TrotParams().frequency  # stride per cycle that matches the commanded speed
            turn = max(-1.0, min(1.0, self.wz / MAX_WZ))
            angles = trot_angles(self.t, TrotParams(step_length=step if abs(step) > 1e-3 else 0.02, turn=turn))
            self.yaw += self.wz * dt
            self.x += self.vx * math.cos(self.yaw) * dt
            self.y += self.vx * math.sin(self.yaw) * dt
        else:
            angles = STAND
        now = self.get_clock().now().to_msg()
        js = JointState()
        js.header.stamp = now
        js.name = list(JOINTS)
        js.position = [float(angles[j]) for j in JOINTS]
        self.joints_pub.publish(js)
        tf = TransformStamped()
        tf.header.stamp = now
        tf.header.frame_id = "odom"
        tf.child_frame_id = "base_link"
        tf.transform.translation.x, tf.transform.translation.y = self.x, self.y
        tf.transform.translation.z = 0.136 if self.mode != "sit" else 0.08
        tf.transform.rotation.z, tf.transform.rotation.w = math.sin(self.yaw / 2), math.cos(self.yaw / 2)
        self.tf.sendTransform(tf)


def main():
    rclpy.init()
    node = TrotNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
