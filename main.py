"""
Factory Compliance & Alert Escalation System — Backend API
FastAPI application wiring all 5 modules together.

Endpoints:
  POST /api/process-clip      — Upload + process a video clip (Modules 1-4)
  GET  /api/events            — Query compliance log (Module 4/5)
  GET  /api/export/csv        — Download CSV audit log (Module 5 View C)
  GET  /api/export/json       — Download JSON audit log (Module 5 View C)
  GET  /api/policy-rules      — Return parsed policy rules
  GET  /api/stats             — Dashboard summary stats
  WS   /ws/alerts             — WebSocket for real-time alerts (Module 3/5)
"""

import os
import sys
import json
import asyncio
import tempfile
import traceback
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.detection.engine import process_video_clip
from src.detection.policy_parser import parse_policy_with_gemini
from src.severity.categorizer import assign_severity_batch
from src.escalation.pipeline import (
    escalate_batch, init_db, get_all_events,
    register_ws, unregister_ws
)
from src.reports.generator import write_reports_batch, export_csv_bytes, read_json_log

POLICY_PDF = str(Path(__file__).parent / "compliance_policy.pdf")

app = FastAPI(title="Factory Compliance System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve built React dashboard if it exists
DASHBOARD_DIST = Path(__file__).parent / "src" / "dashboard" / "dist"
if DASHBOARD_DIST.exists():
    app.mount("/app", StaticFiles(directory=str(DASHBOARD_DIST), html=True), name="dashboard")


@app.on_event("startup")
async def startup():
    await init_db()
    # Pre-parse policy rules on startup (cached after first run)
    try:
        parse_policy_with_gemini(POLICY_PDF)
        print("✅ Policy rules loaded.")
    except Exception as e:
        print(f"⚠️  Policy parsing deferred: {e}")


# ── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    """WebSocket endpoint for real-time HIGH/CRITICAL alert streaming (Module 3)."""
    await websocket.accept()
    register_ws(websocket)
    try:
        while True:
            # Keep connection alive; server pushes alerts via broadcast_alert()
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        pass
    finally:
        unregister_ws(websocket)


# ── Core Processing ────────────────────────────────────────────────────────────

@app.post("/api/process-clip")
async def process_clip(file: UploadFile = File(...)):
    """
    Upload a video clip and run the full compliance pipeline (Modules 1-4).
    Returns all generated violation records.
    """
    # Save upload to temp file
    suffix = Path(file.filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        clip_id = Path(file.filename).stem

        # Module 1: Detection
        rules = parse_policy_with_gemini(POLICY_PDF)
        detections = process_video_clip(tmp_path, clip_id=clip_id, rules=rules)

        if not detections:
            return JSONResponse({
                "clip_id": clip_id,
                "violations_found": 0,
                "records": [],
                "message": "No compliance violations detected in this clip."
            })

        # Module 2: Severity
        categorized = assign_severity_batch(detections)

        # Module 3: Escalation (DB log + WebSocket alerts for HIGH/CRITICAL)
        escalated = await escalate_batch(categorized)

        # Module 4: Report generation
        reports = write_reports_batch(escalated)

        return JSONResponse({
            "clip_id": clip_id,
            "violations_found": len(reports),
            "records": reports,
        })

    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        os.unlink(tmp_path)


# ── Query & Export ─────────────────────────────────────────────────────────────

@app.get("/api/events")
async def get_events(
    severity: str | None = Query(None),
    behavior_class: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int = Query(200),
):
    """Query compliance events with optional filters (Module 5 View C)."""
    events = await get_all_events(
        severity=severity,
        behavior_class=behavior_class,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return JSONResponse({"events": events, "total": len(events)})


@app.get("/api/export/csv")
async def export_csv(
    severity: str | None = Query(None),
    behavior_class: str | None = Query(None),
):
    """Download filtered compliance log as CSV (Module 5 View C export)."""
    events = await get_all_events(severity=severity, behavior_class=behavior_class, limit=10000)
    csv_bytes = export_csv_bytes(events)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=compliance_log.csv"}
    )


@app.get("/api/export/json")
async def export_json_log(
    severity: str | None = Query(None),
    behavior_class: str | None = Query(None),
):
    """Download compliance log as JSON (Module 5 View C export)."""
    events = await get_all_events(severity=severity, behavior_class=behavior_class, limit=10000)
    return Response(
        content=json.dumps(events, indent=2).encode(),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=compliance_log.json"}
    )


@app.get("/api/policy-rules")
async def get_policy_rules():
    """Return parsed policy rules (for dashboard reference)."""
    try:
        rules = parse_policy_with_gemini(POLICY_PDF)
        return JSONResponse(rules)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/stats")
async def get_stats():
    """Return summary statistics for the dashboard."""
    all_events = await get_all_events(limit=10000)
    total = len(all_events)
    by_severity = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    by_class: dict[str, int] = {}
    for e in all_events:
        sev = e.get("severity", "LOW")
        if sev in by_severity:
            by_severity[sev] += 1
        bc = e.get("behavior_class", "Unknown")
        by_class[bc] = by_class.get(bc, 0) + 1

    return JSONResponse({
        "total_events": total,
        "by_severity": by_severity,
        "by_behavior_class": by_class,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    })


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Factory Compliance System"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
