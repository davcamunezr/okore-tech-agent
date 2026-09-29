"""The only way the agent touches the world.

Every tool: validates its LLM-chosen arguments, re-checks permissions (the LLM is only offered allowed tools,
this is the second barrier), calls the backend with timeouts, and projects the response onto an output model
that has no customer PII. Identity travels in ToolContext, never in the arguments the LLM can write.
"""

import functools
import os
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

import httpx
import psycopg
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from okore_agent import events_db
from okore_agent.security import User, allowed_tools, can_act, can_read

HTTP_TIMEOUT_S = 2.0
READ_ATTEMPTS = 2
WRITE_ATTEMPTS = 2  # safe only because every write carries an Idempotency-Key
BACKOFF_S = 0.3
PENDING_TTL = timedelta(minutes=10)
DUPLICATE_WINDOW = timedelta(days=7)

ClaimId = Annotated[str, StringConstraints(pattern=r"^EXP-\d{5}$")]
WorkshopId = Annotated[str, StringConstraints(pattern=r"^T-\d{3}$")]
Document = Literal["PHOTO_PLATE", "PHOTO_DAMAGE", "REPAIR_BUDGET", "REPAIR_INVOICE"]
ErrorCode = Literal[
    "INVALID_INPUT", "FORBIDDEN", "NOT_FOUND", "PRECONDITION_FAILED", "EXPIRED",
    "UPSTREAM_ERROR", "TIMEOUT", "DB_UNAVAILABLE",
]

DOCUMENT_LABELS = {
    "PHOTO_PLATE": "la fotografía de matrícula",
    "PHOTO_DAMAGE": "las fotografías de los daños",
    "REPAIR_BUDGET": "el presupuesto de reparación",
    "REPAIR_INVOICE": "la factura de reparación",
}


# --- Inputs: what the LLM may write. extra="forbid" so it cannot smuggle parameters. ---

class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimInput(_Input):
    claim_id: ClaimId


class WorkshopInput(_Input):
    workshop_id: WorkshopId = Field(
        description="El workshop_id exacto que devolvió get_claim (formato T-123). No lo deduzcas ni lo inventes."
    )


class EventsInput(ClaimInput):
    limit: int = Field(10, ge=1, le=50)


class ProposeActionInput(ClaimInput):
    document: Document


# --- Outputs: allowlist of fields. Anything not declared (e.g. `customer`) is dropped on validation. ---

class Vehicle(BaseModel):
    plate: str
    brand: str
    model: str


class ClaimView(BaseModel):
    claim_id: str
    status: str
    vehicle: Vehicle
    workshop_id: str
    missing_documents: list[str]
    last_update: datetime


class WorkshopContact(BaseModel):
    email: str | None = None
    phone: str | None = None


class WorkshopView(BaseModel):
    workshop_id: str
    name: str
    contact: WorkshopContact
    status: str
    channels: list[str]


class EventView(BaseModel):
    event_type: str
    event_date: datetime
    description: str
    actor: str


class PendingAction(BaseModel):
    pending_action_id: str
    user_id: str
    claim_id: str
    action: Literal["REQUEST_DOCUMENT"]
    document: Document
    workshop_id: str
    workshop_name: str
    created_at: datetime
    expires_at: datetime
    warnings: list[str]
    confirmation_text: str


class ToolError(BaseModel):
    code: ErrorCode
    message: str
    retryable: bool = False


class ToolResult(BaseModel):
    ok: bool
    data: Any = None
    error: ToolError | None = None


class ToolFailure(Exception):
    def __init__(self, code: ErrorCode, message: str, retryable: bool = False):
        super().__init__(message)
        self.error = ToolError(code=code, message=message, retryable=retryable)


@dataclass(frozen=True)
class ToolContext:
    user: User
    http: httpx.Client
    events: Callable[[str, int], list[dict]] = events_db.get_claim_events
    now: Callable[[], datetime] = field(default=datetime.now)


def default_context(user: User) -> ToolContext:
    base_url = os.environ.get("MOCKS_URL", "http://localhost:8001")
    return ToolContext(user=user, http=httpx.Client(base_url=base_url, timeout=HTTP_TIMEOUT_S))


# --- Tool registry and the single boundary every LLM-callable tool goes through. ---

