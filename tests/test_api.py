"""HTTP API over the graph (scripted LLM, rules judge, in-process mocks)."""

import pytest
from fastapi.testclient import TestClient

from okore_agent import graph as agent_graph
from okore_agent.api import create_app
from okore_agent.judge import RulesJudge
from okore_agent.llm import ScriptedLLM
from tests.test_graph import backend, make_context  # noqa: F401  (backend is an autouse fixture)


@pytest.fixture
def api():
    return TestClient(create_app(agent_graph.build_graph(ScriptedLLM(), RulesJudge(), make_context=make_context)))


def as_user(user):
    return {"X-User-Id": user}


def test_serves_the_ui_and_the_user_list(api):
    assert "OKORE" in api.get("/").text
    users = {u["user_id"]: u for u in api.get("/api/users").json()}
    assert users["ana"] == {"user_id": "ana", "role": "viewer", "claims": ["EXP-10234", "EXP-10235"]}
    assert users["luis"]["claims"] is None


@pytest.mark.parametrize("headers", [{}, as_user("mallory")])
def test_identity_is_required(api, headers):
    assert api.post("/api/chat", json={"message": "¿Estado de EXP-10234?"}, headers=headers).status_code == 401


def test_case2_over_http(api, backend):
    r = api.post("/api/chat", json={"message": "Solicita la foto de matrícula de EXP-10234"}, headers=as_user("luis"))
    body = r.json()
    assert body["awaiting_confirmation"] and "T-228" in body["answer"] and backend == []

    done = api.post("/api/chat/confirm", json={"thread_id": body["thread_id"], "approve": True}, headers=as_user("luis"))
    assert done.json()["decision"] == "executed" and len(backend) == 1


def test_a_conversation_belongs_to_its_user(api, backend):
    thread = api.post("/api/chat", json={"message": "Solicita la foto de matrícula de EXP-10234"},
                      headers=as_user("luis")).json()["thread_id"]
    steal = {"thread_id": thread, "approve": True}
    assert api.post("/api/chat/confirm", json=steal, headers=as_user("marta")).status_code == 403
    assert api.post("/api/chat", json={"message": "¿y el taller?", "thread_id": thread},
                    headers=as_user("marta")).status_code == 403
    assert backend == []


def test_empty_thread_id_is_rejected(api):
    assert api.post("/api/chat/confirm", json={"thread_id": "", "approve": True},
                    headers=as_user("luis")).status_code == 422


def test_viewer_gets_the_controlled_refusal(api, backend):
    r = api.post("/api/chat", json={"message": "Solicita la foto de matrícula de EXP-10234"}, headers=as_user("ana"))
    assert r.json()["decision"] == "forbidden" and backend == []
