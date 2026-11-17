#!/usr/bin/env python3
"""Drive the Gazebo position controller with the trot gait (open loop): see the CloudPaw walk WITH physics.

    ros2 run cloudpaw_description gz_trot.py --ros-args -p speed:=0.15 -p seconds:=10
Publishes /leg_position_controller/commands at 50 Hz; stands for 1 s first, ends standing.
"""
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

from cloudpaw_description.gait import JOINTS, STAND, TrotParams, trot_angles


class GzTrot(Node):
    def __init__(self):
        super().__init__("cloudpaw_gz_trot")
        self.declare_parameter("speed", 0.15)
        self.declare_parameter("seconds", 10.0)
        self.speed = float(self.get_parameter("speed").value)
        self.duration = float(self.get_parameter("seconds").value)
        self.pub = self.create_publisher(Float64MultiArray, "leg_position_controller/commands", 10)
        self.t0 = time.time()
        self.timer = self.create_timer(0.02, self.tick)

    def tick(self):
        t = time.time() - self.t0
        if t < 1.0 or t > 1.0 + self.duration:
            angles = STAND
        else:
            angles = trot_angles(t - 1.0, TrotParams(step_length=self.speed / TrotParams().frequency))
        self.pub.publish(Float64MultiArray(data=[float(angles[j]) for j in JOINTS]))
        if t > 2.0 + self.duration:
            self.get_logger().info("done")
            raise SystemExit


def main():
    rclpy.init()
    node = GzTrot()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
