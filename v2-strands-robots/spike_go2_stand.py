"""Spike: the simulated Unitree Go2 standing still (strands-robots 0.6.0, MuJoCo, headless).

Finding (17-nov-2026): the MuJoCo Menagerie Go2 has TORQUE actuators. `Robot.set_gains(kp, kd)` writes the gains but leaves the
actuator bias type as NONE, so the `-kp*q - kd*qdot` terms are ignored: a position target becomes a constant torque and the
robot collapses (z = 0.077 m). Setting the bias type to AFFINE (sim only) makes it a real PD controller: it stands at ~0.23 m.
"""
import warnings

import mujoco

from strands_robots import Robot

warnings.filterwarnings("ignore")
HOME = [0.0, 0.9, -1.8] * 4  # hip, thigh, calf per leg (FL, FR, RL, RR), radians: the model's "home" keyframe


def make_position_controlled(robot, kp=40.0, kd=1.0):
    robot.set_gains(kp=[kp] * 12, kd=[kd] * 12)
    robot.sim.backend.model.actuator_biastype[:] = mujoco.mjtBias.mjBIAS_AFFINE  # workaround, see docstring


go2 = Robot("unitree_go2")
make_position_controlled(go2)
home = dict(zip(go2.action_keys, HOME))
go2.run(lambda obs: home, seconds=3)
z = go2.pose.position[2]
print("z after 3 s holding home: %.3f m -> %s" % (z, "STANDING" if z > 0.2 else "COLLAPSED"))
