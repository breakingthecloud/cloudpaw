"""Tests that need no AWS and no model: the robot rules, the safety limits, the tool schemas and the offline planner.

Run:  cd app/agent && uv run --with pytest pytest -q
"""

import math

import pytest

from cloudpaw.offline import plan, run_offline
from cloudpaw.robot import Mode, SimulatedRobot, render_map
from cloudpaw.toolbox import Limits, ToolBox, make_tools


@pytest.fixture
def box():
    return ToolBox(SimulatedRobot())


def tools_by_name(box):
    return {t.tool_name: t for t in make_tools(box)}


# --- the robot -------------------------------------------------------------------------------------------------


def test_walk_forward_moves_along_y_and_keeps_heading(box):
    r = box.walk("forward", 1.5)
    assert r["ok"] and (r["x_m"], r["y_m"], r["heading_deg"]) == (0.0, 1.5, 0)


def test_turn_right_then_forward_moves_along_x(box):
    box.turn("right", 90)
    r = box.walk("forward", 2)
    assert (r["x_m"], r["y_m"], r["heading_deg"]) == (2.0, 0.0, 90)


def test_turn_left_wraps_the_heading(box):
    assert box.turn("left", 90)["heading_deg"] == 270


def test_sidestep_does_not_change_where_the_robot_faces(box):
    r = box.walk("left", 1)
    assert (r["x_m"], r["y_m"], r["heading_deg"]) == (-1.0, 0.0, 0)


def test_backward_after_a_half_turn_goes_back_to_the_origin_line(box):
    box.turn("right", 180)
    r = box.walk("backward", 1)
    assert (r["x_m"], r["y_m"]) == (0.0, 1.0)


# --- limits live in code ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("meters", [0, 0.05, 2.01, 100, -1, math.inf, math.nan])
def test_walk_out_of_range_is_refused_and_the_robot_does_not_move(box, meters):
    r = box.walk("forward", meters)
    assert r["ok"] is False and r["reason"] in ("out_of_range", "not_a_number")
    assert (r["x_m"], r["y_m"]) == (0.0, 0.0)


@pytest.mark.parametrize("degrees", [0, 0.5, 181, 720, -90])
def test_turn_out_of_range_is_refused(box, degrees):
    assert box.turn("right", degrees)["ok"] is False


def test_the_limits_are_the_documented_ones_and_inclusive(box):
    assert box.walk("forward", 2.0)["ok"] and box.walk("forward", 0.1)["ok"]
    assert box.turn("left", 180)["ok"] and box.turn("left", 1)["ok"]


def test_a_string_instead_of_a_number_is_refused_not_a_crash(box):
    r = box.walk("forward", "far")
    assert r["ok"] is False and r["reason"] == "not_a_number"


def test_unknown_direction_is_refused(box):
    assert box.walk("up", 1)["reason"] == "bad_direction"


def test_the_action_budget_stops_a_long_chain_and_a_new_request_resets_it(box):
    for _ in range(6):
        assert box.walk("forward", 0.1)["ok"]
    r = box.walk("forward", 0.1)
    assert r["ok"] is False and r["reason"] == "too_many_actions"
    box.begin_request()
    assert box.walk("forward", 0.1)["ok"]


def test_refused_attempts_also_spend_the_budget(box):
    for _ in range(6):
        box.walk("forward", 99)
    assert box.walk("forward", 1)["reason"] == "too_many_actions"


def test_stop_always_works_even_without_budget(box):
    for _ in range(6):
        box.walk("forward", 0.1)
    assert box.stop()["ok"] is True


def test_status_is_free(box):
    for _ in range(6):
        box.walk("forward", 0.1)
    assert box.status()["ok"] is True


def test_custom_limits_apply():
    b = ToolBox(SimulatedRobot(), Limits(max_walk_m=0.5))
    assert b.walk("forward", 0.6)["ok"] is False and b.walk("forward", 0.5)["ok"]


# --- state rules -----------------------------------------------------------------------------------------------


def test_cannot_walk_or_turn_while_sitting_and_standing_fixes_it(box):
    box.sit()
    assert box.walk("forward", 1)["reason"] == "sitting"
    assert box.turn("left", 90)["reason"] == "sitting"
    box.stand()
    assert box.walk("forward", 1)["ok"]


def test_cannot_move_while_following_until_stop(box):
    assert box.follow("me")["ok"]
    assert box.walk("forward", 1)["reason"] == "following"
    assert box.sit()["reason"] == "following"
    assert box.stop()["mode"] == Mode.STANDING.value
    assert box.walk("forward", 1)["ok"]


def test_cannot_follow_while_sitting(box):
    box.sit()
    assert box.follow("me")["reason"] == "sitting"


def test_stop_in_any_state_is_harmless(box):
    box.sit()
    assert box.stop()["ok"] and box.robot.mode() is Mode.SITTING


def test_a_refusal_carries_the_current_state(box):
    box.walk("forward", 1)
    r = box.walk("forward", 5)
    assert r["ok"] is False and r["y_m"] == 1.0 and "message" in r


