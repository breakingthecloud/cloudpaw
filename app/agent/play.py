"""Talk to CloudPaw in your terminal. The robot is simulated; the agent, tools and limits are the real ones.

    uv run python play.py                      # chat (needs AWS credentials with Bedrock access)
    uv run python play.py -c "avanza 2 metros y gira a la derecha" -c "stop"   # run commands and exit
    uv run python play.py --offline            # Plan B: no model, no internet (regex planner, same limits)

Type  /map  to redraw the map,  /exit  to leave.
"""

from __future__ import annotations

import argparse
import json
import sys

from cloudpaw.agent import build_agent
from cloudpaw.aws_errors import explain_aws_error
from cloudpaw.offline import run_offline
from cloudpaw.robot import SimulatedRobot, render_map
from cloudpaw.toolbox import ToolBox

DIM, GREEN, RED, CYAN, RESET = "\033[2m", "\033[32m", "\033[31m", "\033[36m", "\033[0m"


def show_state(robot: SimulatedRobot, with_map: bool) -> None:
    p = robot.pose()
    print(f"{DIM}[x={p.x:.2f} m  y={p.y:.2f} m  heading={p.heading:.0f}°  mode={robot.mode().value}]{RESET}")
    if with_map:
        print(render_map(robot.trail))


def _maybe_json(text: str):
    try:
        return json.loads(text.replace("'", '"').replace("True", "true").replace("False", "false"))
    except Exception:
        return None


def make_hooks():
    """Print every tool call the model decides to make, and what the code answered."""
    from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider

    class Printer(HookProvider):
        def register_hooks(self, registry, **kwargs):
            registry.add_callback(BeforeToolCallEvent, self.before)
            registry.add_callback(AfterToolCallEvent, self.after)

        def before(self, event):
            args = ", ".join(f"{k}={v!r}" for k, v in (event.tool_use.get("input") or {}).items())
            print(f"  {CYAN}→ {event.tool_use['name']}({args}){RESET}")

        def after(self, event):
            result = event.result.get("content", [{}])[0]
            data = result.get("json") or _maybe_json(result.get("text", ""))
            if isinstance(data, dict) and data.get("ok") is False:
                print(f"  {RED}✗ refused ({data.get('reason')}): {data.get('message')}{RESET}")
            elif isinstance(data, dict):
                print(f"  {GREEN}✓ {data.get('message')}{RESET}")

    return [Printer()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--command", action="append", help="send this message and exit (can be repeated)")
    ap.add_argument("--offline", action="store_true", help="Plan B: no model, rule-based planner")
    ap.add_argument("--no-map", action="store_true", help="do not draw the map after each message")
    args = ap.parse_args()

    robot = SimulatedRobot()
    if args.offline:
        box = ToolBox(robot)
        agent = None
    else:
        from model.load import load_model

        agent, box = build_agent(load_model(), robot=robot, hooks=make_hooks())

    def handle(text: str) -> None:
        if args.offline:
            for r in run_offline(text, box):
                color = GREEN if r["ok"] else RED
                print(f"  {color}{'✓' if r['ok'] else '✗'} {r['message']}{RESET}")
        else:
            box.begin_request()
            if box.reflex(text):
                print(f"  {RED}⚡ reflex: stop executed BEFORE the model read the message{RESET}")
            try:
                reply = agent(text)
            except Exception as e:  # noqa: BLE001 - we only translate AWS session/access problems; anything else is a bug
                hint = explain_aws_error(e)
                if hint is None:
                    raise
                print(f"{RED}✗ {hint}{RESET}", file=sys.stderr)
                raise SystemExit(2)
            print(f"{GREEN}🐾 {str(reply).strip()}{RESET}")
        show_state(robot, not args.no_map)

    if args.command:
        for text in args.command:
            print(f"\n> {text}")
            handle(text)
        return 0

    print("CloudPaw (simulated). Write in Spanish or English.  /map  /exit")
    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not text:
            continue
        if text in ("/exit", "/salir", "/quit"):
            return 0
        if text == "/map":
            show_state(robot, True)
            continue
        handle(text)


if __name__ == "__main__":
    sys.exit(main())
