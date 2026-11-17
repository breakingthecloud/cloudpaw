"""PPO reward for CloudPaw locomotion. Pure numpy, simulator-agnostic, every term returned separately (for logging/tuning).

The shape follows the common legged-locomotion recipe (track a velocity command with an exponential kernel; penalize
what makes a real robot shake, slip or break). Weights are a STARTING POINT, to be tuned on CloudPaw.
Per-step reward = sum(weight * term) * dt, so totals do not depend on the control rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import numpy as np


@dataclass(frozen=True)
class RewardWeights:
    track_vx: float = 1.5  # follow the forward-speed command
    track_wz: float = 0.8  # follow the yaw-rate command
    lin_vel_z: float = -2.0  # no bouncing
    ang_vel_xy: float = -0.05  # no rocking (roll/pitch rates)
    orientation: float = -1.0  # keep the body level (gravity xy in body frame)
    base_height: float = -20.0  # stay near the stand height
    action_rate: float = -0.02  # smooth commands: hobby servos and gears hate jitter
    servo_speed: float = -0.01  # do not ask more than the servo can do
    joint_limits: float = -1.0  # stay away from the mechanical limits
    alive: float = 0.5  # small bonus for not falling
    tracking_sigma: float = 0.25  # width of the exp kernel for velocity tracking


@dataclass(frozen=True)
class Termination:
    max_tilt_rad: float = 0.8  # body tilted more than ~45 degrees: fallen
    min_height_frac: float = 0.5  # body below half its stand height: fallen (relative, so it fits any robot size)


@dataclass
class StepState:
    """Everything the reward needs for one control step (all in the BODY frame)."""

    lin_vel: np.ndarray  # (3,) m/s
    ang_vel: np.ndarray  # (3,) rad/s
    projected_gravity: np.ndarray  # (3,) unit vector; (0, 0, -1) when level
    base_height: float  # m
    command: np.ndarray  # (2,) vx m/s, wz rad/s
    action: np.ndarray  # (n,) in [-1, 1]
    last_action: np.ndarray  # (n,)
    joint_offset: np.ndarray  # (n,) commanded position minus stand pose, rad
    extra: Dict[str, float] = field(default_factory=dict)


def reward_terms(s: StepState, w: RewardWeights, *, stand_height: float, joint_limit: float, action_scale: float,
                 servo_max_speed: float, dt: float) -> Dict[str, float]:
    """Each weighted term (already multiplied by its weight and dt)."""
    err_vx = (s.command[0] - s.lin_vel[0]) ** 2
    err_wz = (s.command[1] - s.ang_vel[2]) ** 2
    sig = w.tracking_sigma
    commanded_speed = np.abs(s.action - s.last_action) * action_scale / dt  # rad/s asked of each servo
    over_speed = np.clip(commanded_speed - servo_max_speed, 0.0, None)
    near_limit = np.clip(np.abs(s.joint_offset) - 0.9 * joint_limit, 0.0, None)
    raw = {
        "track_vx": float(np.exp(-err_vx / sig)),
        "track_wz": float(np.exp(-err_wz / sig)),
        "lin_vel_z": float(s.lin_vel[2] ** 2),
        "ang_vel_xy": float(np.sum(s.ang_vel[:2] ** 2)),
        "orientation": float(np.sum(s.projected_gravity[:2] ** 2)),
        "base_height": float((s.base_height - stand_height) ** 2),
        "action_rate": float(np.sum((s.action - s.last_action) ** 2)),
        "servo_speed": float(np.sum(over_speed ** 2)),
        "joint_limits": float(np.sum(near_limit)),
        "alive": 1.0,
    }
    return {k: getattr(w, k) * v * dt for k, v in raw.items()}


def reward(s: StepState, w: RewardWeights = RewardWeights(), **kw) -> float:
    return float(sum(reward_terms(s, w, **kw).values()))


def is_fallen(projected_gravity: np.ndarray, base_height: float, stand_height: float, t: Termination = Termination()) -> bool:
    """Tilt = angle between the body's z axis and gravity. Fallen if too tilted or too low."""
    g = np.asarray(projected_gravity, dtype=float)
    cos_tilt = float(np.clip(-g[2] / max(np.linalg.norm(g), 1e-9), -1.0, 1.0))
    return bool(np.arccos(cos_tilt) > t.max_tilt_rad or base_height < t.min_height_frac * stand_height)
