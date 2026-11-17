"""Open-loop trot gait for the CloudPaw demo. Pure Python: no ROS, so it is unit tested on any machine.

Diagonal pairs move together (FL+RR, then FR+RL). Each foot traces a swing arc (lifted) and a stance line (on the ground);
inverse kinematics of the 2-link leg turns foot positions into hip/knee angles. This is a VISUAL demo of how the robot
will move, not the controller: the real gait comes from the PPO policy (v2-strands-robots/cloudpaw_rl).
Angle convention (same as the URDF): 0 = leg straight down, pitch about +y; positive hip swings the leg backward.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Tuple

LEGS = ("FL", "FR", "RL", "RR")
JOINTS = tuple(f"{leg}_{j}" for leg in LEGS for j in ("hip", "knee"))
PHASE_OFFSET = {"FL": 0.0, "RR": 0.0, "FR": 0.5, "RL": 0.5}  # trot: diagonal pairs half a cycle apart


@dataclass(frozen=True)
class LegGeometry:
    thigh: float = 0.075
    shin: float = 0.075
    hip_limit: float = 1.2
    knee_lo: float = -2.4
    knee_hi: float = 0.0


@dataclass(frozen=True)
class TrotParams:
    height: float = 0.124  # hip-to-foot distance at stance (stand pose)
    step_length: float = 0.04  # m, foot travel per half cycle (negative = walk backward)
    step_height: float = 0.025  # m, foot lift during swing
    frequency: float = 1.5  # Hz
    duty: float = 0.5  # fraction of the cycle the foot is on the ground
    turn: float = 0.0  # -1..1: shortens one side's steps to curve (no hip abduction on CloudPaw)


def leg_ik(x: float, z: float, g: LegGeometry = LegGeometry()) -> Tuple[float, float]:
    """Foot at (x forward, z down-positive) relative to the hip -> (hip, knee) radians. Raises if unreachable."""
    d2 = x * x + z * z
    cos_knee = (d2 - g.thigh ** 2 - g.shin ** 2) / (2 * g.thigh * g.shin)
    if not -1.0 <= cos_knee <= 1.0:
        raise ValueError(f"foot ({x:.3f}, {z:.3f}) out of reach")
    knee = -math.acos(cos_knee)  # knee bends backward (negative), like the URDF limits
    hip = math.atan2(-x, z) - math.atan2(g.shin * math.sin(knee), g.thigh + g.shin * math.cos(knee))
    return hip, knee


def leg_fk(hip: float, knee: float, g: LegGeometry = LegGeometry()) -> Tuple[float, float]:
    """(hip, knee) -> foot (x forward, z down-positive) relative to the hip."""
    x = -g.thigh * math.sin(hip) - g.shin * math.sin(hip + knee)
    z = g.thigh * math.cos(hip) + g.shin * math.cos(hip + knee)
    return x, z


def foot_target(phase: float, p: TrotParams, side_scale: float = 1.0) -> Tuple[float, float]:
    """Foot (x, z) for a phase in [0, 1): stance moves the foot backward on the ground, swing brings it forward lifted."""
    phase %= 1.0
    half = p.step_length * side_scale / 2
    if phase < p.duty:  # stance: front -> back, on the ground
        s = phase / p.duty
        return half - 2 * half * s, p.height
    s = (phase - p.duty) / (1 - p.duty)  # swing: back -> front, lifted (half sine)
    return -half + 2 * half * s, p.height - p.step_height * math.sin(math.pi * s)


def trot_angles(t: float, p: TrotParams = TrotParams(), g: LegGeometry = LegGeometry()) -> Dict[str, float]:
    """All 8 joint angles at time t."""
    out: Dict[str, float] = {}
    for leg in LEGS:
        side_scale = 1.0 - p.turn if leg in ("FL", "RL") else 1.0 + p.turn  # turn > 0: left steps shorter -> curve left
        x, z = foot_target(t * p.frequency + PHASE_OFFSET[leg], p, side_scale)
        out[f"{leg}_hip"], out[f"{leg}_knee"] = leg_ik(x, z, g)
    return out


def pose(hip: float, knee: float) -> Dict[str, float]:
    return {f"{leg}_{j}": (hip if j == "hip" else knee) for leg in LEGS for j in ("hip", "knee")}


STAND = pose(0.6, -1.2)
SIT = pose(1.1, -2.2)


def within_limits(angles: Dict[str, float], g: LegGeometry = LegGeometry()) -> bool:
    return all(abs(v) <= g.hip_limit if k.endswith("hip") else g.knee_lo <= v <= g.knee_hi for k, v in angles.items())
