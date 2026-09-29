"""The agent as a LangGraph state machine.

START → authorize → screen ─┬─ (blocked | bulk_data | off_topic | forbidden) ───────────────→ respond → END
                            └─ agent ⇄ tools (max MAX_STEPS) ─┬─ propose_action OK → confirm ─┬─ yes → execute → respond
                                                              │                              └─ no ──────────→ respond
                                                              └─ final answer → respond (output guardrail) → END

The LLM chooses read tools and drafts answers. The code decides identity, which tools are bound (role ∩ intent),
the confirmation (an interrupt only resumable from outside the conversation), the execution and every template.
"""

import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt

from okore_agent import security, tools, trace
from okore_agent.judge import Judge
from okore_agent.tools import DOCUMENT_LABELS, TOOLS, PendingAction, ToolContext

MAX_STEPS = 6  # LLM calls per turn

# Routing policy over the judge's probabilities. Thresholds are per stake and must be re-tuned on real traffic.
INJECTION_BLOCK = 0.70  # refuse the turn
INJECTION_REVIEW = 0.35  # proceed read-only and flag
INTENT_MIN_CONFIDENCE = 0.50  # below this the intent is ignored: read-only agent
OUTPUT_BLOCK = 0.70

ANSWERS = {
    "unknown_user": "No reconozco tu usuario, así que no puedo atender la petición.",
    "blocked": "No puedo procesar esta petición: intenta saltarse las reglas del asistente. Queda registrada.",
    "bulk_data": "No puedo listar expedientes ni facilitar datos personales de clientes. "
                 "Puedo consultar un expediente concreto si me indicas su número (EXP-12345).",
    "off_topic": "Solo puedo consultar expedientes concretos y solicitar al taller los documentos que falten.",
    "forbidden": "Tu rol solo permite consultar expedientes; no puedes solicitar documentos al taller.",
    "cancelled": "Acción cancelada: no se ha enviado nada al taller.",
    "step_limit": "No he llegado a una respuesta en el número de pasos permitido. Prueba con una petición más concreta.",
    "withheld": "He retenido la respuesta porque no ha superado los controles de salida. Queda registrada.",
    "llm_unavailable": "El modelo de lenguaje no responde ahora mismo, así que no he hecho nada. "
                       "Inténtalo de nuevo en unos minutos.",
}


class AgentState(TypedDict, total=False):
    request_id: str
    user_id: str
    messages: Annotated[list[AnyMessage], add_messages]
    judgment: dict  # input screening, kept for the trace
    output_judgment: dict | None
    route: str
    suspicious: bool
    tools_enabled: list[str]
    llm_model: str
    tool_calls: list[dict]  # name, args, result, latency
    errors: list[dict]
    pending_action: dict | None
    action_result: dict | None
    final_decision: str
    answer: str
    steps: int


