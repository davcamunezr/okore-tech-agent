from datetime import datetime, timedelta

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from okore_agent import mock_services, tools
from okore_agent.security import get_user

NOW = datetime(2026, 9, 28, 12, 0)

EVENTS = {
    "EXP-10234": [
        {"event_type": "DOCUMENT_MISSING", "event_date": datetime(2026, 9, 22, 10, 32),
         "description": "Falta la fotografía de la matrícula (PHOTO_PLATE).", "actor": "system"},
    ],
    "EXP-10237": [
        {"event_type": "DOCUMENT_REQUESTED", "event_date": datetime(2026, 9, 25, 9, 30),
         "description": "Solicitado PHOTO_PLATE al taller T-412.", "actor": "operator:marta"},
    ],
    "EXP-10242": [
        {"event_type": "DOCUMENT_REQUESTED", "event_date": datetime(2026, 9, 16, 9, 30),
         "description": "Segunda solicitud (recordatorio) de PHOTO_PLATE al taller T-517.", "actor": "operator:luis"},
    ],
}


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    monkeypatch.setattr(tools, "BACKOFF_S", 0)


def ctx(user_id="luis", http=None, events=None, now=NOW):
    return tools.ToolContext(
        user=get_user(user_id),
        http=http or TestClient(mock_services.app),
        events=events or (lambda claim_id, limit: EVENTS.get(claim_id, [])[:limit]),
        now=lambda: now,
    )


def fake_http(handler):
    calls = []

    def record(request):
        calls.append(request)
        return handler(request)

    return httpx.Client(transport=httpx.MockTransport(record), base_url="http://mocks"), calls


def must_not_call(request):
    raise AssertionError(f"unexpected HTTP call: {request.url}")


# --- Catalog and permissions ---

def test_llm_catalog_never_contains_execute():
    assert set(tools.TOOLS) == {"get_claim", "get_workshop", "get_claim_events", "propose_action"}


@pytest.mark.parametrize("bad_args", [
    {"claim_id": "EXP-1"},
    {"claim_id": "EXP-10234; DROP TABLE claim_events"},
    {"claim_id": "EXP-10234", "sql": "SELECT * FROM claim_events"},
    {},
])
def test_invalid_input_rejected_before_any_call(bad_args):
    http, calls = fake_http(must_not_call)
    result = tools.get_claim(ctx(http=http), **bad_args)
    assert result.error.code == "INVALID_INPUT" and calls == []


def test_viewer_cannot_propose():
    http, calls = fake_http(must_not_call)
    result = tools.propose_action(ctx("ana", http=http), claim_id="EXP-10234", document="PHOTO_PLATE")
    assert result.error.code == "FORBIDDEN" and calls == []


@pytest.mark.parametrize("user_id, claim_id", [("ana", "EXP-10236"), ("marta", "EXP-10234"), ("ana", "EXP-99999")])
def test_out_of_scope_claim_is_forbidden_without_calling(user_id, claim_id):
    http, calls = fake_http(must_not_call)
    for tool in (tools.get_claim, tools.get_claim_events):
        assert tool(ctx(user_id, http=http), claim_id=claim_id).error.code == "FORBIDDEN"
    assert calls == []


# --- Reads ---

def test_claim_output_has_no_customer_pii():
    result = tools.get_claim(ctx("ana"), claim_id="EXP-10234")
    assert result.ok and result.data.missing_documents == ["PHOTO_PLATE"]
    dumped = result.model_dump_json()
    assert "customer" not in dumped and "María" not in dumped and "612 345 678" not in dumped


def test_unknown_claim_is_not_found_without_retry():
    http, calls = fake_http(lambda r: httpx.Response(404, json={"detail": "claim not found"}))
    assert tools.get_claim(ctx(http=http), claim_id="EXP-99999").error.code == "NOT_FOUND"
    assert len(calls) == 1


@pytest.mark.parametrize("handler, code", [
    (lambda r: httpx.Response(500), "UPSTREAM_ERROR"),
    (lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=r)), "TIMEOUT"),
    (lambda r: (_ for _ in ()).throw(httpx.ConnectError("down", request=r)), "UPSTREAM_ERROR"),
])
def test_transient_workshop_failures_are_retried_then_reported(handler, code):
    http, calls = fake_http(handler)
    result = tools.get_workshop(ctx(http=http), workshop_id="T-228")
    assert result.error.code == code and result.error.retryable
    assert len(calls) == tools.READ_ATTEMPTS


