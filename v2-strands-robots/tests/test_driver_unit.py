"""Unit tests (no MuJoCo, no network): frames and StrandsRobotsDriver with a fake strands-robots Robot.

Run:  cd v2-strands-robots && uv run --with pytest pytest -q -m "not integration"
"""

import math
from types import SimpleNamespace

import numpy as np
import pytest

from cloudpaw_v2.frames import StartFrame, turned_deg, wrap180, yaw_deg
from cloudpaw_v2.strands_driver import GO2_SIT, GO2_STAND, StrandsRobotsDriver
from cloudpaw.robot import Mode, RobotRefusal
from cloudpaw.toolbox import ToolBox


def quat(yaw_degrees):
    a = math.radians(yaw_degrees) / 2
    return np.array([math.cos(a), 0.0, 0.0, math.sin(a)])


# --- frames ------------------------------------------------------------------------------------------------------


def test_yaw_of_a_quaternion():
    for y in (0, 30, 90, -90, 179):
        assert yaw_deg(quat(y)) == pytest.approx(y, abs=1e-6)


def test_wrap180():
    assert wrap180(190) == pytest.approx(-170) and wrap180(-190) == pytest.approx(170) and wrap180(180) == 180


def test_start_frame_forward_right_and_clockwise_heading():
    f = StartFrame.from_pose([1.0, 2.0, 0.3], quat(90))  # start facing world +y
    x, y, h = f.to_v1([1.0, 3.0, 0.3], quat(90))  # moved 1 m along world +y = forward
    assert (round(x, 6), round(y, 6), round(h, 6)) == (0.0, 1.0, 0.0)
    x, y, h = f.to_v1([2.0, 2.0, 0.3], quat(0))  # moved along world +x = to the RIGHT, and turned right 90
    assert (round(x, 6), round(y, 6), round(h, 6)) == (1.0, 0.0, 90.0)


def test_turned_deg_is_signed_and_short():
    assert turned_deg(170, -170) == pytest.approx(20) and turned_deg(-170, 170) == pytest.approx(-20)


# --- a fake strands-robots Robot -----------------------------------------------------------------------------------


class FakeRobot:
    """Integrates body-frame (vx, vy, wz) commands at 30 Hz, like a policy run. Speeds are scaled by `efficiency`."""

    action_keys = tuple(f"{leg}_{j}_joint" for leg in ("FL", "FR", "RL", "RR") for j in ("hip", "thigh", "calf"))

    def __init__(self, yaw=10.0, efficiency=0.4, fall_after=None, z=0.12):
        self.x, self.y, self.yaw, self.z = 0.5, -0.2, yaw, z
        self.efficiency, self.fall_after = efficiency, fall_after
        self.holds, self.estops, self.gains, self.runs = 0, [], None, []

    @property
    def pose(self):
        return SimpleNamespace(position=np.array([self.x, self.y, self.z]), orientation=quat(self.yaw))

    def run(self, policy, seconds=None, stop_when=None, **_):
        self.runs.append(policy)
        if callable(policy):  # a joint-target policy (Go2 stand/sit): nothing moves in the fake
            return SimpleNamespace(stopped_by="seconds", seconds=seconds)
        vx, vy, wz = policy
        dt, t, steps = 1 / 30, 0.0, 0
        while t < seconds:
            a = math.radians(self.yaw)
            self.x += (vx * math.cos(a) - vy * math.sin(a)) * self.efficiency * dt
            self.y += (vx * math.sin(a) + vy * math.cos(a)) * self.efficiency * dt
            self.yaw = wrap180(self.yaw + math.degrees(wz) * self.efficiency * dt)
            t += dt
            steps += 1
            if self.fall_after is not None and steps >= self.fall_after:
                self.z = 0.03
            if stop_when and stop_when(SimpleNamespace(pose=self.pose)):
                return SimpleNamespace(stopped_by="stop_when", seconds=t)
        return SimpleNamespace(stopped_by="seconds", seconds=t)

    def hold(self):
        self.holds += 1

    def estop(self, by=None):
        self.estops.append(by)

    def set_gains(self, kp, kd):
        self.gains = (kp, kd)


def duck(**kw):
    robot = FakeRobot(**kw)
    return StrandsRobotsDriver("microduck", robot=robot, gait=lambda vx, vy, wz: (vx, vy, wz)), robot


# --- the microduck path (closed loop) -----------------------------------------------------------------------------


