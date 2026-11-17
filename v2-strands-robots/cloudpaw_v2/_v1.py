"""Make the V1 package (app/agent/cloudpaw) importable from V2 without copying it: one source of truth for the tools,
limits and stop reflex. V2 has its own environment (Python 3.12 + strands-robots); V1's runtime deps are a subset."""

import sys
from pathlib import Path

V1_DIR = Path(__file__).resolve().parents[2] / "app" / "agent"
if str(V1_DIR) not in sys.path:
    sys.path.insert(0, str(V1_DIR))
