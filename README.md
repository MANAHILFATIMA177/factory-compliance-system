# Factory Compliance & Alert Escalation System

**Assessment Submission — Genesys AI Internship**  
Policy Reference: `KMP-OHS-POL-001` — Kafaoglu Metal Plastik Makine San. ve Tic. A.Ş.

---

## Overview

An end-to-end automated factory compliance system that:
- Ingests raw factory video clips
- Parses the OHS Compliance Policy Manual (PDF) using Claude AI
- Detects behavioral violations frame-by-frame using Claude Vision
- Classifies each violation by severity (LOW / MEDIUM / HIGH / CRITICAL)
- Routes alerts via WebSocket (HIGH/CRITICAL) or DB log (LOW/MEDIUM)
- Auto-generates immutable compliance reports (JSON + CSV)
- Presents everything through a live operations dashboard

---

## Architecture

```
factory-compliance-system/
├── main.py                        # FastAPI backend (all API routes + WebSocket)
├── compliance_policy.pdf          # Authoritative OHS policy document
├── requirements.txt
├── .env.example
├── data/                          # Place input video clips here
├── outputs/                       # Auto-generated reports & DB
│   ├── compliance_log.db          # SQLite audit database
│   ├── compliance_log.json        # Append-only JSON report log
│   └── compliance_log.csv         # Append-only CSV audit log
├── config/
│   └── policy_rules.json          # Cached parsed policy rules (auto-generated)
└── src/
    ├── detection/
    │   ├── policy_parser.py       # MODULE 1 (support): PDF → structured rules via Claude
    │   └── engine.py              # MODULE 1: Video → violation detection via Claude Vision
    ├── severity/
    │   └── categorizer.py         # MODULE 2: Severity tier assignment
    ├── escalation/
    │   └── pipeline.py            # MODULE 3: DB logging + WebSocket alert routing
    ├── reports/
    │   └── generator.py           # MODULE 4: Immutable compliance report generation
    └── dashboard/
        └── index.html             # MODULE 5: Standalone HTML operations dashboard
```

---

## Module Design

### Module 1 — Detection Engine

**Policy Parsing (`policy_parser.py`)**  
Uses Claude (`claude-sonnet-4-6`) to parse `compliance_policy.pdf` into a structured JSON schema containing all 4 behavior classes, their observable indicators, policy section references, and severity signals. Result is cached in `config/policy_rules.json` to avoid repeated API calls.

**Video Detection (`engine.py`)**  
- Extracts up to 6 evenly-spaced frames per clip using OpenCV
- Sends each frame to Claude Vision API with a grounded prompt built from parsed policy rules
- Only flags violations with confidence ≥ 0.60
- Keeps highest-confidence detection per behavior class per clip
- Returns structured detection records

**Model Rationale:** Claude Vision (`claude-sonnet-4-6`) was chosen over fine-tuned object detectors because:
1. The 4 compliance classes require semantic understanding (vest color, floor marking boundaries, block counts, panel state) — not just bounding boxes
2. Zero-shot capability eliminates the need for a labeled training dataset
3. Detection logic stays grounded in policy text, not hard-coded strings

**Known Limitations:**
- Processing speed: ~10–30 seconds per clip (API latency)
- Very short clips (<1s) may yield no usable frames
- Low-light or heavily occluded frames may reduce confidence
- Borderline block counts (2 vs 3) on forklifts may produce uncertain results — system defaults to flagging when confidence ≥ 0.60 as per policy's unambiguous threshold language

---

### Module 2 — Severity Categorization Matrix

Severity is **grounded in policy callout language**:

| Class | Behavior | Policy Callout | Max Tier |
|-------|----------|---------------|----------|
| 0 | Safe Walkway Violation | `WARNING` (Section 3.3.2) | HIGH |
| 1 | Unauthorized Intervention | `CRITICAL SAFETY NOTICE` (Section 4.3.2) | CRITICAL |
| 2 | Opened Panel Cover | `WARNING` (Section 5.2.2) | HIGH |
| 3 | Carrying Overload with Forklift | `CRITICAL SAFETY NOTICE` (Section 6.3.2) | CRITICAL |

**Confidence modulation** (within policy-set ceiling):
- confidence ≥ 0.85 → max tier for that class
- 0.70 ≤ confidence < 0.85 → one tier below max
- confidence < 0.70 → two tiers below max

**Multi-violation handling:** Each violation in a clip is escalated independently. The highest-severity event in a clip triggers the real-time alert.

---

### Module 3 — Escalation Pipeline

| Severity | Route |
|----------|-------|
| LOW / MEDIUM | Persistent DB log only |
| HIGH / CRITICAL | WebSocket broadcast → dashboard alert + DB log |