TOOLS: dict[str, Callable[..., ToolResult]] = {}


def _tool(input_model: type[_Input]):
    def decorate(fn):
        @functools.wraps(fn)
        def boundary(ctx: ToolContext, **kwargs) -> ToolResult:
            try:
                args = input_model.model_validate(kwargs)
            except ValidationError as exc:
                # Worded for the caller (the LLM): the service was never called, the fix is on its side.
                return _fail("INVALID_INPUT", f"Argumentos inválidos, no se ha llamado al servicio: {_describe(exc)}. "
                                              "Corrígelos con valores reales obtenidos antes y vuelve a llamar.")
            if fn.__name__ not in allowed_tools(ctx.user):
                return _fail("FORBIDDEN", f"El rol {ctx.user.role} no puede usar {fn.__name__}.")
            try:
                return ToolResult(ok=True, data=fn(ctx, args))
            except ToolFailure as failure:
                return ToolResult(ok=False, error=failure.error)

        boundary.input_model = input_model
        TOOLS[fn.__name__] = boundary
        return boundary

    return decorate


@_tool(ClaimInput)
def get_claim(ctx: ToolContext, args: ClaimInput) -> ClaimView:
    """Estado del expediente: status, vehículo, taller asignado, documentos pendientes y última actualización."""
    _check_scope(ctx, args.claim_id)
    return _fetch_claim(ctx, args.claim_id)


@_tool(WorkshopInput)
def get_workshop(ctx: ToolContext, args: WorkshopInput) -> WorkshopView:
    """Datos del taller: nombre, contacto, estado (ACTIVE/INACTIVE) y canales disponibles.
    Llámala después de get_claim, cuando ya tengas su workshop_id; no en la misma tanda."""
    return _fetch_workshop(ctx, args.workshop_id)


@_tool(EventsInput)
def get_claim_events(ctx: ToolContext, args: EventsInput) -> list[EventView]:
    """Histórico de eventos del expediente, del más reciente al más antiguo."""
    _check_scope(ctx, args.claim_id)
    return [EventView.model_validate(e) for e in _fetch_events(ctx, args.claim_id, args.limit)]


@_tool(ProposeActionInput)
def propose_action(ctx: ToolContext, args: ProposeActionInput) -> PendingAction:
    """Prepara la solicitud de un documento pendiente al taller. NO la ejecuta: requiere confirmación humana."""
    _check_scope(ctx, args.claim_id)
    if not can_act(ctx.user, "REQUEST_DOCUMENT"):
        raise ToolFailure("FORBIDDEN", "No tienes permiso para solicitar documentos.")

    claim = _fetch_claim(ctx, args.claim_id)
    if args.document not in claim.missing_documents:
        raise ToolFailure("PRECONDITION_FAILED", f"{args.document} no figura como pendiente en {claim.claim_id}.")
    # Any workshop error propagates: no proposal without a verified recipient.
    workshop = _fetch_workshop(ctx, claim.workshop_id)
    if workshop.status != "ACTIVE":
        raise ToolFailure("PRECONDITION_FAILED", f"El taller {workshop.workshop_id} está {workshop.status}.")

    now = ctx.now()
    warnings = []
    try:
        events = _fetch_events(ctx, claim.claim_id, 50)
    except ToolFailure:
        warnings.append("No he podido consultar el histórico: no puedo descartar que ya se haya solicitado.")
    else:
        # ponytail: matches the document code inside the description the actions API writes;
        # add a `document` column to claim_events if descriptions stop being machine-written.
        recent = [
            e for e in events
            if e["event_type"] == "DOCUMENT_REQUESTED"
            and args.document in e["description"]
            and e["event_date"] >= now - DUPLICATE_WINDOW
        ]
        if recent:
            last = max(e["event_date"] for e in recent)
            warnings.append(f"Ya se solicitó este documento el {last:%d/%m/%Y a las %H:%M}.")

    label = DOCUMENT_LABELS[args.document]
    text = (
        f"He comprobado que falta {label} en el expediente {claim.claim_id}. "
        f"Se va a solicitar al taller {workshop.workshop_id} ({workshop.name}). "
        + "".join(f"Atención: {w} " for w in warnings)
        + "¿Confirmas que ejecute la acción?"
    )
    return PendingAction(
        pending_action_id=str(uuid.uuid4()),
        user_id=ctx.user.user_id,
        claim_id=claim.claim_id,
        action="REQUEST_DOCUMENT",
        document=args.document,
        workshop_id=workshop.workshop_id,
        workshop_name=workshop.name,
        created_at=now,
        expires_at=now + PENDING_TTL,
        warnings=warnings,
        confirmation_text=text,
    )


