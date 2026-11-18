"""Cumulative map: chaining runs, persistence and drawing."""

import math

from cloudpaw.history import History, to_world
from cloudpaw.robot import Pose, SimulatedRobot, render_history


def close(a: Pose, b: Pose) -> bool:
    return math.isclose(a.x, b.x, abs_tol=1e-6) and math.isclose(a.y, b.y, abs_tol=1e-6) and math.isclose(a.heading % 360, b.heading % 360, abs_tol=1e-6)


def test_to_world_rotates_and_translates():
    base = Pose(1.0, 2.0, 90.0)  # facing east
    assert close(to_world(base, Pose(0, 1, 0)), Pose(2.0, 2.0, 90.0))  # forward = east
    assert close(to_world(base, Pose(1, 0, 0)), Pose(1.0, 1.0, 90.0))  # right = south
    assert close(to_world(base, Pose(0, 0, 90)), Pose(1.0, 2.0, 180.0))


def test_second_run_continues_where_the_first_ended(tmp_path):
    path = tmp_path / "h.json"
    r1 = SimulatedRobot(); h1 = History(path)
    r1.walk("forward", 2); r1.turn("right", 90)
    assert h1.add(r1.trail)
    r2 = SimulatedRobot(); h2 = History(path)  # a new process
    r2.walk("forward", 1)
    h2.add(r2.trail)
    assert len(h2.segments) == 2
    assert close(h2.end(), Pose(1.0, 2.0, 90.0))


def test_no_movement_is_not_recorded(tmp_path):
    h = History(tmp_path / "h.json")
    assert not h.add(SimulatedRobot().trail)
    assert h.segments == []


def test_reset_and_broken_file(tmp_path):
    path = tmp_path / "h.json"
    r = SimulatedRobot(); r.walk("forward", 1)
    h = History(path); h.add(r.trail); h.reset()
    assert History(path).segments == []
    path.write_text("{not json")
    assert History(path).segments == []


def test_render_history_numbers_each_message():
    r = SimulatedRobot(); h = History(None)
    r.walk("forward", 1); h.add(r.trail[0:])
    n = len(r.trail) - 1
    r.walk("right", 1); h.add(r.trail[n:])
    art = render_history(h.segments)
    body = "".join(art.splitlines()[1:-2])  # the grid only, without borders and legend
    assert "1" in body and "2" in body and "S" in body and "↑" in body  # walking sideways keeps the heading
    assert "(2 total)" in art.splitlines()[-1]
    assert "no movements yet" in render_history([])