def test_incomplete_backend_response_is_an_error_not_a_guess():
    http, _ = fake_http(lambda r: httpx.Response(200, json={"claim_id": "EXP-10234", "status": "REPAIRING"}))
    result = tools.get_claim(ctx(http=http), claim_id="EXP-10234")
    assert result.error.code == "UPSTREAM_ERROR" and "incompleta" in result.error.message


def test_events_db_down_is_reported():
    def down(claim_id, limit):
        raise psycopg.OperationalError("connection refused")

    result = tools.get_claim_events(ctx(events=down), claim_id="EXP-10234")
    assert result.error.code == "DB_UNAVAILABLE" and result.error.retryable


# --- propose_action: the deterministic decision ---

def test_propose_request_for_missing_plate_photo():
    result = tools.propose_action(ctx(), claim_id="EXP-10234", document="PHOTO_PLATE")
    assert result.ok, result.error
    pending = result.data
    assert (pending.claim_id, pending.workshop_id, pending.user_id) == ("EXP-10234", "T-228", "luis")
    assert pending.warnings == [] and pending.expires_at == NOW + tools.PENDING_TTL
    assert pending.confirmation_text.startswith("He comprobado que falta la fotografía de matrícula")
    assert "T-228" in pending.confirmation_text and pending.confirmation_text.endswith("¿Confirmas que ejecute la acción?")


@pytest.mark.parametrize("claim_id, document, reason", [
    ("EXP-10235", "PHOTO_PLATE", "no figura como pendiente"),  # nothing missing
    ("EXP-10236", "REPAIR_BUDGET", "INACTIVE"),  # inactive workshop
])
def test_propose_refused_when_preconditions_fail(claim_id, document, reason):
    result = tools.propose_action(ctx(), claim_id=claim_id, document=document)
    assert result.error.code == "PRECONDITION_FAILED" and reason in result.error.message


@pytest.mark.parametrize("claim_id, warned", [("EXP-10237", True), ("EXP-10242", False)])
def test_propose_warns_only_on_recent_duplicate(claim_id, warned):
    result = tools.propose_action(ctx(), claim_id=claim_id, document="PHOTO_PLATE")
    assert result.ok and bool(result.data.warnings) == warned
    assert ("Atención" in result.data.confirmation_text) == warned


def test_no_proposal_when_workshop_api_fails(monkeypatch):
    monkeypatch.setenv("FAULT_WORKSHOPS", "500")
    result = tools.propose_action(ctx(), claim_id="EXP-10234", document="PHOTO_PLATE")
    assert not result.ok and result.error.code == "UPSTREAM_ERROR"


def test_proposal_still_made_but_flagged_when_history_is_down():
    def down(claim_id, limit):
        raise psycopg.OperationalError("connection refused")

    result = tools.propose_action(ctx(events=down), claim_id="EXP-10234", document="PHOTO_PLATE")
    assert result.ok and "histórico" in result.data.warnings[0]


# --- execute_action ---

@pytest.fixture
def backend_events(monkeypatch):
    written = []
    monkeypatch.setattr(mock_services, "record_event", lambda *a: written.append(a))
    monkeypatch.setattr(mock_services, "_processed", {})
    return written


def propose(user_id="luis"):
    return tools.propose_action(ctx(user_id), claim_id="EXP-10234", document="PHOTO_PLATE").data


def test_execute_twice_runs_once(backend_events):
    pending, c = propose(), ctx()
    first, second = tools.execute_action(c, pending), tools.execute_action(c, pending)
    assert first.ok and first.data == second.data and len(backend_events) == 1


def test_lost_response_is_retried_safely(backend_events):
    real = TestClient(mock_services.app)
    attempts = []

    def lose_first_response(request):
        attempts.append(request)
        response = real.request(request.method, request.url.path, content=request.content, headers=request.headers)
        if len(attempts) == 1:
            raise httpx.ReadTimeout("response lost", request=request)  # executed, but we never saw it
        return httpx.Response(response.status_code, content=response.content, headers=response.headers)

    http, _ = fake_http(lose_first_response)
    result = tools.execute_action(ctx(http=http), propose())
    assert result.ok and len(attempts) == 2 and len(backend_events) == 1


@pytest.mark.parametrize("user_id, now, code", [
    ("marta", NOW, "FORBIDDEN"),  # prepared by luis
    ("luis", NOW + tools.PENDING_TTL + timedelta(seconds=1), "EXPIRED"),
])
def test_execute_revalidates(backend_events, user_id, now, code):
    result = tools.execute_action(ctx(user_id, now=now), propose())
    assert result.error.code == code and backend_events == []
