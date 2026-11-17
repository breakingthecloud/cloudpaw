"""Plan B: the same robot and the same safety limits, but WITHOUT a language model.

A handful of regular expressions turn Spanish/English commands into tool calls. It works offline and instantly, and it
is a good contrast in class: it understands exactly what it was told to look for, and nothing else. A model understands
"da unos pasos hacia adelante y mira a tu derecha"; this does not. It is NOT the product, it is the fallback.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from .toolbox import ToolBox

Call = Tuple[str, Dict[str, Any]]

_SPLIT = re.compile(r"\s*(?:(?<!\d),|,(?!\d)|;|\by luego\b|\by despu[eé]s\b|\bluego\b|\bdespu[eé]s\b|\band then\b|\bthen\b|\band\b|\by\b)\s*")
_NUMBER_WORDS = {"un": 1, "uno": 1, "una": 1, "one": 1, "dos": 2, "two": 2, "tres": 3, "three": 3, "cuatro": 4, "four": 4, "cinco": 5, "five": 5}
_NUM = r"(\d+(?:[.,]\d+)?|" + "|".join(_NUMBER_WORDS) + r")"

_STOP = re.compile(r"^(?:stop|alto|para|detente|det[eé]n|freeze|halt)\b|\bstop\b|\bdetente\b|\bfreeze\b")
_FOLLOW = re.compile(r"\b(?:s[ií]gueme|follow(?: me)?|ven conmigo|acomp[aá][ñn]ame)\b")
_SIT = re.compile(r"\b(?:si[eé]ntate|sit(?: down)?)\b")
_STAND = re.compile(r"\b(?:p[aá]rate|lev[aá]ntate|stand(?: up)?|get up)\b")
_STATUS = re.compile(r"\b(?:d[oó]nde est[aá]s|status|estado|where are you|position|posici[oó]n)\b")
_TURN = re.compile(r"\b(?:gira|girar|voltea|rota|turn|rotate|vuelta)\b")
_AROUND = re.compile(r"\b(?:da la vuelta|media vuelta|turn around|about face)\b")
_WALK = re.compile(r"\b(?:avanza|camina|anda|ve|ir|retrocede|walk|go|move|step|forward|backward|back|adelante|atr[aá]s)\b")


def _number(text: str, units: str, default: float) -> float:
    m = re.search(_NUM + r"\s*(?:" + units + r")", text)
    if not m:
        return default
    raw = m.group(1)
    return float(_NUMBER_WORDS[raw]) if raw in _NUMBER_WORDS else float(raw.replace(",", "."))


def _side(text: str, default: str = "right") -> str:
    if re.search(r"\b(?:izquierda|izq|left)\b", text):
        return "left"
    if re.search(r"\b(?:derecha|der|right)\b", text):
        return "right"
    return default


def plan(text: str) -> List[Call]:
    """Sentence -> ordered list of (tool, arguments). Unknown clauses become ('unknown', {'text': clause})."""
    calls: List[Call] = []
    for clause in (c for c in _SPLIT.split(text.lower().strip()) if c):
        if _STOP.search(clause):
            calls.append(("stop", {}))
        elif _FOLLOW.search(clause):
            calls.append(("follow", {"target": "me"}))
        elif _STATUS.search(clause):
            calls.append(("get_status", {}))
        elif _SIT.search(clause):
            calls.append(("sit", {}))
        elif _STAND.search(clause):
            calls.append(("stand", {}))
        elif _AROUND.search(clause):
            calls.append(("turn", {"side": "right", "degrees": 180.0}))
        elif _TURN.search(clause):
            calls.append(("turn", {"side": _side(clause), "degrees": _number(clause, r"grados?|°|deg(?:rees?)?", 90.0)}))
        elif _WALK.search(clause) or re.search(r"\b(?:izquierda|derecha|left|right)\b", clause):
            if re.search(r"\b(?:retrocede|atr[aá]s|back(?:ward)?)\b", clause):
                direction = "backward"
            elif re.search(r"\b(?:izquierda|left)\b", clause):
                direction = "left"
            elif re.search(r"\b(?:derecha|right)\b", clause):
                direction = "right"
            else:
                direction = "forward"
            default = 0.3 if re.search(r"\b(?:un paso|a step|one step)\b", clause) else 0.5 if re.search(r"\b(?:un poco|a little|a bit)\b", clause) else 1.0
            calls.append(("walk", {"direction": direction, "meters": _number(clause, r"metros?|m\b|meters?|metres?", default)}))
        else:
            calls.append(("unknown", {"text": clause}))
    return calls


def run_offline(text: str, box: ToolBox) -> List[Dict[str, Any]]:
    """Execute the plan through the SAME ToolBox (so the same limits apply). Stops at the first refusal."""
    box.begin_request()
    methods = {"walk": box.walk, "turn": box.turn, "follow": box.follow, "stop": box.stop, "stand": box.stand, "sit": box.sit, "get_status": box.status}
    results: List[Dict[str, Any]] = []
    for name, args in plan(text):
        if name == "unknown":
            results.append({"ok": False, "action": "unknown", "reason": "not_understood", "message": f"I did not understand: {args['text']!r}."})
            break
        result = methods[name](**args)
        results.append(result)
        if not result["ok"]:
            break
    return results