# --- what the model sees ---------------------------------------------------------------------------------------


def test_the_agent_gets_exactly_these_tools(box):
    assert set(tools_by_name(box)) == {"walk", "turn", "follow", "stop", "stand", "sit", "get_status"}


def test_direction_arguments_are_enums_in_the_schema(box):
    props = tools_by_name(box)["walk"].tool_spec["inputSchema"]["json"]["properties"]
    assert props["direction"]["enum"] == ["forward", "backward", "left", "right"]
    assert tools_by_name(box)["turn"].tool_spec["inputSchema"]["json"]["properties"]["side"]["enum"] == ["left", "right"]


def test_parameters_are_described_for_the_model(box):
    props = tools_by_name(box)["walk"].tool_spec["inputSchema"]["json"]["properties"]
    assert "0.1 and 2.0" in props["meters"]["description"]


def test_tools_return_plain_json_serialisable_dicts(box):
    import json

    for name, call in {"walk": dict(direction="forward", meters=1), "turn": dict(side="left", degrees=45), "get_status": {}}.items():
        json.dumps(tools_by_name(box)[name](**call))


def test_the_tool_functions_enforce_the_same_limits(box):
    assert tools_by_name(box)["walk"](direction="forward", meters=50)["ok"] is False


# --- the map ---------------------------------------------------------------------------------------------------


def test_map_shows_start_and_the_robot_arrow():
    robot = SimulatedRobot()
    b = ToolBox(robot)
    b.walk("forward", 2)
    b.turn("right", 90)
    art = render_map(robot.trail)
    assert "S" in art and "→" in art and "·" in art


def test_map_of_a_robot_that_never_moved_does_not_crash():
    assert "↑" in render_map(SimulatedRobot().trail)


# --- plan B: the rule-based planner ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("avanza 2 metros", [("walk", {"direction": "forward", "meters": 2.0})]),
        ("camina hacia atrás 1.5 metros", [("walk", {"direction": "backward", "meters": 1.5})]),
        ("walk forward 1 meter", [("walk", {"direction": "forward", "meters": 1.0})]),
        ("camina 0,5 metros a la izquierda", [("walk", {"direction": "left", "meters": 0.5})]),
        ("gira a la derecha", [("turn", {"side": "right", "degrees": 90.0})]),
        ("gira 45 grados a la izquierda", [("turn", {"side": "left", "degrees": 45.0})]),
        ("turn left 30 degrees", [("turn", {"side": "left", "degrees": 30.0})]),
        ("da la vuelta", [("turn", {"side": "right", "degrees": 180.0})]),
        ("turn around", [("turn", {"side": "right", "degrees": 180.0})]),
        ("sígueme", [("follow", {"target": "me"})]),
        ("follow me", [("follow", {"target": "me"})]),
        ("para", [("stop", {})]),
        ("alto", [("stop", {})]),
        ("stop", [("stop", {})]),
        ("siéntate", [("sit", {})]),
        ("párate", [("stand", {})]),
        ("stand up", [("stand", {})]),
        ("¿dónde estás?", [("get_status", {})]),
        ("un paso adelante", [("walk", {"direction": "forward", "meters": 0.3})]),
        ("camina un poco", [("walk", {"direction": "forward", "meters": 0.5})]),
        ("camina dos metros", [("walk", {"direction": "forward", "meters": 2.0})]),
    ],
)
def test_planner_understands_spanish_and_english(text, expected):
    assert plan(text) == expected


def test_planner_chains_clauses_in_order():
    assert plan("avanza 2 metros y gira a la derecha, luego para") == [
        ("walk", {"direction": "forward", "meters": 2.0}),
        ("turn", {"side": "right", "degrees": 90.0}),
        ("stop", {}),
    ]
    assert [c[0] for c in plan("walk forward 1 meter and turn left then stop")] == ["walk", "turn", "stop"]


def test_planner_flags_what_it_does_not_understand():
    assert plan("baila una cumbia")[0][0] == "unknown"


def test_offline_run_uses_the_same_limits_and_stops_at_the_first_refusal(box):
    results = run_offline("avanza 10 metros y gira a la derecha", box)
    assert len(results) == 1 and results[0]["ok"] is False and results[0]["reason"] == "out_of_range"
    assert box.robot.pose().heading == 0.0  # the turn after the refusal was never executed


def test_offline_run_executes_a_valid_chain(box):
    results = run_offline("avanza 1 metro y gira a la derecha y avanza 1 metro", box)
    assert [r["ok"] for r in results] == [True, True, True]
    assert (results[-1]["x_m"], results[-1]["y_m"]) == (1.0, 1.0)


# --- the stop reflex ---------------------------------------------------------------------------------------------

from cloudpaw.reflex import starts_with_stop  # noqa: E402


