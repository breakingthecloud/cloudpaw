"""Tests for the RL pieces (no MuJoCo): spec, reward, policy I/O and the C export for the ESP32.

Run:  cd v2-strands-robots && uv run --with pytest pytest -q tests/test_rl.py
"""

import shutil
import subprocess

import numpy as np
import pytest

from cloudpaw_rl.export_c import forward, to_c_header
from cloudpaw_rl.policy_io import action_to_targets, build_obs, gait_phase
from cloudpaw_rl.reward import RewardWeights, StepState, is_fallen, reward, reward_terms
from cloudpaw_rl.spec import DEFAULT, ObsLayout

KW = dict(stand_height=DEFAULT.stand_height_m, joint_limit=DEFAULT.joint_limit_rad, action_scale=DEFAULT.action_scale_rad,
          servo_max_speed=DEFAULT.servo_max_speed_rad_s, dt=1 / DEFAULT.control_hz)
N = DEFAULT.n_joints


def state(**over):
    base = dict(lin_vel=np.array([0.2, 0, 0.0]), ang_vel=np.zeros(3), projected_gravity=np.array([0, 0, -1.0]),
                base_height=DEFAULT.stand_height_m, command=np.array([0.2, 0.0]), action=np.zeros(N),
                last_action=np.zeros(N), joint_offset=np.zeros(N))
    base.update(over)
    return StepState(**base)


# --- spec -----------------------------------------------------------------------------------------------------------


def test_spec_layout():
    assert N == 8 and len(DEFAULT.joints) == 8 and DEFAULT.joints[:2] == ("FL_hip", "FL_knee")
    layout = ObsLayout(N)
    assert layout.size == 3 + 3 + 2 + 2 + 8 + 8 == 26
    assert layout.slice("command") == slice(6, 8) and layout.slice("last_action") == slice(18, 26)


# --- reward ---------------------------------------------------------------------------------------------------------


def test_tracking_the_command_pays_more_than_not():
    assert reward(state(), **KW) > reward(state(lin_vel=np.array([-0.2, 0, 0.0])), **KW)


def test_yaw_tracking():
    good = state(command=np.array([0.0, 1.0]), ang_vel=np.array([0, 0, 1.0]), lin_vel=np.zeros(3))
    bad = state(command=np.array([0.0, 1.0]), ang_vel=np.zeros(3), lin_vel=np.zeros(3))
    assert reward(good, **KW) > reward(bad, **KW)


@pytest.mark.parametrize("bad", [
    dict(lin_vel=np.array([0.2, 0, 0.5])),  # bouncing
    dict(ang_vel=np.array([2.0, 2.0, 0])),  # rocking
    dict(projected_gravity=np.array([0.5, 0, -0.866])),  # tilted 30 degrees
    dict(base_height=0.06),  # crouched
    dict(action=np.ones(N), last_action=-np.ones(N)),  # jittery and faster than the servos
    dict(joint_offset=np.full(N, 1.19)),  # at the mechanical limit
])
def test_each_bad_behaviour_lowers_the_reward(bad):
    assert reward(state(**bad), **KW) < reward(state(), **KW)


def test_terms_are_finite_signed_and_scaled_by_dt():
    t = reward_terms(state(), RewardWeights(), **KW)
    assert all(np.isfinite(v) for v in t.values())
    assert t["track_vx"] == pytest.approx(1.5 * 1.0 * KW["dt"]) and t["alive"] > 0
    assert all(t[k] <= 0 for k in ("lin_vel_z", "ang_vel_xy", "orientation", "base_height", "action_rate", "servo_speed", "joint_limits"))


def test_only_over_speed_is_penalized():
    slow = state(action=np.full(N, 0.1), last_action=np.zeros(N))  # 0.035 rad per step = 1.75 rad/s < 10
    assert reward_terms(slow, RewardWeights(), **KW)["servo_speed"] == 0.0


def test_fall_detection():
    h = DEFAULT.stand_height_m
    assert not is_fallen(np.array([0, 0, -1.0]), h, h)
    assert is_fallen(np.array([0.8, 0, -0.6]), h, h)  # ~53 degrees
    assert is_fallen(np.array([0, 0, -1.0]), 0.4 * h, h)  # lying on the belly
    assert not is_fallen(np.array([0, 0, -1.0]), 0.6 * h, h)  # crouched, not fallen
    assert is_fallen(np.array([0, 0, 1.0]), h, h)  # upside down


# --- policy I/O -----------------------------------------------------------------------------------------------------


