"""One JSON line per agent run (every ask and every confirm): enough to rebuild what happened and why."""

import json
import os
from pathlib import Path

# ponytail: append-only local file for a single process; ship to a log pipeline / OpenTelemetry for real traffic.
TRACE_PATH = Path(os.environ.get("TRACE_PATH", "logs/agent_runs.jsonl"))


def write(record: dict) -> None:
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
