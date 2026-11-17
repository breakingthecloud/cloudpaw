"""CloudPaw robot spec for RL — INFERRED for the first demo. Every number marked ASSUMED must be replaced by the real one.

Design rule: the policy must run on the ESP32 with only what the ESP32 can sense. Hobby servos have no position feedback,
so the observation uses the *commanded* joint positions, not measured ones, plus the IMU.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

LEGS = ("FL", "FR", "RL", "RR")


@dataclass(frozen=True)
class RobotSpec:
    # --- hardware (ASSUMED) -------------------------------------------------------------------------------------------
    mcu: str = "ESP32-S3 (dual core 240 MHz, 512 KB SRAM, FPU)"  # ASSUMED
    servo: str = "MG90S-class hobby servo, PWM, no position feedback"  # ASSUMED
    servo_driver: str = "PCA9685 over I2C (16 channels)"  # ASSUMED
    imu: str = "MPU-6050 / ICM-42688 over I2C (accelerometer + gyroscope)"  # ASSUMED
    joints_per_leg: Tuple[str, ...] = ("hip", "knee")  # ASSUMED: 2 DoF per leg (8 servos); 12 if a hip roll is added
    servo_max_speed_rad_s: float = 10.0  # ASSUMED: MG90S ~0.1 s / 60 degrees at 4.8 V
    joint_limit_rad: float = 1.2  # ASSUMED: usable +-range around the stand pose, mechanically safe
    stand_pose_rad: Tuple[float, float] = (0.6, -1.2)  # ASSUMED (hip, knee) of the stand pose
    stand_height_m: float = 0.12  # ASSUMED body height when standing
    mass_kg: float = 0.6  # ASSUMED

    # --- control -----------------------------------------------------------------------------------------------------
    control_hz: float = 50.0  # policy rate on the ESP32 (20 ms budget; an MLP this size takes well under 1 ms)
    action_scale_rad: float = 0.35  # action in [-1, 1] -> offset from the stand pose, in radians
    max_cmd_vx: float = 0.25  # m/s, forward/backward command range used in training
    max_cmd_wz: float = 1.0  # rad/s, yaw-rate command range

    @property
    def joints(self) -> Tuple[str, ...]:
        return tuple(f"{leg}_{j}" for leg in LEGS for j in self.joints_per_leg)

    @property
    def n_joints(self) -> int:
        return len(LEGS) * len(self.joints_per_leg)

    @property
    def stand_pose(self) -> Tuple[float, ...]:
        return tuple(self.stand_pose_rad) * len(LEGS)


@dataclass(frozen=True)
class ObsLayout:
    """What the policy sees, in this order. Everything is available on the ESP32 at 50 Hz."""

    n_joints: int
    blocks: Tuple[Tuple[str, int], ...] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "blocks", (
            ("projected_gravity", 3),  # IMU: gravity direction in the body frame (orientation without a magnetometer)
            ("angular_velocity", 3),  # IMU gyroscope, rad/s
            ("command", 2),  # (vx m/s, wz rad/s) from the agent: "walk", "turn"
            ("gait_phase", 2),  # sin, cos of a 1.5 Hz clock: gives the policy a rhythm without sensing feet
            ("joint_commanded", self.n_joints),  # last commanded positions minus stand pose (servos have no feedback)
            ("last_action", self.n_joints),
        ))

    @property
    def size(self) -> int:
        return sum(n for _, n in self.blocks)

    def slice(self, name: str) -> slice:
        start = 0
        for block, n in self.blocks:
            if block == name:
                return slice(start, start + n)
            start += n
        raise KeyError(name)


DEFAULT = RobotSpec()
