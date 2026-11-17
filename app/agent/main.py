"""AgentCore Runtime entrypoint for CloudPaw (a text-controlled quadruped).

One robot (simulated for now) per session: AgentCore gives every session its own isolated microVM, so each session
keeps its own robot position between messages. A real robot would be reached through a driver (see cloudpaw/robot.py).
"""

from functools import lru_cache

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from cloudpaw.agent import build_agent
from model.load import load_model
from parse import parse_payload


@lru_cache(maxsize=128)
def _get_session(session_id: str):
    """(agent, toolbox) for a session. Cached so the conversation and the robot's state survive between messages."""
    return build_agent(load_model())


def create_app():
    app = BedrockAgentCoreApp()
    log = app.logger

    @app.entrypoint
    async def invoke(payload, context):
        session_id = getattr(context, "session_id", None) or "default-session"
        prompt, _actor_id = parse_payload(payload)
        agent, box = _get_session(session_id)
        box.begin_request()  # reset the per-request action budget
        if box.reflex(prompt):  # a stop word at the start stops the robot BEFORE the model reads the message
            log.info("reflex: stop executed before the model")
        log.info(f"CloudPaw session={session_id}")

        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict) or "event" not in event:
                continue
            cbs = event["event"].get("contentBlockStart")
            if cbs is not None and not cbs.get("start"):
                continue
            yield event

    return app


app = create_app()
if __name__ == "__main__":
    app.run()
