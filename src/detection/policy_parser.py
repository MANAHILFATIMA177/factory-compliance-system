"""
Module 1 (support): Policy Parser
Extracts compliance rules from the OHS Policy Manual PDF using Google Gemini (FREE).
Rules are cached after first parse to avoid repeated API calls.
"""

import json
import re
import os
import fitz  # PyMuPDF
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

POLICY_RULES_CACHE_PATH = Path(__file__).parent.parent.parent / "config" / "policy_rules.json"


def extract_pdf_text(pdf_path: str) -> str:
    """Extract full text from PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def parse_policy_with_gemini(pdf_path: str, force_refresh: bool = False) -> dict:
    """
    Use Gemini to extract structured compliance rules from the policy PDF.
    Caches result to config/policy_rules.json after first run.
    """
    POLICY_RULES_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not force_refresh and POLICY_RULES_CACHE_PATH.exists():
        with open(POLICY_RULES_CACHE_PATH) as f:
            return json.load(f)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env file")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    policy_text = extract_pdf_text(pdf_path)

    prompt = f"""You are a compliance rule extraction system. Analyze this Occupational Health & Safety Policy Manual.

Return ONLY a valid JSON object (no markdown, no backticks, no preamble) with this exact schema:
{{
  "behavior_classes": [
    {{
      "class_id": 0,
      "domain": "Pedestrian Movement",
      "unsafe_behavior": "Safe Walkway Violation",
      "safe_behavior": "Safe Walkway",
      "policy_section": "Section 3.3.2",
      "observable_indicator_unsafe": "Person outside green floor markings",
      "observable_indicator_safe": "Person within green floor markings",
      "severity_signal": "WARNING",
      "severity_rationale": "Highest-frequency unsafe behavior; places person near forklift/machinery hazards",
      "suggested_severity_tier": "HIGH",
      "detection_keywords": ["walkway", "green marking", "outside boundary"]
    }}
  ],
  "facility_info": {{
    "company": "Kafaoglu Metal Plastik Makine San. ve Tic. A.S.",
    "document_no": "KMP-OHS-POL-001",
    "effective_date": "01 November 2022"
  }},
  "severity_mapping": {{
    "CRITICAL SAFETY NOTICE": "CRITICAL",
    "WARNING": "HIGH"
  }}
}}

Extract all 4 behavior classes (class_id 0-3):
0 = Pedestrian Walkway (Section 3)
1 = Equipment Intervention (Section 4)
2 = Electrical Panel Cover (Section 5)
3 = Forklift Load Management (Section 6)

For severity_signal use exact callout from policy: WARNING or CRITICAL SAFETY NOTICE
For suggested_severity_tier use: LOW, MEDIUM, HIGH, or CRITICAL

POLICY DOCUMENT:
{policy_text}
"""

    response = model.generate_content(prompt)
    raw = response.text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    rules = json.loads(raw)

    with open(POLICY_RULES_CACHE_PATH, "w") as f:
        json.dump(rules, f, indent=2)

    return rules


def get_behavior_class_by_id(rules: dict, class_id: int) -> dict | None:
    for bc in rules.get("behavior_classes", []):
        if bc["class_id"] == class_id:
            return bc
    return None


if __name__ == "__main__":
    pdf = str(Path(__file__).parent.parent.parent / "compliance_policy.pdf")
    rules = parse_policy_with_gemini(pdf, force_refresh=True)
    print(json.dumps(rules, indent=2))
