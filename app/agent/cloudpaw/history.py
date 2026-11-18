"""Movement history across messages and runs, for the cumulative map.

Each `play.py` run starts a new simulated robot at (0, 0). The history chains every run onto the pose where the
previous one ended, so the cumulative map shows the whole walk. It is only a drawing: the robot's state, the
limits and what the model sees do not change.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import List

from cloudpaw.robot import Pose

MAX_SEGMENTS = 200


def default_path() -> Path:
    return Path(os.environ.get("CLOUDPAW_HISTORY", Path.home() / ".cloudpaw" / "history.json"))


def to_world(base: Pose, local: Pose) -> Pose:
    """Place a pose measured from this run's start into the world, given where this run started (base).

    Heading is clockwise from north (the same convention as SimulatedRobot): forward = +y, right = +x.
    """
    h = math.radians(base.heading)
    x = base.x + local.x * math.cos(h) + local.y * math.sin(h)
    y = base.y - local.x * math.sin(h) + local.y * math.cos(h)
    return Pose(x, y, (base.heading + local.heading) % 360.0)


class History:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.segments: List[List[Pose]] = []
        if path is not None and path.exists():
            try:
                raw = json.loads(path.read_text())
                self.segments = [[Pose(*p) for p in seg] for seg in raw.get("segments", []) if seg]
            except (ValueError, TypeError):
                self.segments = []  # a broken file is not worth stopping the demo for; start over
        self.base = self.end()

    def end(self) -> Pose:
        return self.segments[-1][-1] if self.segments else Pose(0.0, 0.0, 0.0)

    def add(self, local_trail: List[Pose]) -> bool:
        """Record one message's movement (poses from this run's start). Returns False if nothing moved."""
        if len(local_trail) < 2:
            return False
        self.segments.append([to_world(self.base, p) for p in local_trail])
        self.segments = self.segments[-MAX_SEGMENTS:]
        self.save()
        return True

    def reset(self) -> None:
        self.segments = []
        self.base = self.end()
        self.save()

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"segments": [[[round(p.x, 4), round(p.y, 4), round(p.heading, 2)] for p in seg] for seg in self.segments]}
        self.path.write_text(json.dumps(data))