def execute_action(ctx: ToolContext, pending: PendingAction) -> ToolResult:
    """Runs a confirmed PendingAction. Deliberately NOT in TOOLS: only the confirmation flow may call it."""
    if pending.user_id != ctx.user.user_id:
        return _fail("FORBIDDEN", "La acción fue preparada por otro usuario.")
    if not can_act(ctx.user, pending.action) or not can_read(ctx.user, pending.claim_id):
        return _fail("FORBIDDEN", "Ya no tienes permiso para ejecutar esta acción.")
    if ctx.now() > pending.expires_at:
        return _fail("EXPIRED", "La propuesta ha caducado; vuelve a pedirla.")

    try:
        response = _request(
            ctx, "POST", f"/api/claims/{pending.claim_id}/actions", WRITE_ATTEMPTS,
            json={"action": pending.action, "document": pending.document},
            headers={"Idempotency-Key": pending.pending_action_id},
        )
    except ToolFailure as failure:
        return ToolResult(ok=False, error=failure.error)
    return ToolResult(ok=True, data=response)


# --- Internals ---

def _check_scope(ctx: ToolContext, claim_id: str) -> None:
    # Checked before any call, so an out-of-scope id never reveals whether the claim exists.
    if not can_read(ctx.user, claim_id):
        raise ToolFailure("FORBIDDEN", f"No tienes acceso al expediente {claim_id}.")


def _fetch_claim(ctx: ToolContext, claim_id: str) -> ClaimView:
    return _parse(ClaimView, _request(ctx, "GET", f"/api/claims/{claim_id}", READ_ATTEMPTS), "expedientes")


def _fetch_workshop(ctx: ToolContext, workshop_id: str) -> WorkshopView:
    return _parse(WorkshopView, _request(ctx, "GET", f"/api/workshops/{workshop_id}", READ_ATTEMPTS), "talleres")


def _fetch_events(ctx: ToolContext, claim_id: str, limit: int) -> list[dict]:
    try:
        return ctx.events(claim_id, limit)
    except psycopg.Error as exc:
        raise ToolFailure("DB_UNAVAILABLE", f"Histórico no disponible ({type(exc).__name__}).", retryable=True)


def _request(ctx: ToolContext, method: str, path: str, attempts: int, **kwargs) -> dict:
    """Retries only transient failures (timeout, connection, 5xx). 4xx are answers, not failures to retry."""
    failure = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(BACKOFF_S * 2 ** (attempt - 1))
        try:
            response = ctx.http.request(method, path, **kwargs)
        except httpx.TimeoutException:
            failure = ToolFailure("TIMEOUT", f"{method} {path}: sin respuesta a tiempo.", retryable=True)
            continue
        except httpx.TransportError as exc:
            failure = ToolFailure("UPSTREAM_ERROR", f"{method} {path}: servicio no disponible ({exc}).", retryable=True)
            continue
        if response.is_success:
            return response.json()
        if response.status_code == 404:
            raise ToolFailure("NOT_FOUND", f"{path} no existe.")
        if response.status_code == 409:
            raise ToolFailure("PRECONDITION_FAILED", response.json().get("detail", "Conflicto en el backend."))
        if response.status_code >= 500:
            failure = ToolFailure("UPSTREAM_ERROR", f"{method} {path}: error {response.status_code}.", retryable=True)
            continue
        raise ToolFailure("UPSTREAM_ERROR", f"{method} {path}: rechazado con {response.status_code}.")
    raise failure


def _parse(model: type[BaseModel], raw: dict, service: str):
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise ToolFailure("UPSTREAM_ERROR", f"Respuesta incompleta de la API de {service}: {_describe(exc)}")


def _describe(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, e['loc'])) or 'input'}: {e['msg']}" for e in exc.errors())


def _fail(code: ErrorCode, message: str) -> ToolResult:
    return ToolResult(ok=False, error=ToolError(code=code, message=message))
