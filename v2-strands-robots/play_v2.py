"""Talk to CloudPaw V2: the SAME V1 agent, tools, limits and stop reflex, now driving a physics simulation (MuJoCo).

    uv run python play_v2.py                                   # microduck (walks)
    uv run python play_v2.py --robot unitree_go2               # the quadruped: stands/sits; walking needs its PPO policy
    uv run python play_v2.py -c "avanza 30 centímetros y gira a la derecha" -c "alto"

Needs AWS credentials with Bedrock access (AWS_PROFILE=...), like the V1 chat.
"""

from __future__ import annotations

import argparse
import sys
import warnings

from cloudpaw_v2 import _v1  # noqa: F401  (V1 on sys.path)
from cloudpaw_v2.strands_driver import StrandsRobotsDriver

from cloudpaw.agent import build_agent
from cloudpaw.aws_errors import explain_aws_error
from model.load import load_model
from play import GREEN, RED, RESET, make_hooks, show_state  # the V1 terminal's printer

warnings.filterwarnings("ignore")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--robot", default="microduck", choices=["microduck", "unitree_go2"])
    ap.add_argument("-c", "--command", action="append", help="send this message and exit (can be repeated)")
    ap.add_argument("--no-map", action="store_true")
    args = ap.parse_args()

    driver = StrandsRobotsDriver(args.robot)
    agent, box = build_agent(load_model(), robot=driver, hooks=make_hooks())
    print(f"CloudPaw V2 · {args.robot} in MuJoCo (strands-robots). Write in Spanish or English.")

    def handle(text: str) -> None:
        box.begin_request()
        if box.reflex(text):
            print(f"  {RED}⚡ reflex: stop executed BEFORE the model read the message{RESET}")
        try:
            reply = agent(text)
        except Exception as e:  # noqa: BLE001
            hint = explain_aws_error(e)
            if hint is None:
                raise
            print(f"{RED}✗ {hint}{RESET}", file=sys.stderr)
            raise SystemExit(2)
        print(f"{GREEN}🐾 {str(reply).strip()}{RESET}")
        show_state(driver, not args.no_map)

    for text in args.command or []:
        print(f"\n> {text}")
        handle(text)
    if args.command:
        return 0
    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if text in ("/exit", "/salir", "/quit"):
            return 0
        if text:
            handle(text)


if __name__ == "__main__":
    sys.exit(main())
