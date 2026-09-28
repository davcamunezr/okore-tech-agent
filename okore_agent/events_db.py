"""Read access to the claim event history. The only DB entry point the agent has."""

import os

import psycopg
from psycopg.rows import dict_row


def get_claim_events(claim_id: str, limit: int = 20) -> list[dict]:
    """Most recent events first. Connects as agent_ro (read-only, statement_timeout set on the role)."""
    url = os.environ.get("AGENT_DB_URL", "postgresql://agent_ro:agent_ro@localhost:5432/okore")
    with psycopg.connect(url, connect_timeout=3, row_factory=dict_row) as conn:
        return conn.execute(
            "SELECT event_type, event_date, description, actor FROM claim_events"
            " WHERE claim_id = %s ORDER BY event_date DESC LIMIT %s",
            (claim_id, limit),
        ).fetchall()
