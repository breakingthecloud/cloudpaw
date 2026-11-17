#!/usr/bin/env python3
"""Say something to the CloudPaw agent through `agentcore invoke` and print only what matters.

    python3 workshop/tools/say.py "avanza 2 metros y gira a la derecha" --local --port 8081
    python3 workshop/tools/say.py "alto"                       # the deployed Runtime (after `agentcore deploy`)
    python3 workshop/tools/say.py --new "hola"                 # start a NEW session (a new robot at the start pose)

Why this exists: the robot lives inside a Runtime SESSION. `agentcore invoke` makes a new session every time unless you
pass --session-id, and then every message would find a robot back at the start. This keeps one session id for the whole
demo and turns the raw event stream into: the tools the model called, and its answer. Standard library only (Python 3.8+).
"""

import argparse
import json
import os
import subprocess
import sys
import uuid

# AgentCore needs a session id of at least 33 characters.
DEFAULT_SESSION = "cloudpaw-workshop-session-000000001"


def parse_stream(text):
    """Event stream (lines 'data: {...}') -> (tool_calls, reply). tool_calls = [(name, args_dict_or_raw)]."""
    # Block indexes restart at 0 in every assistant message (the answer that follows the tool results is a second
    # message), so a block is identified by (message number, index).
    blocks = {}
    order = []
    message = 0
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            event = json.loads(line[5:].strip()).get("event", {})
        except (ValueError, AttributeError):
            continue
        if "messageStart" in event:
            message += 1
        elif "contentBlockStart" in event:
            cb = event["contentBlockStart"]
            idx = (message, cb.get("contentBlockIndex", len(order)))
            tool = (cb.get("start") or {}).get("toolUse")
            blocks[idx] = {"tool": tool["name"], "input": ""} if tool else {"text": ""}
            order.append(idx)
        elif "contentBlockDelta" in event:
            cb = event["contentBlockDelta"]
            idx = (message, cb.get("contentBlockIndex", 0))
            delta = cb.get("delta", {})
            block = blocks.setdefault(idx, {"text": ""})
            if idx not in order:
                order.append(idx)
            if "toolUse" in delta and "tool" in block:
                block["input"] += delta["toolUse"].get("input", "")
            elif "text" in delta:
                block["text"] = block.get("text", "") + delta["text"]
    calls, reply = [], []
    for idx in order:
        b = blocks[idx]
        if "tool" in b:
            try:
                args = json.loads(b["input"]) if b["input"] else {}
            except ValueError:
                args = b["input"]
            calls.append((b["tool"], args))
        elif b.get("text", "").strip():
            reply.append(b["text"].strip())
    return calls, " ".join(reply)


def format_call(name, args):
    if isinstance(args, dict):
        return "%s(%s)" % (name, ", ".join("%s=%r" % (k, v) for k, v in args.items()))
    return "%s(%s)" % (name, args)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("message", help="what to tell the robot")
    ap.add_argument("--local", action="store_true", help="talk to `agentcore dev` instead of the deployed Runtime")
    ap.add_argument("--port", default="8080", help="port of `agentcore dev` (with --local)")
    ap.add_argument("--session", default=DEFAULT_SESSION, help="Runtime session id (>= 33 chars); same id = same robot")
    ap.add_argument("--new", action="store_true", help="use a brand new session")
    ap.add_argument("--raw", action="store_true", help="print the raw event stream too")
    args = ap.parse_args(argv)

    session = str(uuid.uuid4()) if args.new else args.session
    if len(session) < 33:
        sys.exit("session id must have at least 33 characters")
    cmd = os.environ.get("AGENTCORE_CMD", "agentcore").split()
    cmd += ["invoke", "--runtime", "agent", "--session-id", session, "--payload", json.dumps({"prompt": args.message})]
    if args.local:
        cmd += ["--local", "--port", str(args.port)]

    out = subprocess.run(cmd, capture_output=True, text=True)
    if args.raw:
        print(out.stdout)
    calls, reply = parse_stream(out.stdout)
    if out.returncode != 0 and not (calls or reply):
        print(out.stderr.strip() or out.stdout.strip(), file=sys.stderr)
        return out.returncode or 1
    for name, a in calls:
        print("  -> " + format_call(name, a))
    print("PAW: " + (reply or "(no text; if the message started with a stop word, the reflex already stopped the robot)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
