"""HTTP API and a minimal web UI for the agent.

    uv run --env-file .env uvicorn okore_agent.api:app --port 8000     → http://localhost:8000

Identity comes from the X-User-Id header, never from the chat. Each conversation (thread) belongs to the user who
started it: nobody else can continue it, read its history or confirm its pending action.
"""

import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from okore_agent import graph as agent_graph
from okore_agent.judge import default_judge
from okore_agent.llm import default_llm
from okore_agent.security import USERS

UI = Path(__file__).parent / "static" / "index.html"


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = Field(None, min_length=1, max_length=64)


class ConfirmIn(BaseModel):
    thread_id: str = Field(min_length=1, max_length=64)
    approve: bool


class ReplyOut(BaseModel):
    thread_id: str
    answer: str
    decision: str
    awaiting_confirmation: bool


def create_app(graph) -> FastAPI:
    app = FastAPI(title="OKORE claims agent")
    # ponytail: in-memory like the checkpointer; both move to a shared store (Redis/Postgres) to run replicas.
    owners: dict[str, str] = {}

    def identify(x_user_id: str | None) -> str:
        # ponytail: trusts the header, as the CLI trusts --user; in production a gateway/IdP sets it from a
        # validated token and the client can no longer choose it.
        if x_user_id not in USERS:
            raise HTTPException(401, "Usuario no reconocido.")
        return x_user_id

    def own(thread_id: str, user_id: str) -> None:
        if owners.setdefault(thread_id, user_id) != user_id:
            raise HTTPException(403, "Esta conversación pertenece a otro usuario.")

    @app.get("/", include_in_schema=False)
    def ui():
        return FileResponse(UI)

    @app.get("/api/users")
    def users():
        return [
            {"user_id": u.user_id, "role": u.role, "claims": sorted(u.claims) if u.claims is not None else None}
            for u in USERS.values()
        ]

    @app.post("/api/chat")
    def chat(body: ChatIn, x_user_id: str | None = Header(None)) -> ReplyOut:
        user_id = identify(x_user_id)
        thread_id = body.thread_id or str(uuid.uuid4())
        own(thread_id, user_id)
        reply = agent_graph.ask(graph, thread_id, user_id, body.message)
        return ReplyOut(thread_id=thread_id, **reply.__dict__)

    @app.post("/api/chat/confirm")
    def confirm(body: ConfirmIn, x_user_id: str | None = Header(None)) -> ReplyOut:
        user_id = identify(x_user_id)
        own(body.thread_id, user_id)
        reply = agent_graph.confirm(graph, body.thread_id, user_id, body.approve)
        return ReplyOut(thread_id=body.thread_id, **reply.__dict__)

    return app


app = create_app(agent_graph.build_graph(default_llm(), default_judge()))
