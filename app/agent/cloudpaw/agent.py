"""One place that builds the agent, so the AgentCore entrypoint, the local REPL and the tests share it."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from strands import Agent
from strands.tools.executors import SequentialToolExecutor

from .prompt import SYSTEM_PROMPT
from .robot import RobotDriver, SimulatedRobot
from .toolbox import Limits, ToolBox, make_tools


def build_agent(
    model: Any,
    robot: Optional[RobotDriver] = None,
    limits: Optional[Limits] = None,
    hooks: Optional[list] = None,
) -> Tuple[Agent, ToolBox]:
    """Returns the agent and its ToolBox. Call ``box.begin_request()`` before each user message."""
    robot = robot or SimulatedRobot()
    box = ToolBox(robot, limits)
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=make_tools(box),
        # One movement at a time: the model may ask for several tools in one turn ("stand up and walk"); on a real
        # robot they must not run at once. Found on the physics simulation (V2): walk ran before stand had finished.
        tool_executor=SequentialToolExecutor(),
        callback_handler=None,  # no token-by-token printing in logs; the entrypoint streams events itself
        hooks=hooks,
    )
    return agent, box
