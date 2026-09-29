"""Chat models for the agent node. ScriptedLLM: deterministic, no keys, no network (tests and offline demo)."""

import json
import re
import uuid

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from okore_agent.tools import DOCUMENT_LABELS

_CLAIM_ID = re.compile(r"EXP-\d{5}")
_WANTS_REQUEST = re.compile(r"solicit|recl[aá]m|\bpide\b|p[ií]de(le|selo)|\bpedir\b|env[ií]a|\bmanda", re.I)
_WANTS_HISTORY = re.compile(r"esperando|pendiente|hist[oó]ric|historial|eventos|qu[eé] ha pasado|[uú]ltimos? cambios", re.I)


class ScriptedLLM(BaseChatModel):
    """Plays the LLM's part by rules over the current turn: get_claim → (propose_action | get_workshop) → answer.

    obey_binding=False models a compromised LLM that calls tools it was never offered, to test the barriers
    behind the binding.
    """

    tool_names: tuple[str, ...] = ()
    obey_binding: bool = True

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self.model_copy(update={"tool_names": tuple(t["function"]["name"] for t in tools)})

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next(messages))])

    def _may_call(self, name: str) -> bool:
        return name in self.tool_names or not self.obey_binding

    def _next(self, messages: list[BaseMessage]) -> AIMessage:
        start = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        request = messages[start].content
        results = {m.name: json.loads(m.content) for m in messages[start:] if isinstance(m, ToolMessage)}

        claim_id = _CLAIM_ID.search(request)
        if not claim_id:
            return AIMessage("Indícame el número de expediente (formato EXP-12345).")
        claim_id = claim_id.group()
        if "get_claim" not in results:
            return _call("get_claim", claim_id=claim_id)
        claim = results["get_claim"]
        if not claim["ok"]:
            return AIMessage(f"No he podido consultar el expediente {claim_id}: {claim['error']['message']}")
        claim = claim["data"]

        if _WANTS_REQUEST.search(request) and claim["missing_documents"]:
            if "propose_action" not in results and self._may_call("propose_action"):
                return _call("propose_action", claim_id=claim_id, document=claim["missing_documents"][0])
            if "propose_action" in results:  # a successful proposal never comes back here: the graph pauses
                return AIMessage(f"No puedo preparar la solicitud: {results['propose_action']['error']['message']}")

        if "get_workshop" not in results:
            return _call("get_workshop", workshop_id=claim["workshop_id"])
        if _WANTS_HISTORY.search(request) and "get_claim_events" not in results and self._may_call("get_claim_events"):
            return _call("get_claim_events", claim_id=claim_id, limit=3)
        return AIMessage(_summary(claim, results["get_workshop"], results.get("get_claim_events")))


def _call(name: str, **args) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:8]}"}])


def _summary(claim: dict, workshop: dict, events: dict | None = None) -> str:
    vehicle = claim["vehicle"]
    missing = ", ".join(DOCUMENT_LABELS.get(d, d) for d in claim["missing_documents"]) or "ninguno"
    if workshop["ok"]:
        w = workshop["data"]
        shop = f"{w['workshop_id']} ({w['name']}, {w['status']})"
    else:
        shop = f"{claim['workshop_id']}, pero no he podido obtener sus datos: {workshop['error']['message']}"
    text = (
        f"El expediente {claim['claim_id']} está en estado {claim['status']} "
        f"({vehicle['brand']} {vehicle['model']}, {vehicle['plate']}). Documentos pendientes: {missing}. "
        f"Taller asignado: {shop}. Última actualización: {claim['last_update']}."
    )
    if events is None:
        return text
    if not events["ok"]:
        return f"{text} No he podido consultar el histórico: {events['error']['message']}"
    recent = "; ".join(f"{e['event_date'][:10]} {e['description']}" for e in events["data"]) or "sin eventos"
    return f"{text} Últimos eventos: {recent}"
