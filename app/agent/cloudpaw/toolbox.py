"""The ONLY things the agent can do to the robot: a small set of bounded tools.

Principle (the same one used in production agents): the model PROPOSES, the code DISPOSES.
Limits are enforced here, in code, not in the prompt. A prompt can be ignored or tricked; this cannot.
Every tool returns a structured result, never raises, so the agent can explain a refusal to the user.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Literal

from strands import tool

from .reflex import starts_with_stop
from .robot import RobotDriver, RobotRefusal


@dataclass(frozen=True)
class Limits:
    min_walk_m: float = 0.1
    max_walk_m: float = 2.0
    min_turn_deg: float = 1.0
    max_turn_deg: float = 180.0
    # How many actions one user message may trigger. Stops runaway loops and "walk 100 m" split into 50 calls.
    max_actions_per_request: int = 6
    # Total walking allowed for ONE user message, however it is split. A weak model that chops "walk 10 m" into five
    # 2 m calls to get around max_walk_m is still stopped here.
    max_distance_per_request_m: float = 6.0


class ToolBox:
    """Holds the robot, the limits and the per-request action budget. Tools are thin wrappers over its methods."""

    def __init__(self, robot: RobotDriver, limits: Limits | None = None):
        self.robot = robot
        self.limits = limits or Limits()
        self.actions_used = 0
        self.distance_used = 0.0

    # --- bookkeeping -----------------------------------------------------------------------------------------
    def begin_request(self) -> None:
        """Call once per user message."""
        self.actions_used = 0
        self.distance_used = 0.0

    def _state(self) -> Dict[str, Any]:
        p = self.robot.pose()
        return {"x_m": round(p.x, 2), "y_m": round(p.y, 2), "heading_deg": round(p.heading), "mode": self.robot.mode().value}

    def _ok(self, action: str, message: str) -> Dict[str, Any]:
        return {"ok": True, "action": action, "message": message, **self._state()}

    def _refused(self, action: str, e: RobotRefusal) -> Dict[str, Any]:
        return {"ok": False, "action": action, "reason": e.code, "message": e.message, **self._state()}

    def _spend(self) -> None:
        if self.actions_used >= self.limits.max_actions_per_request:
            raise RobotRefusal(
                "too_many_actions",
                f"Action limit reached for one request ({self.limits.max_actions_per_request}). "
                "Ask the user to confirm before continuing.",
            )
        self.actions_used += 1

    @staticmethod
    def _number(name: str, value: Any, low: float, high: float, unit: str) -> float:
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise RobotRefusal("not_a_number", f"{name} must be a number, got {value!r}.")
        if not math.isfinite(v):
            raise RobotRefusal("not_a_number", f"{name} must be a finite number.")
        if v < low or v > high:
            raise RobotRefusal("out_of_range", f"{name} must be between {low:g} and {high:g} {unit}; got {v:g}.")
        return v

    # --- actions ---------------------------------------------------------------------------------------------
    def walk(self, direction: str, meters: float) -> Dict[str, Any]:
        try:
            self._spend()
            m = self._number("meters", meters, self.limits.min_walk_m, self.limits.max_walk_m, "m")
            if self.distance_used + m > self.limits.max_distance_per_request_m:
                raise RobotRefusal(
                    "distance_budget",
                    f"Distance limit for one request reached ({self.limits.max_distance_per_request_m:g} m, "
                    f"{self.distance_used:g} m already walked). Ask the user to confirm before continuing.",
                )
            self.robot.walk(direction, m)
            self.distance_used += m
            return self._ok("walk", f"Walked {direction} {m:g} m.")
        except RobotRefusal as e:
            return self._refused("walk", e)

    def turn(self, side: str, degrees: float) -> Dict[str, Any]:
        try:
            self._spend()
            d = self._number("degrees", degrees, self.limits.min_turn_deg, self.limits.max_turn_deg, "degrees")
            self.robot.turn(side, d)
            return self._ok("turn", f"Turned {side} {d:g} degrees.")
        except RobotRefusal as e:
            return self._refused("turn", e)

    def follow(self, target: str) -> Dict[str, Any]:
        try:
            self._spend()
            t = (target or "").strip()[:40] or "the user"
            self.robot.follow(t)
            return self._ok("follow", f"Following {t}. Call stop to end.")
        except RobotRefusal as e:
            return self._refused("follow", e)

    def stop(self) -> Dict[str, Any]:
        """Never refused and never counted against the budget: stopping must always work."""
        self.robot.stop()
        return self._ok("stop", "Stopped.")

    def stand(self) -> Dict[str, Any]:
        try:
            self._spend()
            self.robot.stand()
            return self._ok("stand", "Standing.")
        except RobotRefusal as e:
            return self._refused("stand", e)

    def sit(self) -> Dict[str, Any]:
        try:
            self._spend()
            self.robot.sit()
            return self._ok("sit", "Sitting.")
        except RobotRefusal as e:
            return self._refused("sit", e)

    def reflex(self, text: object) -> bool:
        """Call with every user message BEFORE the model sees it. A stop word at the start stops the robot right now."""
        if starts_with_stop(text):
            self.robot.stop()
            return True
        return False

    def status(self) -> Dict[str, Any]:
        """Read only: free of budget."""
        return self._ok("get_status", "Current state.")


def make_tools(box: ToolBox) -> List[Any]:
    """The tool list handed to the Strands Agent. The docstrings are what the model reads: keep them precise."""

    @tool
    def walk(direction: Literal["forward", "backward", "left", "right"], meters: float = 1.0) -> dict:
        """Walk in a straight line, relative to where the robot faces (caminar / avanzar / retroceder / desplazarse).

        'left' and 'right' are side steps: the robot keeps facing the same way. To change where it faces, use turn.

        Args:
            direction: forward (adelante), backward (atrás), left (izquierda, side step) or right (derecha, side step).
            meters: distance in meters, between 0.1 and 2.0. A single step is about 0.3, 'a little' about 0.5.
        """
        return box.walk(direction, meters)

    @tool
    def turn(side: Literal["left", "right"], degrees: float = 90.0) -> dict:
        """Rotate in place (girar / voltear / dar la vuelta). To turn around use 180 degrees.

        Args:
            side: left (izquierda) or right (derecha).
            degrees: angle between 1 and 180. A quarter turn is 90.
        """
        return box.turn(side, degrees)

    @tool
    def follow(target: str = "the user") -> dict:
        """Start following a person or target (seguir / sígueme / follow me). It keeps going until stop is called.

        Args:
            target: who to follow, as the user said it (e.g. 'me', 'Ana'). Defaults to the user.
        """
        return box.follow(target)

    @tool
    def stop() -> dict:
        """STOP everything right now (parar / alto / detente / stop / freeze). Always allowed. Use it first when in doubt."""
        return box.stop()

    @tool
    def stand() -> dict:
        """Stand up (pararse / levantarse / stand up). Needed before walking if the robot is sitting."""
        return box.stand()

    @tool
    def sit() -> dict:
        """Sit down (sentarse / siéntate / sit)."""
        return box.sit()

    @tool
    def get_status() -> dict:
        """Report the robot's position (meters from the start), heading (degrees) and mode (¿dónde estás? / status)."""
        return box.status()

    return [walk, turn, follow, stop, stand, sit, get_status]
