"""Gait tests: pure Python, no ROS. Run anywhere:  python -m pytest -q ros2_ws/src/cloudpaw_description/test"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cloudpaw_description.gait import (  # noqa: E402
    JOINTS, SIT, STAND, LegGeometry, TrotParams, foot_target, leg_fk, leg_ik, trot_angles, within_limits,
)


@pytest.mark.parametrize("x, z", [(0.0, 0.124), (0.02, 0.124), (-0.02, 0.11), (0.03, 0.10)])
def test_ik_then_fk_returns_the_same_foot(x, z):
    hip, knee = leg_ik(x, z)
    fx, fz = leg_fk(hip, knee)
    assert fx == pytest.approx(x, abs=1e-9) and fz == pytest.approx(z, abs=1e-9)
    assert knee <= 0  # knee bends backward


def test_unreachable_foot_is_refused():
    with pytest.raises(ValueError):
        leg_ik(0.0, 0.2)  # longer than thigh + shin


def test_the_stand_pose_puts_the_foot_under_the_hip_at_the_stand_height():
    x, z = leg_fk(STAND["FL_hip"], STAND["FL_knee"])
    assert abs(x) < 0.005 and z == pytest.approx(TrotParams().height, abs=0.002)


def test_stance_is_on_the_ground_and_swing_lifts():
    p = TrotParams()
    for ph in (0.0, 0.1, 0.25, 0.4):
        assert foot_target(ph, p)[1] == pytest.approx(p.height)
    lifted = foot_target(0.75, p)[1]
    assert lifted == pytest.approx(p.height - p.step_height, abs=1e-9)


def test_stance_pushes_backward_and_swing_returns_forward():
    p = TrotParams()
    assert foot_target(0.0, p)[0] > foot_target(0.49, p)[0]  # stance: forward -> back
    assert foot_target(0.51, p)[0] < foot_target(0.99, p)[0]  # swing: back -> forward


def test_trot_moves_diagonal_pairs_together():
    for t in (0.0, 0.13, 0.37):
        a = trot_angles(t)
        assert a["FL_hip"] == pytest.approx(a["RR_hip"]) and a["FR_hip"] == pytest.approx(a["RL_hip"])
        assert a["FL_knee"] == pytest.approx(a["RR_knee"])
    a = trot_angles(0.1)
    assert a["FL_hip"] != pytest.approx(a["FR_hip"])  # the pairs are out of phase


def test_turning_shortens_one_side():
    left = trot_angles(0.05, TrotParams(turn=0.6))
    straight = trot_angles(0.05, TrotParams())
    assert abs(left["FL_hip"] - STAND["FL_hip"]) < abs(straight["FL_hip"] - STAND["FL_hip"])


@pytest.mark.parametrize("params", [TrotParams(), TrotParams(step_length=-0.04), TrotParams(turn=1.0), TrotParams(step_length=0.06, step_height=0.035)])
def test_a_whole_cycle_stays_within_the_joint_limits(params):
    for i in range(200):
        assert within_limits(trot_angles(i / 200 / params.frequency, params))


def test_poses_name_the_eight_joints_and_are_within_limits():
    assert set(STAND) == set(SIT) == set(JOINTS) and len(JOINTS) == 8
    assert within_limits(STAND) and within_limits(SIT)
    assert not within_limits({**STAND, "FL_knee": 0.3})


def test_sit_is_lower_than_stand():
    assert leg_fk(SIT["FL_hip"], SIT["FL_knee"])[1] < leg_fk(STAND["FL_hip"], STAND["FL_knee"])[1]


def test_custom_geometry():
    g = LegGeometry(thigh=0.1, shin=0.1)
    hip, knee = leg_ik(0.0, 0.15, g)
    assert leg_fk(hip, knee, g)[1] == pytest.approx(0.15)
    assert math.isfinite(hip)