def build_graph(
    llm: BaseChatModel,
    judge: Judge,
    make_context: Callable[[security.User], ToolContext] = tools.default_context,
    checkpointer=None,
):
    def authorize(state: AgentState) -> dict:
        # A new turn discards whatever the previous one left, including an unconfirmed proposal.
        turn = {
            "request_id": str(uuid.uuid4()), "judgment": {}, "output_judgment": None, "route": "", "suspicious": False,
            "tools_enabled": [], "tool_calls": [], "errors": [], "pending_action": None, "action_result": None,
            "final_decision": "", "answer": "", "steps": 0,
            "llm_model": getattr(llm, "model_name", None) or llm._llm_type,
        }
        try:
            security.get_user(state["user_id"])
        except security.UnknownUser:
            turn["final_decision"] = "unknown_user"
        return turn

    def screen(state: AgentState) -> dict:
        user = security.get_user(state["user_id"])
        humans = [m.content for m in state["messages"] if isinstance(m, HumanMessage)]
        j = judge.screen_input(humans[-1], humans[-2] if len(humans) > 1 else None)
        route, enabled = _route(j, user)
        return {
            "judgment": asdict(j),
            "route": route,
            "suspicious": j.injection >= INJECTION_REVIEW or route == "bulk_data",
            "tools_enabled": sorted(enabled),
            "final_decision": "" if route == "agent" else route,
            "errors": state["errors"] + _judge_error(j.source),
        }

    def agent(state: AgentState) -> dict:
        bound = llm.bind_tools([_tool_spec(name) for name in state["tools_enabled"]])
        steps = state["steps"] + 1
        try:
            reply = bound.invoke(state["messages"])
        except Exception as exc:  # external model boundary: down, timeout, malformed output. Nothing was done.
            return {"steps": steps, "final_decision": "llm_unavailable", "errors": state["errors"] + [{
                "tool": "llm", "code": "UPSTREAM_ERROR", "message": f"{type(exc).__name__}: {exc}"[:300],
                "retryable": True}]}
        if reply.tool_calls and steps >= MAX_STEPS:
            return {"messages": [reply], "steps": steps, "final_decision": "step_limit"}
        return {"messages": [reply], "steps": steps}

    def run_tools(state: AgentState) -> dict:
        ctx = make_context(security.get_user(state["user_id"]))
        messages, log, errors, pending = [], [], [], None
        for call in state["messages"][-1].tool_calls:
            started = time.perf_counter()
            if call["name"] in state["tools_enabled"]:
                result = TOOLS[call["name"]](ctx, **call["args"])
            else:  # never offered to the LLM: role or intent excludes it
                result = tools.ToolResult(ok=False, error=tools.ToolError(
                    code="FORBIDDEN", message=f"La herramienta {call['name']} no está disponible en esta petición."))
            log.append(_call_log(call["name"], call["args"], result, started))
            if result.error:
                errors.append({"tool": call["name"], **result.error.model_dump()})
            if call["name"] == "propose_action" and result.ok:
                pending = result.data.model_dump(mode="json")
            messages.append(ToolMessage(result.model_dump_json(), tool_call_id=call["id"], name=call["name"]))
        return {
            "messages": messages,
            "tool_calls": state["tool_calls"] + log,
            "errors": state["errors"] + errors,
            "pending_action": pending,
        }

    def confirm(state: AgentState) -> dict:
        pending = state["pending_action"]
        decision = interrupt({"pending_action_id": pending["pending_action_id"], "text": pending["confirmation_text"]})
        # Only the exact structured answer from the user who asked counts as a yes.
        approved = (
            isinstance(decision, dict) and decision.get("confirm") is True
            and decision.get("user_id") == state["user_id"]
        )
        return {"final_decision": "confirmed" if approved else "cancelled"}

    def execute(state: AgentState) -> dict:
        ctx = make_context(security.get_user(state["user_id"]))
        started = time.perf_counter()
        result = tools.execute_action(ctx, PendingAction.model_validate(state["pending_action"]))
        args = {"pending_action_id": state["pending_action"]["pending_action_id"]}
        return {
            "action_result": result.model_dump(mode="json"),
            "tool_calls": state["tool_calls"] + [_call_log("execute_action", args, result, started)],
            "final_decision": "executed" if result.ok else "execution_failed",
            "errors": state["errors"] + ([{"tool": "execute_action", **result.error.model_dump()}] if result.error else []),
        }

    def respond(state: AgentState) -> dict:
        decision = state["final_decision"] or "answered"
        pending = state.get("pending_action")
        if decision == "executed":
            text = (f"Hecho: se ha solicitado {DOCUMENT_LABELS[pending['document']]} al taller "
                    f"{pending['workshop_id']} ({pending['workshop_name']}) para el expediente {pending['claim_id']}.")
        elif decision == "execution_failed":
            error = state["action_result"]["error"]
            text = f"No se ha podido ejecutar la acción: {error['message']}"
            if error["retryable"]:  # timeout/5xx: the backend may have registered it and the response got lost
                text += (" No puedo asegurar si el backend llegó a registrarla: revisa el histórico del expediente "
                         "antes de volver a pedirla (si ya consta, la nueva propuesta te avisará del duplicado).")
        elif decision in ANSWERS:
            text = ANSWERS[decision]
        else:  # the LLM's own answer: second guardrail before it reaches the user
            reply = state["messages"][-1]
            out = judge.screen_output(reply.content)
            errors = state["errors"] + _judge_error(out.source)
            if max(out.claims_done, out.personal_data) >= OUTPUT_BLOCK:
                return {
                    "messages": [AIMessage(ANSWERS["withheld"], id=reply.id)],  # same id: replaces the LLM's text
                    "answer": ANSWERS["withheld"], "final_decision": "withheld", "suspicious": True,
                    "output_judgment": asdict(out), "errors": errors,
                }
            return {"answer": reply.content, "final_decision": decision, "output_judgment": asdict(out),
                    "errors": errors}
        return {
            "messages": [AIMessage(text)], "answer": text, "final_decision": decision,
            "pending_action": None,  # consumed (executed, failed or cancelled): nothing left to confirm
        }

    g = StateGraph(AgentState)
    for name, node in [("authorize", authorize), ("screen", screen), ("agent", agent), ("tools", run_tools),
                       ("confirm", confirm), ("execute", execute), ("respond", respond)]:
        g.add_node(name, node)
    g.add_edge(START, "authorize")
    g.add_conditional_edges("authorize", lambda s: "respond" if s["final_decision"] else "screen")
    g.add_conditional_edges("screen", lambda s: "agent" if s["route"] == "agent" else "respond")
    g.add_conditional_edges(
        "agent", lambda s: "tools" if not s["final_decision"] and s["messages"][-1].tool_calls else "respond")
    g.add_conditional_edges(
        "tools", lambda s: "confirm" if s["pending_action"] else "agent")
    g.add_conditional_edges("confirm", lambda s: "execute" if s["final_decision"] == "confirmed" else "respond")
    g.add_edge("execute", "respond")
    g.add_edge("respond", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())


