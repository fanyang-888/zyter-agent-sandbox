"""
Agent 2 — Competitive Intelligence Brief (V1: Sequential / LCEL)

Input:  competitor name + optional deal context
Flow:
  SENSE  -> RAG retrieve Zyter battle cards + competitor notes
  THINK  -> Claude maps competitor capabilities vs Zyter Symphony/Praxis
  ACT    -> structured brief: Executive Summary | Where We Win | Where We Lose | Positioning
  LEARN  -> sales rep rates output, flags which sections were actually used

Same RAG knowledge base as RFP agent (shared universal collection).
"""

import os
from typing import TypedDict

import anthropic
from dotenv import load_dotenv
from langsmith import traceable

from app.agents.rag import retrieve, format_context

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-opus-4-5"


# ── Data shapes ──────────────────────────────────────────────────────────────

class CIInput(TypedDict):
    competitor_name: str       # e.g. "Cohere Health"
    deal_context: str          # optional: "Health plan RFP, 50k members, UM focus"
    user_id: str


class CIOutput(TypedDict):
    competitor: str
    executive_summary: str
    where_we_win: list[str]
    where_we_lose: list[str]
    recommended_positioning: str
    knowledge_sources: list[str]
    confidence: str            # "high" | "medium" | "low" based on source quality


# ── Step 1 — SENSE ───────────────────────────────────────────────────────────

@traceable(name="ci_sense")
def sense(competitor_name: str, deal_context: str) -> dict:
    """
    Retrieve from two collections:
    - universal: Zyter product docs, capability sheets, Symphony/Praxis specs
    - competitive_intel: battle cards, win/loss notes, analyst reports
    """
    query = f"{competitor_name} {deal_context}".strip()

    universal_docs = retrieve(query, collection_name="universal", k=5)
    ci_docs = retrieve(query, collection_name="competitive_intel", k=5)

    all_docs = universal_docs + ci_docs
    context = format_context(all_docs)
    sources = list({doc.metadata.get("source", "unknown") for doc in all_docs})

    return {
        "context": context,
        "sources": sources,
        "doc_count": len(all_docs),
    }


# ── Step 2 — THINK + ACT ─────────────────────────────────────────────────────

@traceable(name="ci_think_act")
def think_and_act(competitor_name: str, deal_context: str, context: str) -> dict:

    system_prompt = """You are a Zyter|TruCare competitive intelligence analyst.
You help sales reps prepare for deals by mapping Zyter's strengths and gaps vs. competitors.

Rules:
- Only make claims supported by the provided Zyter knowledge context.
- Be honest about weaknesses — sales reps need accurate intel, not cheerleading.
- "Where we win" must cite a specific Zyter capability (Symphony, Praxis module, etc.)
- "Where we lose" must be concrete and actionable, not vague.
- Recommended positioning must be one punchy message the rep can say on a call.
- Output valid JSON only. No markdown fences."""

    user_prompt = f"""=== ZYTER KNOWLEDGE BASE (retrieved) ===
{context}

=== COMPETITOR ===
{competitor_name}

=== DEAL CONTEXT ===
{deal_context if deal_context else "No specific deal context provided."}

=== TASK ===
Produce a competitive intelligence brief as JSON:
{{
  "executive_summary": "2-3 sentences: who the competitor is, how they compare to Zyter, and the bottom-line recommendation for this deal",
  "where_we_win": [
    "Specific Zyter advantage 1 (cite the capability)",
    "Specific Zyter advantage 2"
  ],
  "where_we_lose": [
    "Honest gap or weakness vs this competitor 1",
    "Honest gap or weakness vs this competitor 2"
  ],
  "recommended_positioning": "One sentence the sales rep can say on the call to frame Zyter's value vs this competitor",
  "confidence": "high | medium | low"
}}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    import json
    raw = response.content[0].text.strip()
    return json.loads(raw)


# ── Main entry point ──────────────────────────────────────────────────────────

@traceable(name="ci_agent_run")
def run(input_data: CIInput) -> CIOutput:
    sense_result = sense(input_data["competitor_name"], input_data.get("deal_context", ""))

    output = think_and_act(
        competitor_name=input_data["competitor_name"],
        deal_context=input_data.get("deal_context", ""),
        context=sense_result["context"],
    )

    output["competitor"] = input_data["competitor_name"]
    output["knowledge_sources"] = sense_result["sources"]
    return output


# ── Quick CLI test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = run({
        "competitor_name": "Cohere Health",
        "deal_context": "Medicare Advantage health plan, 100k members, prior authorization automation RFP",
        "user_id": "test_user",
    })

    print(f"=== COMPETITIVE BRIEF: {result['competitor']} ===")
    print(f"\nConfidence: {result['confidence'].upper()}")
    print(f"\nSummary:\n{result['executive_summary']}")
    print("\nWhere We WIN:")
    for w in result["where_we_win"]:
        print(f"  ✅ {w}")
    print("\nWhere We LOSE:")
    for l in result["where_we_lose"]:
        print(f"  ❌ {l}")
    print(f"\nPositioning:\n  💬 \"{result['recommended_positioning']}\"")
    print(f"\nSources: {result['knowledge_sources']}")
