"""
Agent 1 — RFI/RFP Assistant, V2 (LangGraph DAG with HITL interrupts)

Implements the team's RFP Technical Breakdown (Mel, 2026-06-11), Step 3 skeleton:
  graph skeleton [A]-[E],[G] + SQLite checkpointer + interrupt [D] + citation validator.

Why LangGraph (not the V1 LCEL in rfp_agent.py):
  The flow pauses for a human in two places (source confirmation, section review)
  and it branches (low-confidence / uncited sections route to review). LCEL cannot
  model interrupt-and-resume. Per the team's architecture checklist:
  "Does this workflow ever need to pause for a human? Yes -> LangGraph, no exceptions."

Graph:
  [A] parse        extract requirements from RFP
  [B] scope        classify intent, map each requirement to a portfolio area
  [C] retrieve     weighted candidate sources per requirement (reuses rag.py)
  == INTERRUPT ==
  [D] confirm      human approves/swaps/adds/rejects sources  <- interrupt_before
  [E] draft        per-section: content + citation + self-assessed confidence
  --- citation validator (code check) + confidence router ---
  == INTERRUPT (only if any section flagged) ==
  [F] review       human review/edit loop                     <- interrupt_before
  [G] assemble     ordered full draft + decision summary

State persists to SQLite at every transition. Kill mid-run -> resume from checkpoint.

NOTE: Memory layers 6a-6c, weight tuning, and PPT generation [H] are later steps
(team Steps 4-7) -- deliberately out of this skeleton.
"""

import os
import json
from typing import TypedDict, Literal

import anthropic
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.agents.rag import retrieve_routed

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-opus-4-5"

DEFAULT_CONFIDENCE_THRESHOLD = 0.7   # user-configurable, instance-level override
CHECKPOINT_DB = "./checkpoints.sqlite"


# -- Graph state ---------------------------------------------------------------

class Requirement(TypedDict):
    id: str                       # "Q1", "Q2", ...
    text: str
    portfolio_area: str


class CandidateSource(TypedDict):
    source_id: str
    snippet: str
    weighted_score: float


class Section(TypedDict):
    requirement_id: str
    draft: str
    citations: list[str]
    confidence: float
    flagged: bool
    flag_reason: str


class RFPState(TypedDict):
    rfp_text: str
    doc_type: str
    user_id: str
    confidence_threshold: float
    requirements: list[Requirement]
    scope_summary: str
    candidates: dict
    confirmed_sources: dict
    sections: list[Section]
    sections_needing_review: list[str]
    final_draft: str
    decision_summary: str


# -- [A] Parse -----------------------------------------------------------------

