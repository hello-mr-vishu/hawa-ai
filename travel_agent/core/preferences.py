"""Async CRUD for user travel preferences stored in SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from travel_agent.core.logging import get_logger

logger = get_logger(__name__)

# Reuse the ADK session DB directory; keep all persistent state in one file
_DB_PATH = Path(__file__).parent.parent / ".adk" / "session.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS travel_user_preferences (
    user_id             TEXT PRIMARY KEY,
    preferred_destinations TEXT,
    budget_tier         TEXT,
    interests           TEXT,
    dietary_restrictions TEXT,
    home_airport        TEXT,
    updated_at          TEXT
);
"""


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_TABLE_SQL)
    conn.commit()
    return conn


def save_preferences(user_id: str, prefs: dict) -> None:
    """Insert or update user preferences."""
    now = datetime.now(tz=timezone.utc).isoformat()
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO travel_user_preferences
                (user_id, preferred_destinations, budget_tier, interests,
                 dietary_restrictions, home_airport, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                preferred_destinations = excluded.preferred_destinations,
                budget_tier = excluded.budget_tier,
                interests = excluded.interests,
                dietary_restrictions = excluded.dietary_restrictions,
                home_airport = excluded.home_airport,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                json.dumps(prefs.get("preferred_destinations") or []),
                prefs.get("budget_tier"),
                json.dumps(prefs.get("interests") or []),
                prefs.get("dietary_restrictions"),
                prefs.get("home_airport"),
                now,
            ),
        )
        conn.commit()
        logger.info("Preferences saved", extra={"extra": {"user_id": user_id}})
    finally:
        conn.close()


def get_preferences(user_id: str) -> Optional[dict]:
    """Return preferences dict for user_id, or None if not found."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM travel_user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "user_id": row["user_id"],
            "preferred_destinations": json.loads(row["preferred_destinations"] or "[]"),
            "budget_tier": row["budget_tier"],
            "interests": json.loads(row["interests"] or "[]"),
            "dietary_restrictions": row["dietary_restrictions"],
            "home_airport": row["home_airport"],
            "updated_at": row["updated_at"],
        }
    finally:
        conn.close()


def build_preference_context(user_id: str) -> str:
    """Return a natural-language summary of preferences to prepend to agent queries."""
    prefs = get_preferences(user_id)
    if not prefs:
        return ""

    parts = []
    if prefs.get("budget_tier"):
        parts.append(f"budget={prefs['budget_tier']}")
    if prefs.get("interests"):
        parts.append(f"interests={prefs['interests']}")
    if prefs.get("home_airport"):
        parts.append(f"home_airport={prefs['home_airport']}")
    if prefs.get("preferred_destinations"):
        parts.append(f"previously_visited={prefs['preferred_destinations']}")
    if prefs.get("dietary_restrictions"):
        parts.append(f"dietary={prefs['dietary_restrictions']}")

    if not parts:
        return ""

    return f"[User preferences: {', '.join(parts)}]\n"
