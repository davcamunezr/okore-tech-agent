"""Simulated backend: claims, workshops and actions APIs.

Customer PII is present on purpose: the agent's tools must project it away.
Run: uv run uvicorn okore_agent.mock_services:app --port 8001
"""

import asyncio
import os
import uuid
from datetime import datetime
from typing import Literal

import psycopg
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

CLAIMS = {
    # The brief's claim (cases 1 and 2): plate photo missing, never requested yet.
    "EXP-10234": {
        "claim_id": "EXP-10234",
        "status": "REPAIRING",
        "vehicle": {"plate": "1234ABC", "brand": "BMW", "model": "X1"},
        "workshop_id": "T-228",
        "missing_documents": ["PHOTO_PLATE"],
        "last_update": "2026-09-22T10:32:00",
        "customer": {"name": "María López García", "phone": "+34 612 345 678", "email": "maria.lopez@example.com"},
    },
    # Repair finished, nothing pending.
    "EXP-10235": {
        "claim_id": "EXP-10235",
        "status": "READY_FOR_PICKUP",
        "vehicle": {"plate": "5678DFG", "brand": "Seat", "model": "Ibiza"},
        "workshop_id": "T-228",
        "missing_documents": [],
        "last_update": "2026-09-05T17:45:00",
        "customer": {"name": "Jorge Martín Ruiz", "phone": "+34 698 765 432", "email": "jorge.martin@example.com"},
    },
    # Assigned to an inactive workshop: a request must not be proposed.
    "EXP-10236": {
        "claim_id": "EXP-10236",
        "status": "WAITING_DOCUMENTS",
        "vehicle": {"plate": "9012GHJ", "brand": "Toyota", "model": "Corolla"},
        "workshop_id": "T-305",
        "missing_documents": ["REPAIR_BUDGET"],
        "last_update": "2026-09-20T09:00:00",
        "customer": {"name": "Lucía Fernández Soto", "phone": "+34 655 111 222", "email": "lucia.fernandez@example.com"},
    },
    # Plate photo missing but already requested 3 days ago: likely duplicate.
    "EXP-10237": {
        "claim_id": "EXP-10237",
        "status": "REPAIRING",
        "vehicle": {"plate": "3456JKL", "brand": "Renault", "model": "Clio"},
        "workshop_id": "T-412",
        "missing_documents": ["PHOTO_PLATE"],
        "last_update": "2026-09-25T09:30:00",
        "customer": {"name": "Andrés Navarro Gil", "phone": "+34 677 222 333", "email": "andres.navarro@example.com"},
    },
    # Damage photos were requested and received earlier; now the budget is missing.
    "EXP-10238": {
        "claim_id": "EXP-10238",
        "status": "WAITING_DOCUMENTS",
        "vehicle": {"plate": "7890MNP", "brand": "Volkswagen", "model": "Golf"},
        "workshop_id": "T-517",
        "missing_documents": ["REPAIR_BUDGET"],
        "last_update": "2026-09-18T08:00:00",
        "customer": {"name": "Carmen Ortega Vidal", "phone": "+34 644 333 444", "email": "carmen.ortega@example.com"},
    },
    # Full lifecycle, closed.
    "EXP-10239": {
        "claim_id": "EXP-10239",
        "status": "CLOSED",
        "vehicle": {"plate": "2468BCD", "brand": "Peugeot", "model": "308"},
        "workshop_id": "T-228",
        "missing_documents": [],
        "last_update": "2026-08-20T09:00:00",
        "customer": {"name": "Pablo Serrano Díaz", "phone": "+34 633 444 555", "email": "pablo.serrano@example.com"},
    },
    # Just entered the workshop, waiting for the expert.
    "EXP-10240": {
        "claim_id": "EXP-10240",
        "status": "WAITING_ASSESSMENT",
        "vehicle": {"plate": "1357FGH", "brand": "Kia", "model": "Sportage"},
        "workshop_id": "T-633",
        "missing_documents": [],
        "last_update": "2026-09-24T11:00:00",
        "customer": {"name": "Elena Castro Romero", "phone": "+34 622 555 666", "email": "elena.castro@example.com"},
    },
    # Two documents missing, nothing requested yet.
    "EXP-10241": {
        "claim_id": "EXP-10241",
        "status": "WAITING_DOCUMENTS",
        "vehicle": {"plate": "8642KLM", "brand": "Ford", "model": "Focus"},
        "workshop_id": "T-412",
        "missing_documents": ["PHOTO_PLATE", "PHOTO_DAMAGE"],
        "last_update": "2026-09-27T10:00:00",
        "customer": {"name": "Raúl Moreno Prieto", "phone": "+34 611 666 777", "email": "raul.moreno@example.com"},
    },
    # Plate photo requested twice weeks ago with no answer: candidate for escalation.
    "EXP-10242": {
        "claim_id": "EXP-10242",
        "status": "REPAIRING",
        "vehicle": {"plate": "9753NPR", "brand": "Audi", "model": "A3"},
        "workshop_id": "T-517",
        "missing_documents": ["PHOTO_PLATE"],
        "last_update": "2026-09-16T09:30:00",
        "customer": {"name": "Sofía Ramos Herrera", "phone": "+34 699 777 888", "email": "sofia.ramos@example.com"},
    },
}

