"""
Agent 1 — RFI/RFP Assistant (V1: Sequential / LCEL)

Handles both RFI (Request for Information) and RFP (Request for Proposal):
  - RFI: describe Zyter capabilities in response to open-ended questions
  - RFP: map each stated requirement to Zyter's portfolio, flag gaps

Input:  raw RFI or RFP text (pasted or uploaded) + doc_type flag
Flow:
  SENSE  -> auto-route query across relevant collections (rfp_archive + universal)
  THINK  -> Claude responds grounded in Zyter knowledge, mode-aware
  ACT    -> structured draft with per-section confidence scores
  LEARN  -> captures user rating + edit flags for future retrieval tuning

This is V1 (sequential LCEL). V2 will add LangGraph conditional branching.
"""

import os
from typing import TypedDict

import anthropic
from dotenv import load_dotenv
from langsmith import traceable

from app.agents.rag import retrieve_routed, format_context

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-opus-4-5"


# ── Data shapes ──────────────────────────────────────────────────────────────

class RFPInput(TypedDict):
    rfp_text: str          # raw RFI or RFP content pasted by user
    user_id: str           # for per-user output history
    doc_type: str          # "rfi" | "rfp" — defaults to "rfp" if omitted


class RFPSection(TypedDict):
    section_title: str
    draft_response: str
    confidence: str        # "high" | "medium" | "low"
    flag_for_review: bool


class RFPOutput(TypedDict):
    summary: str
    sections: list[RFPSection]
    gaps: list[str]        # requirements no Zyter module covers
    knowledge_sources: list[str]


# ── Step 1 — SENSE: parse + retrieve ─────────────────────────────────────────

@traceable(name="rfp_sense")
def sense(rfp_text: str) -> dict:
    """
    Auto-routes the query to relevant collections (rfp_archive + universal)
    using retrieve_routed() — no hardcoded collection names.
    """
    all_docs = retrieve_routed(rfp_text, k=8)
    context = format_context(all_docs)
    sources = list({doc.metadata.get("source", "unknown") for doc in all_docs})

    return {
        "context": context,
        "sources": sources,
        "doc_count": len(all_docs),
    }


# ── Step 2 — THINK + ACT: Claude maps requirements → draft ───────────────────

@traceable(name="rfp_think_act")
def think_and_act(rfp_text: str, context: str, doc_type: str = "rfp") -> RFPOutput:
    """
    Claude reads the RFI/RFP + retrieved Zyter knowledge and produces:
    - Per-section draft responses with confidence scores
    - Gap list (requirements not covered by Zyter)

    doc_type controls the mode:
      "rfi" → describe capabilities in response to open-ended questions
      "rfp" → map stated requirements to Zyter portfolio, flag gaps
    """

    mode_instruction = {
        "rfi": (
            "This is an RFI (Request for Information). "
            "The prospect is asking open-ended questions about Zyter's capabilities. "
            "Focus on clearly describing what Zyter can do, with specific product references. "
            "Be factual and honest — if a capability is partial, say so."
        ),
        "rfp": (
            "This is an RFP (Request for Proposal). "
            "The prospect has stated specific requirements. "
            "Map each requirement to Zyter's product capabilities. "
            "Flag gaps where no module covers the ask — do not fabricate coverage."
        ),
    }.get(doc_type, "rfp")

    system_prompt = f"""You are a Zyter|TruCare Sales Engineering assistant.
{mode_instruction}

Rules (apply to both RFI and RFP):
- Only make claims you can support from the provided Zyter knowledge context.
- Assign confidence: "high" if well-supported by context, "medium" if partial, "low" if thin.
- flag_for_review must be true for any section with confidence "low".
- Be concise. Sales engineers will edit this, not send it verbatim.
- Output valid JSON only. No markdown fences."""

    doc_label = "RFI" if doc_type == "rfi" else "RFP"
    user_prompt = f"""=== ZYTER KNOWLEDGE BASE (retrieved) ===
{context}

=== INCOMING {doc_label} ===
{rfp_text}

=== TASK ===
Analyze this {doc_label} and produce a JSON response with this exact structure:
{{
  "summary": "2-3 sentence overview of what this {doc_label} is asking for and Zyter's fit",
  "sections": [
    {{
      "section_title": "question or requirement from the {doc_label}",
      "draft_response": "draft answer grounded in Zyter capabilities",
      "confidence": "high | medium | low",
      "flag_for_review": true | false
    }}
  ],
  "gaps": ["capability or requirement not covered by Zyter"]
}}

Identify every distinct question or requirement. Each becomes one section."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    import json
    raw = response.content[0].text.strip()
    return json.loads(raw)


# ── Step 3 — LEARN: capture feedback ─────────────────────────────────────────

def capture_feedback(user_id: str, rating: int, edited_sections: list[str]):
    """
    Stub for Sprint 1. In MVP this writes to RDS and adjusts retrieval weights.
    For now: appends to a local JSONL file for later analysis.
    """
    import json
    from datetime import datetime

    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "agent": "rfp_agent",
        "rating": rating,
        "edited_sections": edited_sections,
    }

    os.makedirs("user_data", exist_ok=True)
    with open(f"user_data/{user_id}_feedback.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


# ── Main entry point ──────────────────────────────────────────────────────────

@traceable(name="rfp_agent_run")
def run(input_data: RFPInput) -> RFPOutput:
    """
    Full SENSE → THINK → ACT pipeline for RFI/RFP agent.
    Call this from FastAPI or directly for testing.

    doc_type defaults to "rfp" for backward compatibility.
    """
    doc_type = input_data.get("doc_type", "rfp")
    sense_result = sense(input_data["rfp_text"])

    output = think_and_act(
        rfp_text=input_data["rfp_text"],
        context=sense_result["context"],
        doc_type=doc_type,
    )

    output["knowledge_sources"] = sense_result["sources"]
    return output


# ── Quick CLI test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample_rfp = """
    We are seeking a Care Management platform with the following capabilities:
    1. Automated prior authorization workflow for Medicare Advantage members
    2. Integration with Epic EHR for patient data ingestion
    3. Real-time clinical decision support during care manager workflows
    4. HIPAA-compliant data storage and audit logging
    5. SSO integration with Azure Active Directory
    6. Reporting dashboard for utilization metrics by care manager
    """

    result = run({"rfp_text": sample_rfp, "user_id": "test_user"})

    print("=== SUMMARY ===")
    print(result["summary"])
    print("\n=== SECTIONS ===")
    for s in result["sections"]:
        flag = " ⚠️  REVIEW REQUIRED" if s["flag_for_review"] else ""
        print(f"\n[{s['confidence'].upper()}] {s['section_title']}{flag}")
        print(s["draft_response"])
    if result["gaps"]:
        print("\n=== GAPS (no Zyter coverage) ===")
        for g in result["gaps"]:
            print(f"  - {g}")
