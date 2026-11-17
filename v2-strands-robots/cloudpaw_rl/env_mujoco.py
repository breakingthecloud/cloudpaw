"""CloudPaw training environment in MuJoCo — on the Unitree Go2 as a PROXY until CloudPaw's own model (MJCF/URDF) exists.

The Go2 has 12 joints; the hip abduction joints are locked at 0 so the policy controls 8 (hip pitch = "hip", calf =
"knee"), like the inferred CloudPaw. Same observation, action mapping, servo limits and reward as on the robot.
Interface follows gymnasium (reset(seed) -> (obs, info); step(a) -> (obs, reward, terminated, truncated, info)) without
depending on it, so any PPO library can wrap it (Stable-Baselines3, skrl, CleanRL...).
"""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Optional

import mujoco
import numpy as np

from .policy_io import action_to_targets, build_obs
from .reward import RewardWeights, StepState, is_fallen, reward_terms
from .spec import DEFAULT, RobotSpec

GO2_SCENE = os.path.expanduser("~/.cache/robot_descriptions/mujoco_menagerie/unitree_go2/scene.xml")
# The proxy's numbers: the Go2's geometry and stand pose, with the inferred CloudPaw's servo limits and control rate.
GO2_PROXY = replace(DEFAULT, stand_pose_rad=(0.9, -1.8), stand_height_m=0.27, joint_limit_rad=0.9, servo_max_speed_rad_s=10.0)
# Go2 actuator index for each controlled joint (FL, FR, RL, RR) x (thigh, calf); abduction (0, 3, 6, 9) locked at 0.
CONTROLLED = [1, 2, 4, 5, 7, 8, 10, 11]
ABDUCTION = [0, 3, 6, 9]


def _quat_rotate_inverse(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate a world vector into the body frame. q = (w, x, y, z)."""
    w, x, y, z = q
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                  [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                  [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
    return r.T @ v


class CloudPawEnv:
    def __init__(self, spec: RobotSpec = GO2_PROXY, weights: RewardWeights = RewardWeights(), episode_s: float = 10.0,
                 kp: float = 40.0, kd: float = 1.0, scene: str = GO2_SCENE, command: Optional[np.ndarray] = None):
        self.spec, self.weights = spec, weights
        self.model = mujoco.MjModel.from_xml_path(scene)
        self.data = mujoco.MjData(self.model)
        self.kp, self.kd = kp, kd
        self.substeps = max(1, int(round(1.0 / (spec.control_hz * self.model.opt.timestep))))  # 0.002 s physics -> 10
        self.dt = self.substeps * self.model.opt.timestep
        self.max_steps = int(episode_s / self.dt)
        self.fixed_command = command
        self.home_key = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_KEY, "home")
        self.rng = np.random.default_rng()
        self.n_act = spec.n_joints

    # --- helpers ------------------------------------------------------------------------------------------------
    def _base(self):
        q = self.data.qpos[3:7].copy()
        lin_body = _quat_rotate_inverse(q, self.data.qvel[0:3])  # free joint: linear velocity is in the world frame
        ang_body = self.data.qvel[3:6].copy()  # free joint: angular velocity is in the body frame
        gravity_body = _quat_rotate_inverse(q, np.array([0.0, 0.0, -1.0]))
        return lin_body, ang_body, gravity_body, float(self.data.qpos[2])

    def _obs(self):
        _, ang, grav, _ = self._base()
        offsets = self.targets - np.asarray(self.spec.stand_pose)
        return build_obs(projected_gravity=grav, angular_velocity=ang, command=self.command, t=self.t,
                         joint_commanded=offsets, last_action=self.last_action, spec=self.spec)

    def _pd(self, targets_12: np.ndarray):
        q, qd = self.data.qpos[7:], self.data.qvel[6:]
        tau = self.kp * (targets_12 - q) - self.kd * qd
        lo, hi = self.model.actuator_ctrlrange[:, 0], self.model.actuator_ctrlrange[:, 1]
        self.data.ctrl[:] = np.clip(tau, lo, hi)

    # --- gymnasium-style API --------------------------------------------------------------------------------------
    def reset(self, seed: Optional[int] = None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        mujoco.mj_resetDataKeyframe(self.model, self.data, self.home_key)
        mujoco.mj_forward(self.model, self.data)
        self.targets = np.asarray(self.spec.stand_pose, dtype=float)
        self.last_action = np.zeros(self.n_act)
        self.t, self.steps = 0.0, 0
        if self.fixed_command is not None:
            self.command = np.asarray(self.fixed_command, dtype=float)
        else:  # a random command per episode: the policy learns to follow any "walk"/"turn" the agent sends
            self.command = np.array([self.rng.uniform(-self.spec.max_cmd_vx, self.spec.max_cmd_vx),
                                     self.rng.uniform(-self.spec.max_cmd_wz, self.spec.max_cmd_wz)])
        return self._obs(), {"command": self.command.copy()}

    def step(self, action):
        action = np.clip(np.nan_to_num(np.asarray(action, dtype=float)), -1.0, 1.0)
        self.targets = action_to_targets(action, self.targets, self.spec)
        full = np.zeros(12)
        full[CONTROLLED] = self.targets
        full[ABDUCTION] = 0.0
        for _ in range(self.substeps):
            self._pd(full)
            mujoco.mj_step(self.model, self.data)
        self.t += self.dt
        self.steps += 1
        lin, ang, grav, height = self._base()
        s = StepState(lin_vel=lin, ang_vel=ang, projected_gravity=grav, base_height=height, command=self.command,
                      action=action, last_action=self.last_action, joint_offset=self.targets - np.asarray(self.spec.stand_pose))
        terms = reward_terms(s, self.weights, stand_height=self.spec.stand_height_m, joint_limit=self.spec.joint_limit_rad,
                             action_scale=self.spec.action_scale_rad, servo_max_speed=self.spec.servo_max_speed_rad_s, dt=self.dt)
        self.last_action = action
        terminated = is_fallen(grav, height, self.spec.stand_height_m)
        truncated = self.steps >= self.max_steps
        return self._obs(), float(sum(terms.values())), terminated, truncated, {"terms": terms, "height": height}