def test_build_obs_order_and_size():
    obs = build_obs(projected_gravity=[0, 0, -1], angular_velocity=[1, 2, 3], command=[0.2, -0.5], t=0.0,
                    joint_commanded=np.arange(N), last_action=-np.arange(N))
    L = ObsLayout(N)
    assert obs.shape == (26,) and obs.dtype == np.float32
    assert list(obs[L.slice("command")]) == pytest.approx([0.2, -0.5])
    assert list(obs[L.slice("gait_phase")]) == pytest.approx([0.0, 1.0])
    assert obs[L.slice("last_action")][1] == -1


def test_build_obs_rejects_a_wrong_joint_count():
    with pytest.raises(ValueError):
        build_obs(projected_gravity=[0, 0, -1], angular_velocity=[0, 0, 0], command=[0, 0], t=0,
                  joint_commanded=np.zeros(N - 1), last_action=np.zeros(N))


def test_gait_phase_period():
    assert gait_phase(0) == pytest.approx(gait_phase(1 / 1.5), abs=1e-9)


def test_action_to_targets_respects_limits_rate_and_nan():
    stand = np.array(DEFAULT.stand_pose)
    t = action_to_targets(np.ones(N), stand)
    assert np.allclose(t - stand, DEFAULT.servo_max_speed_rad_s / DEFAULT.control_hz)  # rate-limited (0.2 rad/step)
    for _ in range(20):
        t = action_to_targets(np.ones(N), t)
    assert np.allclose(t - stand, DEFAULT.action_scale_rad)  # converges to the scaled offset, not beyond
    assert np.allclose(action_to_targets(np.full(N, 9.0), stand + DEFAULT.action_scale_rad), stand + DEFAULT.action_scale_rad)
    assert np.allclose(action_to_targets(np.full(N, np.nan), stand), stand)


# --- C export for the ESP32 -------------------------------------------------------------------------------------------


def random_mlp(sizes, seed=0):
    rng = np.random.default_rng(seed)
    ws = [rng.normal(0, 0.4, (o, i)).astype(np.float32) for i, o in zip(sizes, sizes[1:])]
    bs = [rng.normal(0, 0.1, o).astype(np.float32) for o in sizes[1:]]
    return ws, bs


def test_header_shape_checks():
    ws, bs = random_mlp([26, 64, 8])
    with pytest.raises(ValueError):
        to_c_header([ws[0], ws[0]], bs)


@pytest.mark.skipif(shutil.which("cc") is None, reason="needs a C compiler")
@pytest.mark.parametrize("with_norm", [False, True])
def test_the_c_policy_matches_numpy(tmp_path, with_norm):
    sizes = [26, 64, 64, 8]
    ws, bs = random_mlp(sizes, seed=3)
    rng = np.random.default_rng(7)
    mean = rng.normal(0, 1, 26).astype(np.float32) if with_norm else None
    std = rng.uniform(0.5, 2, 26).astype(np.float32) if with_norm else None
    (tmp_path / "cloudpaw_policy.h").write_text(to_c_header(ws, bs, mean, std))
    obs = rng.normal(0, 1, (5, 26)).astype(np.float32)
    rows = "\n".join("{" + ", ".join(f"{v:.9g}f" for v in o) + "}," for o in obs)
    (tmp_path / "main.c").write_text(f"""#include <stdio.h>
#include "cloudpaw_policy.h"
static const float OBS[5][26] = {{{rows}}};
int main(void) {{ float act[8]; for (int r = 0; r < 5; r++) {{ cloudpaw_policy_forward(OBS[r], act);
  for (int i = 0; i < 8; i++) printf("%.7f ", act[i]); printf("\\n"); }} return 0; }}
""")
    subprocess.run(["cc", "-std=c99", "-O2", "-Wall", "-Werror", "-o", str(tmp_path / "p"), str(tmp_path / "main.c"), "-lm"], check=True)
    got = np.array([[float(x) for x in line.split()] for line in subprocess.run([str(tmp_path / "p")], capture_output=True, text=True, check=True).stdout.splitlines()])
    want = np.array([forward(o, ws, bs, mean, std) for o in obs])
    assert got.shape == (5, 8) and np.max(np.abs(got - want)) < 1e-5


def test_jitter_within_servo_speed_is_still_penalized():
    # 0.2 -> 0.07 rad per step = 3.5 rad/s: within the servo's 10 rad/s, so only action_rate can see it
    jitter = state(action=np.full(N, 0.2), last_action=np.zeros(N))
    terms = reward_terms(jitter, RewardWeights(), **KW)
    assert terms["servo_speed"] == 0.0 and terms["action_rate"] < 0
    assert reward(jitter, **KW) < reward(state(), **KW)
