"""CloudPaw V1: the robot contract and a simulator.

The agent never talks to motors. It talks to a ``RobotDriver``. Today that is ``SimulatedRobot``.
The day the quadruped is ready, a ``Ros2Robot`` (or a serial / HTTP driver) that implements the same
methods is the ONLY file that changes: the agent, the tools, the prompt and the tests stay as they are.

Coordinates: meters, x to the right and y forward of the START pose. ``heading`` is in degrees,
clockwise, 0 = the direction the robot faced at the start.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Protocol


class Mode(str, Enum):
    STANDING = "standing"
    SITTING = "sitting"
    FOLLOWING = "following"


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    heading: float


class RobotRefusal(Exception):
    """The robot (or the safety layer) says no.

    ``code`` is machine readable; ``message`` explains it in English and the agent translates it for the user.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class RobotDriver(Protocol):
    """What the agent's tools need from any robot, real or simulated."""

    def stand(self) -> None: ...
    def sit(self) -> None: ...
    def walk(self, direction: str, meters: float) -> None: ...
    def turn(self, side: str, degrees: float) -> None: ...
    def follow(self, target: str) -> None: ...
    def stop(self) -> None: ...
    def pose(self) -> Pose: ...
    def mode(self) -> Mode: ...


# Unit vector of each walking direction relative to the heading (degrees clockwise).
_WALK_OFFSET_DEG = {"forward": 0.0, "right": 90.0, "backward": 180.0, "left": 270.0}


class SimulatedRobot:
    """A robot that lives in memory. Movements are instant; the rules are the real ones."""

    def __init__(self) -> None:
        self._x = 0.0
        self._y = 0.0
        self._heading = 0.0
        self._mode = Mode.STANDING
        self.following: str | None = None
        self.trail: List[Pose] = [self.pose()]

    # --- state -----------------------------------------------------------------------------------------------
    def pose(self) -> Pose:
        return Pose(self._x, self._y, self._heading % 360.0)

    def mode(self) -> Mode:
        return self._mode

    # --- rules shared by every movement ----------------------------------------------------------------------
    def _must_be_free_to_move(self) -> None:
        if self._mode is Mode.SITTING:
            raise RobotRefusal("sitting", "The robot is sitting. Call stand first.")
        if self._mode is Mode.FOLLOWING:
            raise RobotRefusal("following", f"The robot is following {self.following}. Call stop first.")

    # --- actions ---------------------------------------------------------------------------------------------
    def stand(self) -> None:
        if self._mode is Mode.SITTING:
            self._mode = Mode.STANDING

    def sit(self) -> None:
        if self._mode is Mode.FOLLOWING:
            raise RobotRefusal("following", f"The robot is following {self.following}. Call stop first.")
        self._mode = Mode.SITTING

    def walk(self, direction: str, meters: float) -> None:
        self._must_be_free_to_move()
        if direction not in _WALK_OFFSET_DEG:
            raise RobotRefusal("bad_direction", f"Unknown direction {direction!r}.")
        angle = math.radians(self._heading + _WALK_OFFSET_DEG[direction])
        self._x += math.sin(angle) * meters
        self._y += math.cos(angle) * meters
        self.trail.append(self.pose())

    def turn(self, side: str, degrees: float) -> None:
        self._must_be_free_to_move()
        if side not in ("left", "right"):
            raise RobotRefusal("bad_direction", f"Unknown side {side!r}.")
        self._heading += degrees if side == "right" else -degrees
        self.trail.append(self.pose())

    def follow(self, target: str) -> None:
        if self._mode is Mode.SITTING:
            raise RobotRefusal("sitting", "The robot is sitting. Call stand first.")
        self._mode = Mode.FOLLOWING
        self.following = target

    def stop(self) -> None:
        """Always allowed, in any state."""
        if self._mode is Mode.FOLLOWING:
            self._mode = Mode.STANDING
        self.following = None


# --- a tiny map for the classroom -------------------------------------------------------------------------------
_ARROWS = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]


def heading_arrow(heading: float) -> str:
    return _ARROWS[int(((heading % 360.0) + 22.5) // 45) % 8]


def render_map(trail: List[Pose], width: int = 31, height: int = 13) -> str:
    """ASCII top view: S = start, · = path, arrow = where the robot is and faces. North (up) = start heading."""
    xs = [p.x for p in trail]
    ys = [p.y for p in trail]
    min_x, max_x = min(xs + [0.0]), max(xs + [0.0])
    min_y, max_y = min(ys + [0.0]), max(ys + [0.0])
    # a character is about twice as tall as wide: one row covers twice the meters of one column
    cell_x = max(0.25, (max_x - min_x) / (width - 3), (max_y - min_y) / (2 * (height - 3)))
    cell_y = 2 * cell_x

    grid = [[" "] * width for _ in range(height)]

    def put(x: float, y: float, ch: str, only_if_empty: bool = False) -> None:
        col = int(round((x - min_x) / cell_x)) + 1
        row = height - 2 - int(round((y - min_y) / cell_y))
        if 0 <= row < height and 0 <= col < width and (not only_if_empty or grid[row][col] == " "):
            grid[row][col] = ch

    for a, b in zip(trail, trail[1:]):
        steps = max(1, int(max(abs(b.x - a.x) / cell_x, abs(b.y - a.y) / cell_y) * 2))
        for i in range(steps + 1):
            t = i / steps
            put(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, "·", only_if_empty=True)
    put(0.0, 0.0, "S")
    last = trail[-1]
    put(last.x, last.y, heading_arrow(last.heading))

    border = "+" + "-" * width + "+"
    body = ["|" + "".join(r) + "|" for r in grid]
    return "\n".join([border, *body, border, f"1 column = {cell_x:.2f} m   S = start   N = start heading"])