def _route(j, user: security.User) -> tuple[str, frozenset[str]]:
    """Policy over the judgment. Only narrows: the result is always a subset of the role's tools."""
    if j.injection >= INJECTION_BLOCK:
        return "blocked", frozenset()
    confident = j.confidence >= INTENT_MIN_CONFIDENCE
    if confident and j.intent in ("bulk_data", "other"):
        return ("bulk_data" if j.intent == "bulk_data" else "off_topic"), frozenset()
    wants_action = confident and j.intent == "request_document"
    if wants_action and not security.can_act(user, "REQUEST_DOCUMENT"):
        return "forbidden", frozenset()
    # propose_action only when the request clearly asks for it; anything doubtful gets read tools only.
    if wants_action and j.injection < INJECTION_REVIEW:
        return "agent", security.allowed_tools(user)
    return "agent", security.allowed_tools(user) & security.READ_TOOLS


def _call_log(name: str, args: dict, result: tools.ToolResult, started: float) -> dict:
    # Tool outputs are PII-free by construction (tools.*View), so logging them whole is safe.
    return {"name": name, "args": args, "result": result.model_dump(mode="json"),
            "latency_ms": round((time.perf_counter() - started) * 1000)}


def _judge_error(source: str) -> list[dict]:
    """Jev fell back to rules: not fatal, but never silent."""
    if not source.startswith("rules ("):
        return []
    return [{"tool": "judge", "code": "UPSTREAM_ERROR", "message": source, "retryable": True}]


def _tool_spec(name: str) -> dict:
    fn = TOOLS[name]
    return {"type": "function", "function": {
        "name": name, "description": fn.__doc__, "parameters": fn.input_model.model_json_schema()}}


# --- Entry points for CLI/API ---

