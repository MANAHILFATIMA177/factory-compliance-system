"""
Module 1: Detection Engine
Ingests video clips and identifies behavioral compliance violations
using Google Gemini Vision (FREE) grounded in policy-extracted rules.
"""

import uuid
import json
import re
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import google.generativeai as genai
from PIL import Image
import io
from dotenv import load_dotenv

from .policy_parser import parse_policy_with_gemini, get_behavior_class_by_id

load_dotenv()

POLICY_PDF_PATH = str(Path(__file__).parent.parent.parent / "compliance_policy.pdf")
MAX_FRAMES_PER_CLIP = 6


def extract_frames(video_path: str, max_frames: int = MAX_FRAMES_PER_CLIP) -> list[tuple[float, bytes]]:
    """Extract evenly-spaced frames from a video clip."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    if total_frames <= max_frames:
        frame_indices = list(range(total_frames))
    else:
        step = total_frames / max_frames
        frame_indices = [int(i * step) for i in range(max_frames)]

    frames = []
    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        timestamp = idx / fps
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        w, h = pil_img.size
        if w > 1280:
            pil_img = pil_img.resize((1280, int(h * 1280 / w)), Image.LANCZOS)
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=85)
        frames.append((timestamp, buf.getvalue()))

    cap.release()
    return frames


def build_detection_prompt(rules: dict) -> str:
    """Build a grounded detection prompt from extracted policy rules."""
    classes_desc = ""
    for bc in rules.get("behavior_classes", []):
        classes_desc += f"""
CLASS {bc['class_id']} — {bc['domain']}
  Unsafe behavior: {bc['unsafe_behavior']}
  Observable indicator of UNSAFE: {bc['observable_indicator_unsafe']}
  Policy section: {bc['policy_section']}
"""
    return f"""You are a factory compliance detection AI analyzing surveillance camera footage.

COMPLIANCE RULES (from policy KMP-OHS-POL-001):
{classes_desc}

Examine this image carefully. For each of the 4 compliance classes, determine if an UNSAFE behavior is visible.

Return ONLY a valid JSON object (no markdown, no backticks) with this schema:
{{
  "violations": [
    {{
      "class_id": 0,
      "behavior_class": "Safe Walkway Violation",
      "detected": true,
      "confidence": 0.85,
      "description": "A person is standing outside the green floor markings near machinery",
      "zone": "Zone-1",
      "policy_section": "Section 3.3.2",
      "observable_evidence": "Person visible outside green painted boundary lines"
    }}
  ],
  "frame_summary": "Brief description of what is visible in this frame"
}}

Rules:
- Only include entries where detected=true
- If nothing unsafe is visible return empty violations array
- Zones: Zone-1 (left), Zone-2 (center), Zone-3 (right), Zone-Unknown (unclear)
- Confidence: 0.0 to 1.0 — only flag if confidence >= 0.60
"""


def analyze_frame_with_gemini(model, frame_bytes: bytes, prompt: str) -> dict:
    """Send a single frame to Gemini Vision for compliance analysis."""
    pil_image = Image.open(io.BytesIO(frame_bytes))
    response = model.generate_content([prompt, pil_image])
    raw = response.text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def process_video_clip(
    video_path: str,
    clip_id: Optional[str] = None,
    rules: Optional[dict] = None
) -> list[dict]:
    """
    Full detection pipeline for a single video clip.
    Returns list of detection records (one per unique violation class per clip).
    """
    if rules is None:
        rules = parse_policy_with_gemini(POLICY_PDF_PATH)

    if clip_id is None:
        clip_id = Path(video_path).stem

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env file")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = build_detection_prompt(rules)
    frames = extract_frames(video_path)
    if not frames:
        return []

    # Track best detection per class_id
    best_detections: dict[int, dict] = {}

    for timestamp, frame_bytes in frames:
        try:
            result = analyze_frame_with_gemini(model, frame_bytes, prompt)
        except Exception as e:
            print(f"Frame analysis error at t={timestamp:.1f}s: {e}")
            continue

        for v in result.get("violations", []):
            if not v.get("detected", False):
                continue
            cid = v.get("class_id", -1)
            conf = v.get("confidence", 0.0)

            if cid not in best_detections or conf > best_detections[cid]["confidence"]:
                bc_info = get_behavior_class_by_id(rules, cid)
                best_detections[cid] = {
                    "event_id": str(uuid.uuid4()),
                    "clip_id": clip_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "frame_timestamp_sec": round(timestamp, 2),
                    "class_id": cid,
                    "behavior_class": v.get("behavior_class", "Unknown"),
                    "policy_section": v.get("policy_section", bc_info["policy_section"] if bc_info else "Unknown"),
                    "description": v.get("description", ""),
                    "zone": v.get("zone", "Zone-Unknown"),
                    "confidence": conf,
                    "observable_evidence": v.get("observable_evidence", ""),
                    "severity_signal": bc_info["severity_signal"] if bc_info else "WARNING",
                    "frame_summary": result.get("frame_summary", ""),
                }

    return list(best_detections.values())
