<div align="center">

# 🏭 Factory Compliance & Alert Escalation System

### AI-Powered Real-Time Safety Monitoring for Industrial Environments

[![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![Gemini AI](https://img.shields.io/badge/Gemini-1.5_Flash-4285F4?style=for-the-badge&logo=google)](https://aistudio.google.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

> **Genesys AI Internship Assessment Submission**  
> Policy Reference: `KMP-OHS-POL-001` — Kafaoglu Metal Plastik Makine San. ve Tic. A.Ş.

[Features](#-features) • [Architecture](#-architecture) • [Setup](#-setup--installation) • [Usage](#-usage) • [API](#-api-reference) • [Dashboard](#-dashboard-preview)

</div>

---

##  Project Overview

This system is a complete, production-ready **Factory Compliance & Alert Escalation System** that bridges three critical domains:

| Domain | Technology | Purpose |
|--------|-----------|---------|
| **Computer Vision** | Google Gemini 1.5 Flash | Detect violations in video frames |
|  **NLP / Document AI** | Gemini + PyMuPDF | Parse OHS policy PDF into structured rules |
|  **Real-time Workflow** | FastAPI + WebSocket | Route alerts based on risk severity |

The system automatically monitors factory video footage, cross-references observed behavior against a formal OHS Compliance Policy Manual, and triggers real-time alerts — all without any manual intervention.

---

##  Features

-  **Video Ingestion** — Upload any factory video clip for instant compliance analysis
- **AI Policy Parsing** — Automatically extracts compliance rules from PDF using Gemini AI
-  **Zero-Shot Detection** — Detects violations without any labeled training data
-  **Real-Time Alerts** — WebSocket-powered live alerts for HIGH/CRITICAL violations
- **Severity Classification** — 4-tier risk system (LOW → MEDIUM → HIGH → CRITICAL)
-  **Automated Reports** — Immutable compliance records in JSON + CSV + SQLite
- **Live Dashboard** — Real-time operations center with 3 functional views
-  **Export Ready** — Download filtered audit logs in CSV or JSON format

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPLIANCE PIPELINE                          │
│                                                                 │
│  📹 Video Clip                                                  │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐   │
│  │  MODULE 1   │    │   MODULE 2   │    │    MODULE 3     │   │
│  │  Detection  │───▶│  Severity    │───▶│   Escalation    │   │
│  │   Engine    │    │  Matrix      │    │   Pipeline      │   │
│  └─────────────┘    └──────────────┘    └─────────────────┘   │
│       │                    │                     │              │
│  Gemini Vision        LOW/MED/HIGH/         WebSocket +        │
│  + Policy Rules        CRITICAL             DB Logging         │
│                                                 │              │
│                                    ┌────────────┘              │
│                                    ▼                           │
│                           ┌─────────────────┐                 │
│                           │    MODULE 4     │                 │
│                           │ Report Generator│                 │
│                           └─────────────────┘                 │
│                                    │                           │
│                           JSON + CSV + SQLite                  │
│                                    │                           │
│                                    ▼                           │
│                           ┌─────────────────┐                 │
│                           │    MODULE 5     │                 │
│                           │   Dashboard     │                 │
│                           └─────────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
```

### 📁 Project Structure

```
factory-compliance-system/
├── 📄 main.py                        # FastAPI backend + WebSocket server
├── 📋 compliance_policy.pdf          # OHS Policy Manual (source of truth)
├── 📦 requirements.txt               # Python dependencies
├── 🔧 .env.example                   # Environment variables template
│
├── 📁 src/
│   ├── 📁 detection/
│   │   ├── policy_parser.py          # MODULE 1a: PDF → structured rules (Gemini AI)
│   │   └── engine.py                 # MODULE 1b: Video → violation detection
│   ├── 📁 severity/
│   │   └── categorizer.py            # MODULE 2: Risk tier assignment
│   ├── 📁 escalation/
│   │   └── pipeline.py               # MODULE 3: Alert routing + DB logging
│   ├── 📁 reports/
│   │   └── generator.py              # MODULE 4: Compliance report generation
│   └── 📁 dashboard/
│       └── index.html                # MODULE 5: Live operations dashboard
│
├── 📁 data/                          # Input video clips
├── 📁 outputs/                       # Generated reports & database
│   ├── compliance_log.db             # SQLite audit database
│   ├── compliance_log.json           # Append-only JSON log
│   └── compliance_log.csv            # Append-only CSV audit trail
└── 📁 config/
    └── policy_rules.json             # Cached parsed policy rules
```

---

## 🔬 Module Design

### Module 1 — Detection Engine

The detection pipeline operates in two stages:

**Stage A — Policy Parsing**
- Extracts full text from `compliance_policy.pdf` using PyMuPDF
- Sends text to Gemini AI with a structured extraction prompt
- Returns all 4 behavior classes with observable indicators, policy section references, and severity signals
- Caches result in `config/policy_rules.json` — no repeated API calls

**Stage B — Video Analysis**
- Extracts up to 6 evenly-spaced frames per clip using OpenCV
- Builds detection prompt **grounded in policy-extracted rules** (not hard-coded strings)
- Sends each frame to Gemini Vision API for compliance analysis
- Only flags violations with confidence ≥ 0.60
- Keeps highest-confidence detection per behavior class per clip

**Why Gemini Vision over fine-tuned detectors?**
> The 4 compliance classes require semantic understanding — vest color, floor marking boundaries, block counts, panel states — not just bounding boxes. Zero-shot capability eliminates the need for a labeled training dataset, and detection logic stays grounded in policy text.

---

### Module 2 — Severity Categorization Matrix

Severity tiers are **directly grounded in policy callout language**:

| Class | Behavior | Policy Callout | Max Severity |
|-------|----------|---------------|-------------|
| 0 | Safe Walkway Violation | `⚠️ WARNING` § 3.3.2 | **HIGH** |
| 1 | Unauthorized Intervention | `🚨 CRITICAL SAFETY NOTICE` § 4.3.2 | **CRITICAL** |
| 2 | Opened Panel Cover | `⚠️ WARNING` § 5.2.2 | **HIGH** |
| 3 | Carrying Overload with Forklift | `🚨 CRITICAL SAFETY NOTICE` § 6.3.2 | **CRITICAL** |

**Confidence modulation** (within policy-set ceiling):

```
confidence ≥ 0.85  →  Max tier (e.g. CRITICAL)
confidence ≥ 0.70  →  One tier below max (e.g. HIGH)
confidence < 0.70  →  Two tiers below max (e.g. MEDIUM)
```

---

### Module 3 — Escalation Pipeline

```
Severity        →    Action
─────────────────────────────────────────────────────
LOW / MEDIUM    →    Persistent DB log only
HIGH / CRITICAL →    🚨 WebSocket alert + DB log
```

Real-time alerts are broadcast via WebSocket to all connected dashboard clients instantly upon detection.

---

### Module 4 — Automated Report Generation

Every detected violation generates an immutable record written simultaneously to:
- `outputs/compliance_log.db` — SQLite (primary queryable store)
- `outputs/compliance_log.json` — Append-only JSON log
- `outputs/compliance_log.csv` — Append-only CSV audit trail

**Required fields:** `event_id` · `timestamp` · `clip_id` · `zone` · `behavior_class` · `policy_rule_ref` · `event_description` · `severity` · `escalation_action`

---

### Module 5 — Operations Dashboard

Single-file HTML dashboard with no build step required.

| View | Description |
|------|-------------|
| **Live Feed Monitor** | Drag-drop video upload, real-time processing results with severity color coding |
|  **Alert Timeline** | Chronological stream of all events, filterable by severity & behavior class |
|  **Historical Log** | Full audit log with date range filters + CSV/JSON export |
|  **Policy Rules** | Displays AI-extracted compliance rules from the policy document |

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.10+
- Google Gemini API Key — **completely FREE** at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

### 1. Clone the Repository

```bash
git clone https://github.com/MANAHILFATIMA177/factory-compliance-system.git
cd factory-compliance-system
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Open `.env` and add your Gemini API key:

```env
GEMINI_API_KEY=your-gemini-api-key-here
```

### 4. Add Video Clips

Place factory video clips in the `data/` directory:

```
data/
├── walkway_violation_01.mp4
├── unauthorized_intervention_01.mp4
├── panel_cover_open_01.mp4
└── forklift_overload_01.mp4
```

> 📥 Dataset: [Video Dataset for Safe and Unsafe Behaviours](https://www.kaggle.com/datasets/trnhhnggiang/videodataset-for-safe-and-unsafe-behaviours)

### 5. Run the System

```bash
py main.py
```

Backend starts at `http://localhost:8000` 

### 6. Open Dashboard

Open `src/dashboard/index.html` in your browser and start uploading video clips!

---

##  API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/process-clip` | Upload + analyze a video clip |
| `GET` | `/api/events` | Query compliance log (filterable) |
| `GET` | `/api/export/csv` | Download audit log as CSV |
| `GET` | `/api/export/json` | Download audit log as JSON |
| `GET` | `/api/policy-rules` | Get AI-parsed policy rules |
| `GET` | `/api/stats` | Dashboard summary statistics |
| `WS` | `/ws/alerts` | WebSocket for real-time alerts |

### Example: Process a Video Clip

```bash
curl -X POST http://localhost:8000/api/process-clip \
  -F "file=@data/my_clip.mp4"
```

### Example Response

```json
{
  "clip_id": "my_clip",
  "violations_found": 2,
  "records": [
    {
      "event_id": "a1b2c3d4-...",
      "timestamp": "2024-11-25T10:45:00Z",
      "clip_id": "my_clip",
      "zone": "Zone-2",
      "behavior_class": "Unauthorized Intervention",
      "policy_rule_ref": "Section 4.3.2",
      "event_description": "Person interacting with equipment without green authorization vest",
      "severity": "CRITICAL",
      "escalation_action": "Real-time alert triggered + DB log"
    }
  ]
}
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
|  AI / Vision | Google Gemini 1.5 Flash | Policy parsing + video analysis |
|  Video Processing | OpenCV | Frame extraction |
|  PDF Parsing | PyMuPDF | Policy document text extraction |
|  Backend | FastAPI + Uvicorn | REST API + WebSocket server |
| Database | SQLite + aiosqlite | Async compliance log storage |
| Real-time | WebSocket | Live alert broadcasting |
| Dashboard | HTML + Vanilla JS | No-build operations UI |
| Reports | JSON + CSV | Immutable audit trail |

---

## 📋 Compliance Behavior Classes

Defined in `KMP-OHS-POL-001`:

```
Class 0 — Pedestrian Movement
  Safe:   Person within green floor markings
  Unsafe: Person outside green floor markings (Safe Walkway Violation)

Class 1 — Equipment Interaction  
  Safe:   Person with green authorization vest
   Unsafe: Person without green vest touching equipment (Unauthorized Intervention)

Class 2 — Electrical Safety
 Safe:   Panel cover fully closed
Unsafe: Panel cover left open (Opened Panel Cover)

Class 3 — Forklift Load Management
  Safe:   Forklift carrying ≤ 2 blocks
 Unsafe: Forklift carrying ≥ 3 blocks (Carrying Overload)
```

---

## Acknowledgements

- Dataset: [Video Dataset for Safe and Unsafe Behaviours](https://www.kaggle.com/datasets/trnhhnggiang/videodataset-for-safe-and-unsafe-behaviours) by Trịnh Hương Giang
- Policy Document: KMP-OHS-POL-001 — Kafaoglu Metal Plastik Makine San. ve Tic. A.Ş.
- AI Model: Google Gemini 1.5 Flash

---

<div align="center">

**Submitted for Genesys AI Internship Assessment**  
Made  by Manahil Fatima

</div>
