"""Integration tests: the real MuJoCo simulation through strands-robots (headless). Slower; first run downloads models.

Run:  cd v2-strands-robots && uv run --with pytest pytest -q -m integration
"""

import warnings

import pytest

from cloudpaw_v2.strands_driver import StrandsRobotsDriver
from cloudpaw.robot import RobotRefusal
from cloudpaw.toolbox import ToolBox

warnings.filterwarnings("ignore")
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def duck_box():
    return ToolBox(StrandsRobotsDriver("microduck"))


def test_microduck_walks_the_measured_distance(duck_box):
    duck_box.begin_request()
    r = duck_box.walk("forward", 0.3)
    assert r["ok"], r
    assert r["y_m"] == pytest.approx(0.3, abs=0.06) and abs(r["x_m"]) < 0.1


def test_microduck_turns_right_90_in_the_v1_heading(duck_box):
    duck_box.begin_request()
    r = duck_box.turn("right", 90)
    assert r["ok"], r
    assert r["heading_deg"] == pytest.approx(90, abs=8)


def test_microduck_walks_backward_and_side_steps(duck_box):
    duck_box.begin_request()
    before = duck_box.status()
    back = duck_box.walk("backward", 0.15)
    side = duck_box.walk("left", 0.15)
    assert back["ok"], back
    assert side["ok"], side
    assert (back["x_m"], back["y_m"]) != (before["x_m"], before["y_m"])


def test_limits_and_stop_on_the_real_simulation(duck_box):
    duck_box.begin_request()
    assert duck_box.walk("forward", 9)["reason"] == "out_of_range"
    assert duck_box.reflex("alto") is True
    assert duck_box.stop()["ok"]


def test_go2_stands_sits_and_refuses_to_walk_without_its_ppo_policy():
    d = StrandsRobotsDriver("unitree_go2")
    standing = d._height()
    d.sit()
    sitting = d._height()
    d.stand()
    standing_again = d._height()
    assert standing > 0.2 and standing_again > 0.2, (standing, standing_again)
    assert sitting < standing - 0.04, (sitting, standing)
    with pytest.raises(RobotRefusal) as e:
        d.walk("forward", 0.5)
    assert e.value.code == "no_gait_policy"
