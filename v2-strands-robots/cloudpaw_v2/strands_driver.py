"""StrandsRobotsDriver: the CloudPaw V1 RobotDriver on top of a strands-robots Robot (MuJoCo simulation or hardware).

The V1 agent, tools, limits and stop reflex do not change: they talk to a RobotDriver, and this is one more driver.

    microduck   walk/turn run its walking policy in CLOSED LOOP on the measured pose (stop_when), so "walk 0.3 m"
                means 0.3 m measured, not velocity x time (the policy reaches ~40% of the commanded speed).
    unitree_go2 (quadruped) stand/sit ramp the joints to a pose; walk/turn need a gait policy (CloudPaw's PPO policy):
                pass gait=... When there is none, walk/turn are refused with reason 'no_gait_policy'.

stop() ends follow mode and holds the current pose; it never latches. emergency_stop() is the library's e-stop: it latches
and only a named operator can release it (resume(approved_by=...)), on purpose not reachable from the agent's tools.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Optional

from . import _v1  # noqa: F401  (puts the V1 package on sys.path)
from cloudpaw.robot import Mode, Pose, RobotRefusal  # V1 types

from .frames import StartFrame, wrap180, yaw_deg

# Joint poses of the Unitree Go2 (hip, thigh, calf per leg; FL, FR, RL, RR), radians, inside the model's limits.
GO2_STAND = [0.0, 0.9, -1.8] * 4  # the model's "home" keyframe
GO2_SIT = [0.0, 1.25, -2.6] * 4  # body lowered (calf limit is -2.72)

# A gait policy factory: (vx m/s, vy m/s, wz rad/s) -> something Robot.run accepts (a Policy or obs -> action callable).
GaitFactory = Callable[[float, float, float], Any]

MICRODUCK_FALL_Z = 0.07  # below this height the microduck has fallen (from the library's preset)


def microduck_gait(vx: float, vy: float, wz: float) -> Any:
    from strands_robots import Policy

    return Policy(f"microduck?vx={vx:g}&vy={vy:g}&wz={wz:g}")


class StrandsRobotsDriver:
    """V1 RobotDriver over a strands-robots Robot. ``robot`` can be injected (tests use a fake)."""

    # (vx, vy) per V1 walking direction, as a fraction of the walking speed; ROS convention: +y is LEFT.
    _DIRECTIONS = {"forward": (1.0, 0.0), "backward": (-1.0, 0.0), "left": (0.0, 1.0), "right": (0.0, -1.0)}

    def __init__(
        self,
        name: str = "microduck",
        *,
        robot: Any = None,
        gait: Optional[GaitFactory] = None,
        walk_speed: float = 0.3,
        turn_speed: float = 1.0,
        min_speed_mps: float = 0.05,
        min_turn_dps: float = 15.0,
        fall_z: Optional[float] = None,
    ):
        if robot is None:
            from strands_robots import Robot

            robot = Robot(name)
        self.name = name
        self.robot = robot
        self.gait = gait if gait is not None else (microduck_gait if name == "microduck" else None)
        self.walk_speed, self.turn_speed = walk_speed, turn_speed
        self.min_speed_mps, self.min_turn_dps = min_speed_mps, min_turn_dps  # for the time budget of each move
        self.fall_z = fall_z if fall_z is not None else (MICRODUCK_FALL_Z if name == "microduck" else 0.12)
        self._mode = Mode.STANDING
        self.following: Optional[str] = None
        p = self.robot.pose
        self.frame = StartFrame.from_pose(p.position, p.orientation)
        if name == "unitree_go2":
            self._make_go2_position_controlled()
        self.trail = [self.pose()]

    # --- state ---------------------------------------------------------------------------------------------------
    def pose(self) -> Pose:
        p = self.robot.pose
        x, y, heading = self.frame.to_v1(p.position, p.orientation)
        return Pose(x, y, heading)

    def mode(self) -> Mode:
        return self._mode

    def _height(self) -> float:
        return float(self.robot.pose.position[2])

    # --- rules shared with the V1 simulator --------------------------------------------------------------------------
    def _must_be_free_to_move(self) -> None:
        if self._mode is Mode.SITTING:
            raise RobotRefusal("sitting", "The robot is sitting. Call stand first.")
        if self._mode is Mode.FOLLOWING:
            raise RobotRefusal("following", f"The robot is following {self.following}. Call stop first.")
        if self.gait is None:
            raise RobotRefusal("no_gait_policy", f"{self.name} has no gait policy yet, so it can stand and sit but cannot walk or turn: load the CloudPaw PPO gait policy.")
        if self._height() < self.fall_z:
            raise RobotRefusal("fallen", "The robot has fallen. It must be reset before moving.")

    def _run(self, policy: Any, seconds: float, done: Callable[[Any], bool]) -> Any:
        """Run until done(obs) or the time budget is over; a fall always ends the move."""
        fell = {"v": False}

        def stop_when(obs: Any) -> bool:
            if float(obs.pose.position[2]) < self.fall_z:
                fell["v"] = True
                return True
            return done(obs)

        result = self.robot.run(policy, seconds=seconds, stop_when=stop_when)
        if fell["v"]:
            self.robot.hold()
            raise RobotRefusal("fallen", "The robot fell during the move and was stopped.")
        return result

    # --- actions -----------------------------------------------------------------------------------------------------
    def walk(self, direction: str, meters: float) -> None:
        if direction not in self._DIRECTIONS:
            raise RobotRefusal("bad_direction", f"Unknown direction {direction!r}.")
        self._must_be_free_to_move()
        fx, fy = self._DIRECTIONS[direction]
        start = self.robot.pose.position[:2].copy()

        def reached(obs: Any) -> bool:
            return math.dist(obs.pose.position[:2], start) >= meters

        budget = meters / self.min_speed_mps + 1.0
        result = self._run(self.gait(fx * self.walk_speed, fy * self.walk_speed, 0.0), budget, reached)
        self.robot.hold()
        self.trail.append(self.pose())
        if getattr(result, "stopped_by", "") != "stop_when":
            moved = math.dist(self.robot.pose.position[:2], start)
            raise RobotRefusal("did_not_reach", f"Walked {moved:.2f} of {meters:g} m before the time limit.")

    def turn(self, side: str, degrees: float) -> None:
        if side not in ("left", "right"):
            raise RobotRefusal("bad_direction", f"Unknown side {side!r}.")
        self._must_be_free_to_move()
        sign = 1.0 if side == "left" else -1.0  # +wz = counter-clockwise = left
        track = {"last": yaw_deg(self.robot.pose.orientation), "acc": 0.0}

        def reached(obs: Any) -> bool:  # accumulate step by step: a 180-degree turn does not wrap around
            now = yaw_deg(obs.pose.orientation)
            track["acc"] += wrap180(now - track["last"])
            track["last"] = now
            return abs(track["acc"]) >= degrees

        budget = degrees / self.min_turn_dps + 1.0
        result = self._run(self.gait(0.0, 0.0, sign * self.turn_speed), budget, reached)
        self.robot.hold()
        self.trail.append(self.pose())
        if getattr(result, "stopped_by", "") != "stop_when":
            raise RobotRefusal("did_not_reach", f"Turned {abs(track['acc']):.0f} of {degrees:g} degrees before the time limit.")

    def follow(self, target: str) -> None:
        if self._mode is Mode.SITTING:
            raise RobotRefusal("sitting", "The robot is sitting. Call stand first.")
        self._mode = Mode.FOLLOWING  # no perception yet: following is a mode, as in the V1 simulator
        self.following = target

    def stop(self) -> None:
        """Always allowed: ends follow mode and holds the pose. Does not latch."""
        self.robot.hold()
        if self._mode is Mode.FOLLOWING:
            self._mode = Mode.STANDING
        self.following = None

    def stand(self) -> None:
        if self._mode is Mode.FOLLOWING:
            return
        if self.name == "unitree_go2":
            self._go2_pose(GO2_STAND)
        self._mode = Mode.STANDING

    def sit(self) -> None:
        if self._mode is Mode.FOLLOWING:
            raise RobotRefusal("following", f"The robot is following {self.following}. Call stop first.")
        if self.name == "unitree_go2":
            self._go2_pose(GO2_SIT)
        self._mode = Mode.SITTING  # the microduck has no verified sit skill yet: a mode, it keeps standing

    def emergency_stop(self, by: str) -> None:
        """The library's latched e-stop (operator only, not an agent tool). Release with robot.resume(approved_by=...)."""
        self.robot.estop(by=by)

    # --- Unitree Go2 specifics ---------------------------------------------------------------------------------------
    def _make_go2_position_controlled(self, kp: float = 40.0, kd: float = 1.0) -> None:
        """The MuJoCo Menagerie Go2 has torque actuators. strands-robots 0.6.0 set_gains writes kp/kd but leaves the bias
        type NONE, so position targets act as constant torques and the robot collapses; AFFINE makes it a PD (sim only)."""
        self.robot.set_gains(kp=[kp] * 12, kd=[kd] * 12)
        backend = getattr(getattr(self.robot, "sim", None), "backend", None)
        if backend is not None and getattr(backend, "model", None) is not None:
            import mujoco

            backend.model.actuator_biastype[:] = mujoco.mjtBias.mjBIAS_AFFINE
        self._go2_pose(GO2_STAND)

    def _go2_pose(self, joints: list, seconds: float = 1.5) -> None:
        target = dict(zip(self.robot.action_keys, joints))
        self.robot.run(lambda obs: target, seconds=seconds)
