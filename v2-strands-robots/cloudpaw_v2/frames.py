"""Frames: simulator world -> CloudPaw V1 frame. Pure math, no simulator needed (unit tested).

Simulator (MuJoCo): z up, yaw counter-clockwise from +x, quaternion (w, x, y, z).
CloudPaw V1: meters from the START pose, x to the right, y forward; heading in degrees, clockwise, 0 = start heading.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


def yaw_deg(q: Sequence[float]) -> float:
    """Yaw (degrees, counter-clockwise) of a (w, x, y, z) quaternion."""
    w, x, y, z = (float(v) for v in q)
    return math.degrees(math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))


def wrap180(deg: float) -> float:
    """An angle in (-180, 180]."""
    d = (deg + 180.0) % 360.0 - 180.0
    return 180.0 if d == -180.0 else d


@dataclass(frozen=True)
class StartFrame:
    """The start pose; every later pose is expressed relative to it."""

    x0: float
    y0: float
    yaw0: float  # degrees, counter-clockwise

    @classmethod
    def from_pose(cls, position: Sequence[float], orientation: Sequence[float]) -> "StartFrame":
        return cls(float(position[0]), float(position[1]), yaw_deg(orientation))

    def to_v1(self, position: Sequence[float], orientation: Sequence[float]) -> tuple[float, float, float]:
        """(x right, y forward, heading clockwise in [0, 360)) relative to the start pose."""
        dx, dy = float(position[0]) - self.x0, float(position[1]) - self.y0
        a = math.radians(self.yaw0)
        forward = dx * math.cos(a) + dy * math.sin(a)
        right = dx * math.sin(a) - dy * math.cos(a)
        heading = (-(yaw_deg(orientation) - self.yaw0)) % 360.0
        return right, forward, heading


def turned_deg(yaw_start: float, yaw_now: float) -> float:
    """How far the robot has turned, in degrees (positive = counter-clockwise = left)."""
    return wrap180(yaw_now - yaw_start)
