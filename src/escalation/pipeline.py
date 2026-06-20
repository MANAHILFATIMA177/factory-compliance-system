"""
Module 3: Escalation Pipeline
Routes violations to the correct downstream channel based on severity tier.

Routing rules (from Module spec):
  LOW / MEDIUM  → Persistent DB log only (no real-time alert)
  HIGH / CRITICAL → Real-time alert (WebSocket broadcast) + persistent DB log

Uses aiosqlite for async DB operations and a WebSocket connection manager
for broadcasting real-time alerts to the dashboard.
"""

import json
import aiosqlite
from pathlib import Path
from datetime import datetime, timezone
from typing import Callable, Awaitable

DB_PATH = str(Path(__file__).parent.parent.parent / "outputs" / "compliance_log.db")

# In-memory set of active WebSocket connections (managed by FastAPI)
_ws_connections: set = set()


def register_ws(ws) -> None:
    _ws_connections.add(ws)


def unregister_ws(ws) -> None:
    _ws_connections.discard(ws)


async def broadcast_alert(payload: dict) -> None:
    """Broadcast a real-time alert JSON to all connected WebSocket clients."""
    msg = json.dumps(payload)
    dead = set()
    for ws in _ws_connections:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    for ws in dead:
        _ws_connections.discard(ws)


async def init_db() -> None:
    """Initialize the SQLite compliance log database."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS compliance_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                clip_id TEXT NOT NULL,
                zone TEXT NOT NULL,
                behavior_class TEXT NOT NULL,
                class_id INTEGER NOT NULL,
                policy_section TEXT NOT NULL,
                event_description TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence REAL,
                escalation_action TEXT NOT NULL,
                severity_rationale TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def log_to_db(record: dict) -> None:
    """Write a structured violation record to the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO compliance_events (
                event_id, timestamp, clip_id, zone, behavior_class, class_id,
                policy_section, event_description, severity, confidence,
                escalation_action, severity_rationale
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["event_id"],
            record["timestamp"],
            record["clip_id"],
            record.get("zone", "Zone-Unknown"),
            record["behavior_class"],
            record.get("class_id", -1),
            record.get("policy_section", "Unknown"),
            record.get("description", record.get("event_description", "")),
            record["severity"],
            record.get("confidence", 0.0),
            record.get("escalation_action", "Logged to DB"),
            record.get("severity_rationale", ""),
        ))
        await db.commit()


async def escalate(record: dict) -> dict:
    """
    Execute escalation routing for a single violation record.

    LOW/MEDIUM → DB log only
    HIGH/CRITICAL → real-time WebSocket alert + DB log

    Returns record augmented with escalation_action field.
    """
    severity = record.get("severity", "LOW")

    if severity in ("HIGH", "CRITICAL"):
        action = "Real-time alert triggered + DB log"
        # Broadcast to all live dashboard WebSocket connections
        await broadcast_alert({
            "type": "VIOLATION_ALERT",
            "severity": severity,
            "event_id": record["event_id"],
            "clip_id": record["clip_id"],
            "behavior_class": record["behavior_class"],
            "zone": record.get("zone", "Zone-Unknown"),
            "description": record.get("description", ""),
            "timestamp": record["timestamp"],
            "confidence": record.get("confidence", 0.0),
        })
    else:
        action = "Logged to DB"

    augmented = {**record, "escalation_action": action}
    await log_to_db(augmented)
    return augmented


async def escalate_batch(records: list[dict]) -> list[dict]:
    """Escalate a batch of violation records. Handles multi-severity clips correctly."""
    results = []
    for record in records:
        result = await escalate(record)
        results.append(result)
    return results


async def get_all_events(
    severity: str | None = None,
    behavior_class: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 500,
) -> list[dict]:
    """Query compliance events from DB with optional filters."""
    clauses = []
    params = []

    if severity:
        clauses.append("severity = ?")
        params.append(severity)
    if behavior_class:
        clauses.append("behavior_class = ?")
        params.append(behavior_class)
    if date_from:
        clauses.append("timestamp >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("timestamp <= ?")
        params.append(date_to)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT * FROM compliance_events {where} ORDER BY timestamp DESC LIMIT ?",
            params
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
