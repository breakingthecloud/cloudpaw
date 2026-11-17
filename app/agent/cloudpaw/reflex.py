"""The reflex: a stop word at the start of a message stops the robot BEFORE any model reads it.

Why: a model decides what to do from what it believes, and a belief can be stale ("I am already stopped"). Stopping must not
depend on that. Like a spinal reflex, it acts first and does not wait for the brain. Stopping too often is the safe failure.
"""

import re

STOP_WORDS = ("stop", "alto", "para", "parar", "pare", "detente", "detén", "deten", "freeze", "halt", "basta", "emergency", "emergencia")
_STARTS_WITH_STOP = re.compile(r"^[\W_]*(?:" + "|".join(STOP_WORDS) + r")\b", re.IGNORECASE)


def starts_with_stop(text: object) -> bool:
    return isinstance(text, str) and bool(_STARTS_WITH_STOP.match(text))