WORKSHOPS = {
    "T-228": {
        "workshop_id": "T-228",
        "name": "Talleres Norte Madrid",
        "contact": {"email": "recepcion@talleresnorte.example", "phone": "+34 910 000 228"},
        "status": "ACTIVE",
        "channels": ["EMAIL", "PORTAL"],
    },
    "T-305": {
        "workshop_id": "T-305",
        "name": "Chapa y Pintura Levante",
        "contact": {"email": "info@chapalevante.example", "phone": "+34 960 000 305"},
        "status": "INACTIVE",
        "channels": ["PHONE"],
    },
    "T-412": {
        "workshop_id": "T-412",
        "name": "Autotaller Sur Sevilla",
        "contact": {"email": "citas@autotallersur.example", "phone": "+34 954 000 412"},
        "status": "ACTIVE",
        "channels": ["EMAIL", "PHONE"],
    },
    "T-517": {
        "workshop_id": "T-517",
        "name": "Carrocerías Galicia",
        "contact": {"email": "taller@carroceriasgalicia.example", "phone": "+34 981 000 517"},
        "status": "ACTIVE",
        "channels": ["EMAIL", "PORTAL", "PHONE"],
    },
    "T-633": {
        "workshop_id": "T-633",
        "name": "Mecánica Bilbao Centro",
        "contact": {"email": "admin@mecanicabilbao.example", "phone": "+34 944 000 633"},
        "status": "ACTIVE",
        "channels": ["PORTAL"],
    },
}


class ActionRequest(BaseModel):
    action: Literal["REQUEST_DOCUMENT"]
    document: Literal["PHOTO_PLATE", "PHOTO_DAMAGE", "REPAIR_BUDGET", "REPAIR_INVOICE"]


# ponytail: in-memory idempotency store, lost on restart; persist keys (unique column) for a real backend.
_processed: dict[str, tuple[str, ActionRequest, dict]] = {}

app = FastAPI(title="OKORE mock services")


@app.get("/api/claims/{claim_id}")
def get_claim(claim_id: str):
    if claim_id not in CLAIMS:
        raise HTTPException(404, "claim not found")
    return CLAIMS[claim_id]


@app.get("/api/workshops/{workshop_id}")
async def get_workshop(workshop_id: str):
    # Case 3 fault injection. Read per request so tests can monkeypatch it; in Docker, recreate the container:
    # FAULT_WORKSHOPS=500 docker compose up -d mocks
    fault = os.environ.get("FAULT_WORKSHOPS", "")
    if fault == "500":
        raise HTTPException(500, "workshops service error")
    if fault == "timeout":
        await asyncio.sleep(30)
    if workshop_id not in WORKSHOPS:
        raise HTTPException(404, "workshop not found")
    return WORKSHOPS[workshop_id]


@app.post("/api/claims/{claim_id}/actions", status_code=201)
def post_action(claim_id: str, body: ActionRequest, idempotency_key: str = Header(min_length=1)):
    if idempotency_key in _processed:
        prev_claim, prev_body, response = _processed[idempotency_key]
        if (prev_claim, prev_body) != (claim_id, body):
            raise HTTPException(422, "Idempotency-Key reused with a different request")
        return response
    claim = CLAIMS.get(claim_id)
    if claim is None:
        raise HTTPException(404, "claim not found")
    if body.document not in claim["missing_documents"]:
        raise HTTPException(409, f"{body.document} is not missing for {claim_id}")

    record_event(claim_id, "DOCUMENT_REQUESTED",
                 f"Solicitado {body.document} al taller {claim['workshop_id']}.", "actions-api")
    # The document stays in missing_documents until the workshop sends it.
    response = {
        "action_id": str(uuid.uuid4()),
        "claim_id": claim_id,
        "action": body.action,
        "document": body.document,
        "workshop_id": claim["workshop_id"],
        "status": "REQUESTED",
        "requested_at": datetime.now().isoformat(timespec="seconds"),
    }
    _processed[idempotency_key] = (claim_id, body, response)
    return response


def record_event(claim_id: str, event_type: str, description: str, actor: str) -> None:
    """Append to the event history with the write role. Tests monkeypatch this."""
    url = os.environ.get("BACKEND_DB_URL", "postgresql://backend_rw:backend_rw@localhost:5432/okore")
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            conn.execute(
                "INSERT INTO claim_events (claim_id, event_type, description, actor) VALUES (%s, %s, %s, %s)",
                (claim_id, event_type, description, actor),
            )
    except psycopg.Error as exc:
        raise HTTPException(503, "event store unavailable") from exc
