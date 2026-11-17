"""Integration tests for the MuJoCo training environment (Go2 as an 8-DoF proxy). Needs the Menagerie model in the cache
(downloaded the first time a strands-robots Go2 is loaded). Run: uv run --with pytest pytest -q -m integration"""

import os

import numpy as np
import pytest

from cloudpaw_rl.env_mujoco import GO2_SCENE, CloudPawEnv
from cloudpaw_rl.spec import ObsLayout

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.path.exists(GO2_SCENE), reason="Go2 model not downloaded")]


def test_zero_action_keeps_the_proxy_standing_and_pays():
    env = CloudPawEnv(command=np.array([0.0, 0.0]))
    obs, info = env.reset(seed=0)
    assert obs.shape == (ObsLayout(8).size,) and env.dt == pytest.approx(0.02)
    total = 0.0
    for _ in range(100):  # 2 s
        obs, r, terminated, truncated, info = env.step(np.zeros(8))
        total += r
        assert not terminated
    assert info["height"] > 0.2 and total > 0


def test_random_actions_stay_finite():
    env = CloudPawEnv()
    env.reset(seed=1)
    rng = np.random.default_rng(1)
    for _ in range(300):
        obs, r, terminated, truncated, info = env.step(rng.uniform(-1, 1, 8))
        assert np.all(np.isfinite(obs)) and np.isfinite(r)
        if terminated or truncated:
            env.reset()


def test_a_collapse_is_detected_as_a_fall():
    env = CloudPawEnv(kp=0.0)
    env.reset(seed=0)
    for _ in range(100):
        _, _, terminated, _, _ = env.step(np.zeros(8))
        if terminated:
            return
    pytest.fail("a robot without motor torque was never reported as fallen")


def test_seed_reproducibility_and_command_ranges():
    a, b = CloudPawEnv(), CloudPawEnv()
    _, ia = a.reset(seed=42)
    _, ib = b.reset(seed=42)
    assert np.allclose(ia["command"], ib["command"])
    assert abs(ia["command"][0]) <= a.spec.max_cmd_vx and abs(ia["command"][1]) <= a.spec.max_cmd_wz


def test_episode_is_truncated_at_its_length():
    env = CloudPawEnv(episode_s=0.2, command=np.zeros(2))
    env.reset(seed=0)
    out = [env.step(np.zeros(8)) for _ in range(10)]
    assert out[-1][3] is True and not any(o[2] for o in out)


def test_info_exposes_each_reward_term():
    env = CloudPawEnv(command=np.array([0.2, 0.0]))
    env.reset(seed=0)
    _, r, _, _, info = env.step(np.zeros(8))
    assert set(info["terms"]) >= {"track_vx", "orientation", "action_rate", "alive"}
    assert r == pytest.approx(sum(info["terms"].values()))
