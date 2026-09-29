"""Chat with the agent from a terminal.

    uv run --env-file .env python -m okore_agent.cli --user luis
    uv run --env-file .env python -m okore_agent.cli --user ana "¿En qué estado está EXP-10234?"

The identity comes from --user, never from the chat. Confirmations are asked here, outside the conversation:
typing "sí, confirmo" in the chat is just another message and executes nothing.
"""

import argparse
import uuid

from okore_agent import graph as agent_graph, trace
from okore_agent.judge import default_judge
from okore_agent.llm import PROMPT_VERSION, default_llm
from okore_agent.security import USERS

YES = {"s", "si", "sí", "y", "yes"}


def main() -> None:
    users = ", ".join(f"{u.user_id} ({u.role})" for u in USERS.values())
    parser = argparse.ArgumentParser(description="OKORE claims agent")
    parser.add_argument("--user", required=True, help=f"Simulated identity: {users}")
    parser.add_argument("message", nargs="?", help="Ask once and exit (default: interactive chat)")
    args = parser.parse_args()

    llm, judge = default_llm(), default_judge()
    graph = agent_graph.build_graph(llm, judge)
    thread = str(uuid.uuid4())
    model = getattr(llm, "model_name", None) or llm._llm_type
    print(f"usuario={args.user} · llm={model} ({PROMPT_VERSION}) · juez={type(judge).__name__} · traza={trace.TRACE_PATH}")

    if args.message:
        turn(graph, thread, args.user, args.message)
        return
    print("Escribe tu petición ('salir' para terminar).")
    while True:
        try:
            text = input(f"\n{args.user}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text.lower() in ("salir", "exit", "quit"):
            return
        if text:
            turn(graph, thread, args.user, text)


def turn(graph, thread: str, user: str, text: str) -> None:
    reply = agent_graph.ask(graph, thread, user, text)
    print(f"agente> {reply.answer}")
    if reply.awaiting_confirmation:
        try:
            # lstrip: Windows PowerShell prepends a BOM when piping ("s" | ...).
            approve = input("¿Confirmas? [s/N] ").lstrip("﻿").strip().lower() in YES
        except (EOFError, KeyboardInterrupt):
            approve = False
        print(f"agente> {agent_graph.confirm(graph, thread, user, approve).answer}")


if __name__ == "__main__":
    main()
