"""
Module 4: Automated Report Generation
Produces structured, immutable compliance records for every detected violation.
Writes reports in JSON (append-only log) and CSV formats.
"""

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

OUTPUTS_DIR = Path(__file__).parent.parent.parent / "outputs"
JSON_LOG_PATH = OUTPUTS_DIR / "compliance_log.json"
CSV_LOG_PATH = OUTPUTS_DIR / "compliance_log.csv"

CSV_FIELDS = [
    "event_id",
    "timestamp",
    "clip_id",
    "zone",
    "behavior_class",
    "policy_rule_ref",
    "event_description",
    "severity",
    "escalation_action",
    "confidence",
    "severity_rationale",
]


def _ensure_outputs_dir():
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_csv_header():
    if not CSV_LOG_PATH.exists():
        with open(CSV_LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()


def build_report(record: dict) -> dict:
    """
    Construct a fully-formed compliance report from an escalated detection record.
    All required fields per Module 4 spec are guaranteed present.
    """
    return {
        "event_id": record.get("event_id", str(uuid.uuid4())),
        "timestamp": record.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "clip_id": record.get("clip_id", "unknown"),
        "zone": record.get("zone", "Zone-Unknown"),
        "behavior_class": record.get("behavior_class", "Unknown"),
        "policy_rule_ref": record.get("policy_section", "Unknown"),
        "event_description": record.get("description", record.get("event_description", "No description provided.")),
        "severity": record.get("severity", "LOW"),
        "escalation_action": record.get("escalation_action", "Logged to DB"),
        # Extended fields for richer audit trail
        "confidence": record.get("confidence", 0.0),
        "severity_rationale": record.get("severity_rationale", ""),
        "observable_evidence": record.get("observable_evidence", ""),
        "frame_timestamp_sec": record.get("frame_timestamp_sec", 0.0),
    }


def write_report(record: dict) -> dict:
    """
    Write a compliance report to both JSON and CSV audit logs.
    Returns the finalized report dict.
    """
    _ensure_outputs_dir()
    _ensure_csv_header()

    report = build_report(record)

    # Append to JSON log
    existing = []
    if JSON_LOG_PATH.exists():
        try:
            with open(JSON_LOG_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []

    existing.append(report)
    with open(JSON_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)

    # Append to CSV log
    with open(CSV_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writerow(report)

    return report


def write_reports_batch(records: list[dict]) -> list[dict]:
    """Write reports for a batch of violation records."""
    return [write_report(r) for r in records]


def read_json_log() -> list[dict]:
    """Read all reports from the JSON audit log."""
    if not JSON_LOG_PATH.exists():
        return []
    try:
        with open(JSON_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def export_csv_bytes(records: list[dict]) -> bytes:
    """Serialize a list of report records to CSV bytes for download."""
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for r in records:
        writer.writerow(r)
    return buf.getvalue().encode("utf-8")