Real-time alerts are pushed via WebSocket (`/ws/alerts`) to all connected dashboard clients. The dashboard renders a flashing red banner and plays an alert animation for HIGH/CRITICAL events.

---

### Module 4 — Automated Report Generation

Every detected violation auto-generates a record written to:
- `outputs/compliance_log.db` (SQLite — primary queryable store)
- `outputs/compliance_log.json` (append-only JSON log)
- `outputs/compliance_log.csv` (append-only CSV audit trail)

**Required fields per report:**
`event_id` · `timestamp` · `clip_id` · `zone` · `behavior_class` · `policy_rule_ref` · `event_description` · `severity` · `escalation_action`

---

### Module 5 — Operations Dashboard

Single-file HTML dashboard (`src/dashboard/index.html`) — open directly in a browser while the backend runs.

**View A — Live Feed Monitor**  
Drag-and-drop video clip upload. Clips are processed through the full pipeline and results display inline with severity color coding and escalation status.

**View B — Alert Timeline Stream**  
Real-time chronological stream of all compliance events. Filterable by severity and behavior class. New events appear instantly via WebSocket.

**View C — Historical Log & Export**  
Full queryable audit log with filters for severity, behavior class, and date range. Export buttons download filtered results as CSV or JSON.

**Policy Rules Tab**  
Displays the structured rules extracted from the policy PDF — showing behavior classes, observable indicators, policy sections, and severity signals.

---

## Setup & Run Instructions

### 1. Prerequisites

- Python 3.10+
- An Gemini key

### 2. Clone & Install

```bash
git clone <your-repo-url>
cd factory-compliance-system

pip install -r requirements.txt
```

### 3. Configure API Key

```bash
cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY
```

Or export directly:
```bash
export GEMINI_API_KEY=your-gemini-api-key-here
```

### 4. Add Video Clips

Place your factory video clips in the `data/` directory:
```
data/
├── clip_001.mp4
├── clip_002.mp4
└── ...
```

Download the dataset from:  
https://www.kaggle.com/datasets/trnhhnggiang/videodataset-for-safe-and-unsafe-behaviours

### 5. Start the Backend

```bash
python main.py
# Backend runs at http://localhost:8000
```

On first startup, the system parses the compliance policy PDF and caches rules to `config/policy_rules.json`.

### 6. Open the Dashboard

Open `src/dashboard/index.html` in your browser — or navigate to:
```
http://localhost:8000
```

The dashboard connects automatically via WebSocket for live alerts.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/process-clip` | Upload + analyze a video clip |
| `GET` | `/api/events` | Query compliance log (filterable) |
| `GET` | `/api/export/csv` | Download audit log as CSV |
| `GET` | `/api/export/json` | Download audit log as JSON |
| `GET` | `/api/policy-rules` | Get parsed policy rules |
| `GET` | `/api/stats` | Dashboard summary statistics |
| `WS` | `/ws/alerts` | WebSocket for real-time alerts |

---

## Policy Parsing Approach

The compliance policy PDF is parsed by prompting Claude with the full document text and requesting a structured JSON extraction of all 4 behavior classes. The extraction includes:

- Behavior class name (safe and unsafe pair)
- Observable visual indicators (the primary detection signal)
- Policy section reference
- Severity callout language (WARNING vs CRITICAL SAFETY NOTICE)

**Faithfulness verification:** The parsed rules are cached as `config/policy_rules.json`. Reviewers can inspect this file to verify that extracted rules match the source document. The policy section references allow direct cross-checking against the PDF.

---

## Severity Mapping Rationale

The assignment specification states:
> *"Two of the four behavior categories appear in the compliance policy under a 'WARNING' callout and two appear under a 'CRITICAL SAFETY NOTICE' callout."*

From the policy:
- **WARNING** (Sections 3.3.2, 5.2.2) → maximum severity tier = **HIGH**
- **CRITICAL SAFETY NOTICE** (Sections 4.3.2, 6.3.2) → maximum severity tier = **CRITICAL**

Severity is further modulated downward based on detection confidence to avoid false alarms at maximum tier when the model is uncertain.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Vision & NLP | Google Gemini (`gemini-1.5-flash`) — FREE |
| Video processing | OpenCV (`opencv-python-headless`) |
| PDF parsing | PyMuPDF (`fitz`) |
| Backend | FastAPI + Uvicorn |
| Database | SQLite via `aiosqlite` |
| Real-time alerts | WebSocket (FastAPI native) |
| Dashboard | Vanilla HTML/JS (no build step) |
| Reports | JSON + CSV (stdlib) |

---

## License

Submitted for evaluation purposes only — Genesys AI Internship Assessment.
