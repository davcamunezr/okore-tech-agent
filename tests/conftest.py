import pytest

from okore_agent import trace


@pytest.fixture(autouse=True)
def trace_file(tmp_path, monkeypatch):
    """Every test writes its trace to its own file, never to logs/."""
    path = tmp_path / "agent_runs.jsonl"
    monkeypatch.setattr(trace, "TRACE_PATH", path)
    return path