def test_walk_forward_reaches_the_measured_distance_in_the_v1_frame():
    d, _ = duck()
    d.walk("forward", 0.5)
    p = d.pose()
    assert p.y == pytest.approx(0.5, abs=0.02) and abs(p.x) < 0.02 and p.heading == pytest.approx(0, abs=0.5)


@pytest.mark.parametrize("direction, axis, sign", [("backward", "y", -1), ("left", "x", -1), ("right", "x", 1)])
def test_other_directions(direction, axis, sign):
    d, _ = duck()
    d.walk(direction, 0.3)
    assert getattr(d.pose(), axis) == pytest.approx(sign * 0.3, abs=0.02)


@pytest.mark.parametrize("side, heading", [("right", 90), ("left", 270)])
def test_turn_uses_the_v1_clockwise_heading(side, heading):
    d, _ = duck()
    d.turn(side, 90)
    assert d.pose().heading == pytest.approx(heading, abs=2)


def test_a_180_degree_turn_does_not_stop_early_at_the_wrap():
    d, _ = duck(yaw=170.0)  # starts close to the +-180 wrap
    d.turn("left", 180)
    assert d.pose().heading == pytest.approx(180, abs=2)


def test_every_move_ends_holding_the_pose():
    d, robot = duck()
    d.walk("forward", 0.2)
    d.turn("left", 45)
    assert robot.holds == 2


def test_a_slow_robot_is_reported_not_silently_short():
    d, _ = duck(efficiency=0.01)
    with pytest.raises(RobotRefusal) as e:
        d.walk("forward", 1.0)
    assert e.value.code == "did_not_reach"


def test_a_fall_stops_the_move_and_further_moves_are_refused():
    d, robot = duck(fall_after=5)
    with pytest.raises(RobotRefusal) as e:
        d.walk("forward", 1.0)
    assert e.value.code == "fallen" and robot.holds >= 1
    with pytest.raises(RobotRefusal) as e2:
        d.walk("forward", 0.2)
    assert e2.value.code == "fallen"


def test_state_rules_match_v1():
    d, _ = duck()
    d.sit()
    with pytest.raises(RobotRefusal):
        d.walk("forward", 0.2)
    d.stand()
    d.follow("me")
    with pytest.raises(RobotRefusal):
        d.turn("left", 10)
    d.stop()
    assert d.mode() is Mode.STANDING


def test_stop_never_latches_but_emergency_stop_uses_the_library_estop():
    d, robot = duck()
    d.stop()
    assert robot.estops == []
    d.emergency_stop(by="operator")
    assert robot.estops == ["operator"]


# --- the quadruped path (Go2) ------------------------------------------------------------------------------------


def test_go2_without_a_gait_policy_refuses_to_walk_but_stands_and_sits():
    robot = FakeRobot()
    d = StrandsRobotsDriver("unitree_go2", robot=robot)
    assert robot.gains == ([40.0] * 12, [1.0] * 12)  # made position-controlled
    with pytest.raises(RobotRefusal) as e:
        d.walk("forward", 0.5)
    assert e.value.code == "no_gait_policy"
    d.sit()
    d.stand()
    targets = [p(None) for p in robot.runs if callable(p)]
    assert [list(t.values()) for t in targets[-2:]] == [GO2_SIT, GO2_STAND]


def test_go2_with_a_gait_policy_walks():
    robot = FakeRobot()
    d = StrandsRobotsDriver("unitree_go2", robot=robot, gait=lambda vx, vy, wz: (vx, vy, wz))
    d.walk("forward", 0.4)
    assert d.pose().y == pytest.approx(0.4, abs=0.02)


# --- the V1 tools and limits on top of it --------------------------------------------------------------------------


def test_v1_toolbox_limits_still_apply_on_the_new_driver():
    d, _ = duck()
    box = ToolBox(d)
    assert box.walk("forward", 50)["reason"] == "out_of_range"
    ok = box.walk("forward", 0.5)
    assert ok["ok"] and ok["y_m"] == pytest.approx(0.5, abs=0.02)
    assert box.turn("right", 90)["heading_deg"] == pytest.approx(90, abs=2)


def test_a_driver_refusal_becomes_a_structured_tool_result():
    box = ToolBox(StrandsRobotsDriver("unitree_go2", robot=FakeRobot()))
    r = box.walk("forward", 0.5)
    assert r["ok"] is False and r["reason"] == "no_gait_policy" and "PPO" in r["message"]