@pytest.mark.parametrize("text", ["stop", "STOP!", "alto", "¡alto!", "para", "Para ya", "detente", "detén", "freeze", "  stop now", "alto, camina 2 metros", "para y gira", "emergencia"])
def test_stop_words_at_the_start_trigger_the_reflex(text):
    assert starts_with_stop(text)


@pytest.mark.parametrize("text", ["avanza para adelante", "camina 1 metro", "parada de bus", "paradigma", "stopwatch", "altoparlante", "turn left then stop", "", "   ", "hola"])
def test_other_messages_do_not(text):
    assert not starts_with_stop(text)


@pytest.mark.parametrize("not_text", [None, 5, ["stop"], {"prompt": "stop"}])
def test_non_strings_never_trigger(not_text):
    assert not starts_with_stop(not_text)


def test_reflex_stops_a_following_robot_without_spending_budget(box):
    box.follow("me")
    assert box.robot.mode() is Mode.FOLLOWING
    assert box.reflex("alto, avanza 2 metros") is True
    assert box.robot.mode() is Mode.STANDING
    assert box.actions_used == 1  # only the follow


def test_reflex_does_nothing_for_a_normal_message(box):
    box.follow("me")
    assert box.reflex("avanza") is False
    assert box.robot.mode() is Mode.FOLLOWING


# --- distance budget per request ---------------------------------------------------------------------------------


def test_walking_split_into_chunks_cannot_beat_the_distance_budget(box):
    results = [box.walk("forward", 2.0) for _ in range(5)]
    assert [r["ok"] for r in results] == [True, True, True, False, False]
    assert results[3]["reason"] == "distance_budget"
    assert box.robot.pose().y == 6.0


def test_distance_budget_resets_with_the_next_message_and_turns_do_not_count(box):
    for _ in range(3):
        box.walk("forward", 2.0)
    for _ in range(2):
        box.turn("left", 10)
    box.begin_request()
    assert box.walk("forward", 2.0)["ok"]


def test_a_refused_walk_does_not_spend_distance(box):
    box.walk("forward", 99)
    assert box.distance_used == 0.0


def test_distance_budget_is_configurable():
    b = ToolBox(SimulatedRobot(), Limits(max_distance_per_request_m=1.0))
    assert b.walk("forward", 0.8)["ok"] and b.walk("forward", 0.3)["reason"] == "distance_budget"


# --- AWS errors explained -------------------------------------------------------------------------------------------

from botocore.exceptions import ClientError, NoCredentialsError, NoRegionError, TokenRetrievalError  # noqa: E402

from cloudpaw.aws_errors import explain_aws_error  # noqa: E402


def _client_error(code):
    return ClientError({"Error": {"Code": code, "Message": "x"}}, "Converse")


def test_an_expired_sso_session_says_how_to_log_in_again():
    msg = explain_aws_error(TokenRetrievalError(provider="sso", error_msg="Token has expired and refresh failed"))
    assert "SSO" in msg and "aws sso login" in msg and "--offline" in msg


@pytest.mark.parametrize("code", ["ExpiredToken", "ExpiredTokenException", "RequestExpired"])
def test_expired_credentials(code):
    assert "caducaron" in explain_aws_error(_client_error(code))


def test_missing_credentials_and_region():
    assert "No hay credenciales" in explain_aws_error(NoCredentialsError())
    assert "AWS_REGION" in explain_aws_error(NoRegionError())


@pytest.mark.parametrize("code", ["UnrecognizedClientException", "InvalidSignatureException"])
def test_rejected_credentials(code):
    assert "rechazó" in explain_aws_error(_client_error(code))


def test_access_denied_suggests_another_model():
    msg = explain_aws_error(_client_error("AccessDeniedException"))
    assert "CLOUDPAW_MODEL_ID" in msg


def test_the_aws_error_is_found_even_when_the_sdk_wraps_it():
    try:
        try:
            raise TokenRetrievalError(provider="sso", error_msg="expired")
        except TokenRetrievalError as inner:
            raise RuntimeError("model call failed") from inner
    except RuntimeError as wrapped:
        assert "aws sso login" in explain_aws_error(wrapped)


@pytest.mark.parametrize("exc", [ValueError("bug"), KeyError("x"), _client_error("ThrottlingException"), RuntimeError("other")])
def test_anything_else_is_not_hidden(exc):
    assert explain_aws_error(exc) is None


def test_the_agent_runs_tools_one_at_a_time():
    from strands.tools.executors import SequentialToolExecutor

    from cloudpaw.agent import build_agent

    agent, _ = build_agent(model=None)
    assert isinstance(agent.tool_executor, SequentialToolExecutor)


def test_the_terminal_printer_reads_a_python_dict_repr_with_apostrophes():
    from play import _maybe_json

    text = repr({"ok": False, "reason": "no_gait_policy", "message": "the robot's policy is missing"})
    assert _maybe_json(text)["reason"] == "no_gait_policy"
    assert _maybe_json('{"ok": true}') == {"ok": True}
    assert _maybe_json("not a dict") is None and _maybe_json("[1, 2]") is None
