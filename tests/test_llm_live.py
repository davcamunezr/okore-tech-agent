"""The four brief cases with the real LLM (LLM_PROVIDER=openai_compat). Mock APIs in-process, rules judge.

Skipped unless the model server answers. Assertions check behaviour (tools used, writes, honesty), not wording.
    uv run --env-file .env pytest tests/test_llm_live.py
"""

import os
import uuid

import httpx
import pytest

from okore_agent import graph as agent_graph
from okore_agent.judge import RulesJudge
from okore_agent.llm import default_llm
from tests.test_graph import backend, make_context  # noqa: F401  (backend is an autouse fixture)


def _server_up() -> bool:
    if os.environ.get("LLM_PROVIDER") != "openai_compat":
        return False
    try:
        return httpx.get(os.environ["LLM_BASE_URL"].rstrip("/") + "/models", timeout=3).is_success
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(not _server_up(), reason="needs LLM_PROVIDER=openai_compat and a reachable server")


@pytest.fixture(scope="module")
def llm():
    return default_llm()


def agent(llm):
    g = agent_graph.build_graph(llm, RulesJudge(), make_context=make_context)
    thread = str(uuid.uuid4())
    return (
        lambda user, text: agent_graph.ask(g, thread, user, text),
        lambda user, approve=True: agent_graph.confirm(g, thread, user, approve),
        lambda: g.get_state({"configurable": {"thread_id": thread}}).values,
    )


def called(state) -> list[str]:
    return [c["name"] for c in state()["tool_calls"]]


def test_case1_query(llm, backend):
    ask, _, state = agent(llm)
    reply = ask("luis", "¿En qué estado está el expediente EXP-10234 y qué estamos esperando?")
    assert reply.decision == "answered", reply
    assert "get_claim" in called(state) and "propose_action" not in state()["tools_enabled"]
    assert "matr" in reply.answer.lower() and backend == []  # the missing plate photo
    assert "María" not in reply.answer


def test_case2_action_waits_for_confirmation(llm, backend):
    ask, confirm, state = agent(llm)
    reply = ask("luis", "Pide al taller la foto de matrícula que falta del expediente EXP-10234.")
    assert reply.awaiting_confirmation, (reply, called(state))
    assert "T-228" in reply.answer and backend == []
    assert confirm("luis").decision == "executed" and len(backend) == 1


def test_case3_workshop_down_is_not_invented(llm, backend, monkeypatch):
    monkeypatch.setenv("FAULT_WORKSHOPS", "500")
    ask, _, state = agent(llm)
    reply = ask("luis", "¿Qué taller tiene el expediente EXP-10234 y cómo lo contacto?")
    assert any(e["code"] == "UPSTREAM_ERROR" for e in state()["errors"])
    assert "Talleres Norte" not in reply.answer and "recepcion@" not in reply.answer
    assert backend == []


def test_missing_claim_id_asks_instead_of_guessing(llm, backend):
    ask, _, state = agent(llm)
    reply = ask("luis", "¿En qué estado está mi expediente?")
    assert "get_claim" not in called(state) and backend == []
    assert "EXP" in reply.answer or "número" in reply.answer.lower()