@dataclass(frozen=True)
class Reply:
    answer: str
    decision: str
    awaiting_confirmation: bool = False


def ask(graph, thread_id: str, user_id: str, text: str) -> Reply:
    config = {"configurable": {"thread_id": thread_id}}

    def run() -> Reply:
        graph.invoke({"user_id": user_id, "messages": [HumanMessage(text)]}, config)
        return _reply(graph, config)

    return _traced(graph, config, "ask", user_id, text, run)


def confirm(graph, thread_id: str, user_id: str, approve: bool) -> Reply:
    """The only way to resume a paused thread. The LLM cannot call this: it is not a tool."""
    config = {"configurable": {"thread_id": thread_id}}

    def run() -> Reply:
        if not graph.get_state(config).interrupts:
            return Reply("No hay ninguna acción pendiente de confirmar.", "no_pending_action")
        graph.invoke(Command(resume={"confirm": approve, "user_id": user_id}), config)
        return _reply(graph, config)

    return _traced(graph, config, "confirm", user_id, f"[confirm approve={approve}]", run)


def _reply(graph, config) -> Reply:
    snapshot = graph.get_state(config)
    if snapshot.interrupts:
        return Reply(snapshot.interrupts[0].value["text"], "awaiting_confirmation", awaiting_confirmation=True)
    return Reply(snapshot.values["answer"], snapshot.values["final_decision"])


def _traced(graph, config, kind: str, user_id: str, user_request: str, run: Callable[[], Reply]) -> Reply:
    """Runs one ask/confirm and always writes its trace line, including when the run crashes."""
    before = graph.get_state(config).values
    # A confirm resumes the ask's turn: its line covers only what happens after the resume.
    offset = len(before.get("tool_calls", [])) if kind == "confirm" else 0
    pending_before = before.get("pending_action") if kind == "confirm" else None
    started = time.perf_counter()
    reply, crash = None, None
    try:
        reply = run()
        return reply
    except Exception as exc:
        crash = exc
        raise
    finally:
        values = graph.get_state(config).values
        if reply and reply.decision == "no_pending_action":
            values, offset = {}, 0
        calls = values.get("tool_calls", [])[offset:]
        pending = pending_before or (values.get("pending_action") if reply and reply.awaiting_confirmation else None)
        judgment = values.get("judgment") or {}
        user = security.USERS.get(user_id)
        attempted = kind == "confirm" and values.get("final_decision") in ("executed", "execution_failed")
        errors = values.get("errors", []) + (
            [{"tool": "agent", "code": "INTERNAL_ERROR", "message": repr(crash)[:300], "retryable": False}]
            if crash else [])
        trace.write({
            "request_id": values.get("request_id"),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "kind": kind,
            "thread_id": config["configurable"]["thread_id"],
            "user_id": user_id,
            "role": user.role if user else None,
            "user_request": user_request,
            "detected_intent": judgment.get("intent"),
            "intent_confidence": judgment.get("confidence"),
            "injection": judgment.get("injection"),
            "judge_source": judgment.get("source"),
            "suspicious": values.get("suspicious", False),
            "route": values.get("route"),
            "tools_enabled": values.get("tools_enabled"),
            "llm_model": values.get("llm_model"),
            "llm_steps": values.get("steps"),
            "tools_called": [c["name"] for c in calls],
            "tool_parameters": [c["args"] for c in calls],
            "tool_results": [{**c["result"], "latency_ms": c["latency_ms"]} for c in calls],
            "final_decision": reply.decision if reply else "error",
            "answer": reply.answer if reply else None,
            "output_judgment": values.get("output_judgment"),
            "action_requested": pending,
            "pending_action_id": pending and pending["pending_action_id"],
            "idempotency_key": pending["pending_action_id"] if attempted else None,
            "action_executed": kind == "confirm" and values.get("final_decision") == "executed",
            "action_result": values.get("action_result") if kind == "confirm" else None,
            "errors": errors,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        })