def node_parse(state: RFPState) -> dict:
    """Extract discrete requirements/questions from the RFP document."""
    doc_label = "RFI" if state["doc_type"] == "rfi" else "RFP"
    prompt = f"""Extract every distinct requirement or question from this {doc_label}.
Return JSON only: {{"requirements": [{{"id": "Q1", "text": "..."}}]}}

=== {doc_label} ===
{state['rfp_text']}"""
    resp = client.messages.create(
        model=MODEL, max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    parsed = json.loads(resp.content[0].text.strip())
    reqs = [{"id": r["id"], "text": r["text"], "portfolio_area": ""}
            for r in parsed["requirements"]]
    return {"requirements": reqs}


# -- [B] Scope -----------------------------------------------------------------

def node_scope(state: RFPState) -> dict:
    """Classify overall intent and map each requirement to a portfolio area."""
    reqs_text = "\n".join(f"{r['id']}: {r['text']}" for r in state["requirements"])
    prompt = f"""For this {state['doc_type'].upper()}, map each requirement to a Zyter
portfolio area (Utilization Management, Care Management, Integration, Security,
Reporting, Other). Return JSON only:
{{"scope_summary": "1-2 sentences", "mapping": {{"Q1": "area"}}}}

=== Requirements ===
{reqs_text}"""
    resp = client.messages.create(
        model=MODEL, max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    out = json.loads(resp.content[0].text.strip())
    mapping = out.get("mapping", {})
    reqs = [{**r, "portfolio_area": mapping.get(r["id"], "Other")}
            for r in state["requirements"]]
    return {"requirements": reqs, "scope_summary": out.get("scope_summary", "")}


# -- [C] Weighted retrieval ----------------------------------------------------

def node_retrieve(state: RFPState) -> dict:
    """Candidate grounding sources per requirement, via rag.retrieve_routed.

    (Skeleton uses rag.py relevance_score; named-multiplier weighting from
    source-metadata.md is team Step 2/4.)
    """
    candidates: dict = {}
    for r in state["requirements"]:
        docs = retrieve_routed(r["text"], k=4)
        candidates[r["id"]] = [
            {"source_id": d.metadata.get("source", "unknown"),
             "snippet": d.page_content[:200],
             "weighted_score": d.metadata.get("relevance_score", 0.0)}
            for d in docs
        ]
    return {"candidates": candidates}


# -- [D] Human confirms sources  (INTERRUPT before this node) -------------------

def node_confirm_sources(state: RFPState) -> dict:
    """Resume point after human confirmation.

    Graph compiled with interrupt_before=["confirm_sources"] -> pauses BEFORE here.
    UI reads state['candidates'], human approves/swaps/adds/rejects, writes
    state['confirmed_sources'] via update_state, resumes with invoke(None).

    Default (auto): approve all candidates so the skeleton runs end-to-end.
    """
    confirmed = state.get("confirmed_sources") or {}
    if not confirmed:
        confirmed = {rid: [c["source_id"] for c in cands]
                     for rid, cands in state["candidates"].items()}
    return {"confirmed_sources": confirmed}


# -- [E] Draft per section -----------------------------------------------------

def node_draft(state: RFPState) -> dict:
    """Draft each section grounded ONLY in human-confirmed sources."""
    sections: list[Section] = []
    for r in state["requirements"]:
        approved_ids = state["confirmed_sources"].get(r["id"], [])
        cands = state["candidates"].get(r["id"], [])
        grounding = "\n".join(
            f"[{c['source_id']}] {c['snippet']}"
            for c in cands if c["source_id"] in approved_ids
        ) or "No confirmed sources."

        prompt = f"""You are a Zyter Sales Engineering assistant drafting a {state['doc_type'].upper()} response.
Draft a response to this requirement, grounded ONLY in the confirmed sources below.
Every claim must trace to a source. Cite source filenames you used.
Style: specific, compelling, but never over-promise capabilities not in the sources.

Return JSON only:
{{"draft": "...", "citations": ["source_id"], "confidence": 0.0}}

=== Requirement {r['id']} ({r['portfolio_area']}) ===
{r['text']}

=== Confirmed sources ===
{grounding}"""
        resp = client.messages.create(
            model=MODEL, max_tokens=1536,
            messages=[{"role": "user", "content": prompt}],
        )
        out = json.loads(resp.content[0].text.strip())
        sections.append({
            "requirement_id": r["id"],
            "draft": out.get("draft", ""),
            "citations": out.get("citations", []),
            "confidence": float(out.get("confidence", 0.0)),
            "flagged": False, "flag_reason": "",
        })
    return {"sections": sections}


# -- Citation validator + confidence router (CODE check, not LLM) --------------

def validate_and_route(state: RFPState) -> dict:
    """Hard citation enforcement + confidence routing.

    Citation rule (team section 2, decided): every section must carry >=1 citation,
    and every citation must resolve to a source confirmed at gate [D]. A section with
    missing/unresolvable citations routes to review REGARDLESS of confidence.
    """
    threshold = state.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
    flagged_ids: list[str] = []
    sections = []
    for s in state["sections"]:
        approved = set(state["confirmed_sources"].get(s["requirement_id"], []))
        cites = s["citations"]
        flagged, reason = False, ""
        if not cites or not all(c in approved for c in cites):
            flagged, reason = True, "missing_or_unresolvable_citation"
        elif s["confidence"] < threshold:
            flagged, reason = True, "low_confidence"
        sections.append({**s, "flagged": flagged, "flag_reason": reason})
        if flagged:
            flagged_ids.append(s["requirement_id"])
    return {"sections": sections, "sections_needing_review": flagged_ids}


def route_after_validation(state: RFPState) -> Literal["human_review", "assemble"]:
    """Conditional edge: any flagged section -> human review; else -> assemble."""
    return "human_review" if state["sections_needing_review"] else "assemble"


# -- [F] Human review loop  (INTERRUPT before this node) -----------------------

def node_human_review(state: RFPState) -> dict:
    """Resume point after human review/edit.

    Compiled with interrupt_before=["human_review"]. UI shows flagged sections;
    human edits/approves; resume writes updated sections via update_state.

    Skeleton default (auto-approve): clear flags so the graph completes.
    Full section-6b tagged-feedback co-editing memory is team Step 5.
    """
    sections = [{**s, "flagged": False} for s in state["sections"]]
    return {"sections": sections, "sections_needing_review": []}


# -- [G] Assemble --------------------------------------------------------------

def node_assemble(state: RFPState) -> dict:
    """Order sections by requirement id; build final draft + decision summary."""
    ordered = sorted(state["sections"], key=lambda s: s["requirement_id"])
    parts = []
    for s in ordered:
        cite = f"  [sources: {', '.join(s['citations'])}]" if s["citations"] else ""
        parts.append(f"### {s['requirement_id']}\n{s['draft']}{cite}")
    final = "\n\n".join(parts)
    n_review = sum(1 for s in state["sections"] if s["flag_reason"])
    summary = (f"{len(state['sections'])} sections drafted; "
               f"{n_review} required human review. "
               f"Scope: {state.get('scope_summary', '')}")
    return {"final_draft": final, "decision_summary": summary}


# -- Build the graph -----------------------------------------------------------

def build_graph(checkpointer=None):
    """Compile the LangGraph DAG with two HITL interrupts.

    interrupt_before pauses execution BEFORE the named node so the UI can inject
    human decisions via update_state, then resume with invoke(None, config).
    """
    g = StateGraph(RFPState)
    g.add_node("parse", node_parse)
    g.add_node("scope", node_scope)
    g.add_node("retrieve", node_retrieve)
    g.add_node("confirm_sources", node_confirm_sources)
    g.add_node("draft", node_draft)
    g.add_node("validate", validate_and_route)
    g.add_node("human_review", node_human_review)
    g.add_node("assemble", node_assemble)

    g.add_edge(START, "parse")
    g.add_edge("parse", "scope")
    g.add_edge("scope", "retrieve")
    g.add_edge("retrieve", "confirm_sources")
    g.add_edge("confirm_sources", "draft")
    g.add_edge("draft", "validate")
    g.add_conditional_edges("validate", route_after_validation, {
        "human_review": "human_review",
        "assemble": "assemble",
    })
    g.add_edge("human_review", "assemble")
    g.add_edge("assemble", END)

    return g.compile(
        checkpointer=checkpointer,
        interrupt_before=["confirm_sources", "human_review"],
    )


# -- Convenience runner --------------------------------------------------------

def run(rfp_text: str, user_id: str = "anon", doc_type: str = "rfp",
        thread_id: str = "default") -> dict:
    """Run end-to-end, auto-passing both interrupts with defaults (for tests/demo)."""
    with SqliteSaver.from_conn_string(CHECKPOINT_DB) as cp:
        graph = build_graph(checkpointer=cp)
        config = {"configurable": {"thread_id": thread_id}}
        init: RFPState = {
            "rfp_text": rfp_text, "doc_type": doc_type, "user_id": user_id,
            "confidence_threshold": DEFAULT_CONFIDENCE_THRESHOLD,
            "requirements": [], "scope_summary": "", "candidates": {},
            "confirmed_sources": {}, "sections": [],
            "sections_needing_review": [], "final_draft": "", "decision_summary": "",
        }
        graph.invoke(init, config)        # -> pauses before confirm_sources
        graph.invoke(None, config)        # resume -> pauses before human_review or ends
        if graph.get_state(config).next:  # still paused at human_review
            graph.invoke(None, config)
        return graph.get_state(config).values


if __name__ == "__main__":
    # Structure smoke test -- does the graph compile with the right shape?
    graph = build_graph(checkpointer=None)
    print("OK: graph compiled")
    print("Nodes:", [n for n in graph.get_graph().nodes.keys()])
    print("\nInterrupts before: confirm_sources, human_review")
    print("\nGraph (mermaid):")
    print(graph.get_graph().draw_mermaid())
