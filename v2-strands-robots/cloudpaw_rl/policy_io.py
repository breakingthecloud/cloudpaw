"""Policy input/output, identical in training and on the ESP32 (the C port mirrors these functions)."""

from __future__ import annotations

import math

import numpy as np

from .spec import DEFAULT, ObsLayout, RobotSpec

GAIT_HZ = 1.5


def gait_phase(t: float, hz: float = GAIT_HZ) -> np.ndarray:
    a = 2.0 * math.pi * hz * t
    return np.array([math.sin(a), math.cos(a)])


def build_obs(*, projected_gravity, angular_velocity, command, t: float, joint_commanded, last_action,
              spec: RobotSpec = DEFAULT) -> np.ndarray:
    """Concatenate the blocks in ObsLayout order. joint_commanded = commanded position minus stand pose (rad)."""
    layout = ObsLayout(spec.n_joints)
    parts = {
        "projected_gravity": np.asarray(projected_gravity, dtype=np.float32),
        "angular_velocity": np.asarray(angular_velocity, dtype=np.float32),
        "command": np.asarray(command, dtype=np.float32),
        "gait_phase": gait_phase(t).astype(np.float32),
        "joint_commanded": np.asarray(joint_commanded, dtype=np.float32),
        "last_action": np.asarray(last_action, dtype=np.float32),
    }
    obs = np.concatenate([parts[name] for name, _ in layout.blocks])
    if obs.shape != (layout.size,):
        raise ValueError(f"observation has {obs.shape[0]} values, expected {layout.size}")
    return obs


def action_to_targets(action, previous_targets, spec: RobotSpec = DEFAULT) -> np.ndarray:
    """Action in [-1, 1] -> joint targets (rad): offset from the stand pose, clipped to the joint limits and to what the
    servo can travel in one control step. The SAME clipping runs on the ESP32: the policy never sees a target it can't get."""
    a = np.clip(np.nan_to_num(np.asarray(action, dtype=np.float64), nan=0.0), -1.0, 1.0)
    stand = np.asarray(spec.stand_pose)
    target = stand + a * spec.action_scale_rad
    target = np.clip(target, stand - spec.joint_limit_rad, stand + spec.joint_limit_rad)
    max_step = spec.servo_max_speed_rad_s / spec.control_hz
    prev = np.asarray(previous_targets, dtype=np.float64)
    return prev + np.clip(target - prev, -max_step, max_step)
