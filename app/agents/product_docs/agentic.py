"""
Product Documentation Chatbot — AGENTIC variant (task #2 core).

The agent plans its own retrieval: Claude decides which tool(s) to call, with what
versions, and whether to retrieve again (multi-hop) — a ReAct / IRCoT loop, NOT a
fixed chain. Contrast arm is baseline.py (single fixed retrieve).

Grounded in agentic-tech.md + rag.md:
  - ReAct loop (think→tool→observe→repeat) = "plans its own retrieval"
  - Session Memory via SqliteSaver keyed by thread_id = follow-up handling
  - Abstain + unanswerable_log = Visible Escalation / KB-gap detector
  - Explicit versions in a follow-up override thread history (hard rule)

Graph:  START → rewrite → agent ⇄ tools → compose → END
                                  (loop while Claude keeps calling tools)
"""

import os
import json
import operator
from typing import TypedDict, Annotated, Literal
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.agents.product_docs.tools import TOOL_SCHEMAS, TOOL_FNS

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-opus-4-5"
CHECKPOINT_DB = "./product_docs_checkpoints.sqlite"
UNANSWERABLE_LOG = "./unanswerable_log.jsonl"
MAX_TOOL_HOPS = 5   # safety bound on the ReAct loop

SYSTEM = """You are a TruCare product documentation assistant. Answer questions about
features and bugs ACROSS VERSIONS using the provided tools.

Rules:
- Version is a HARD boundary. A 25.1-vs-25.2 answer must never use a v24 fact.
- Plan your own retrieval: call tools as many times as needed (e.g. pull each version,
  then compare). For "what changed between X and Y", retrieve both before answering.
- Answer ONLY from tool results. Every factual claim must cite its source (cp_id or
  version + source file).
- If the tools don't return enough to answer, reply starting with "ABSTAIN:" and say
  what's missing. NEVER guess a version fact.
- If the question is outside product documentation (pricing, licensing, contracts,
  roadmap, support SLAs), reply starting with "ABSTAIN:" and redirect to the right team —
  do NOT answer from general knowledge.
- End with a sources block listing the cp_ids / files you used."""


# ── State ─────────────────────────────────────────────────────────────────────

class PDState(TypedDict):
    question: str
    rewritten_question: str
    messages: Annotated[list, operator.add]   # anthropic-format, accumulates
    stop_reason: str
    tool_hops: Annotated[int, operator.add]
    answer: str
    abstained: bool


# ── [rewrite] follow-up resolution ────────────────────────────────────────────

def node_rewrite(state: PDState) -> dict:
    """Resolve a follow-up into a standalone question using thread history.

    Hard rule: explicit versions in the new question override versions from history.
    On a thread's first turn this is trivially a pass-through.
    The checkpointer supplies prior messages; we look at what's already in state.
    """
    history = state.get("messages", [])
    q = state["question"]

    if not history:
        rewritten = q   # first turn — nothing to resolve against
    else:
        prompt = f"""Given the conversation so far, rewrite the new question into a
standalone question. If it's already self-contained, return it unchanged.
HARD RULE: any versions named explicitly in the new question override versions from history.
Return JSON only: {{"standalone": true|false, "rewritten": "..."}}

New question: {q}"""
        resp = client.messages.create(
            model=MODEL, max_tokens=512, system=prompt,
            messages=history + [{"role": "user", "content": q}],
        )
        try:
            out = json.loads(resp.content[0].text.strip())
            rewritten = out.get("rewritten", q)
        except Exception:
            rewritten = q   # conservative: fall back to literal question

    return {
        "rewritten_question": rewritten,
        "messages": [{"role": "user", "content": rewritten}],
    }


# ── [agent] ReAct: Claude decides tool calls ──────────────────────────────────

def node_agent(state: PDState) -> dict:
    """One Claude turn with tools bound. If it calls tools → loop; else → final answer."""
    resp = client.messages.create(
        model=MODEL, max_tokens=2048, system=SYSTEM,
        messages=state["messages"], tools=TOOL_SCHEMAS,
    )
    assistant_msg = {"role": "assistant", "content": resp.content}
    return {"messages": [assistant_msg], "stop_reason": resp.stop_reason}


def route_agent(state: PDState) -> Literal["tools", "compose"]:
    """Loop to tools while Claude keeps calling them, up to MAX_TOOL_HOPS."""
    if state["stop_reason"] == "tool_use" and state.get("tool_hops", 0) < MAX_TOOL_HOPS:
        return "tools"
    return "compose"


# ── [tools] execute the calls, feed results back ──────────────────────────────

def node_tools(state: PDState) -> dict:
    """Run every tool_use block in the last assistant message; return tool_results."""
    last = state["messages"][-1]
    results = []
    for block in last["content"]:
        if getattr(block, "type", None) == "tool_use":
            fn = TOOL_FNS.get(block.name)
            try:
                out = fn(**block.input) if fn else {"error": f"unknown tool {block.name}"}
            except Exception as e:
                out = {"error": str(e)}
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(out)[:6000],
            })
    return {"messages": [{"role": "user", "content": results}], "tool_hops": 1}


# ── [compose] extract final answer / detect abstention ────────────────────────

def _final_text(msg) -> str:
    parts = []
    for block in msg["content"]:
        t = getattr(block, "text", None)
        if t:
            parts.append(t)
    return "\n".join(parts)


def _gathered_evidence(messages) -> str:
    """All tool_result payloads accumulated across the ReAct loop, oldest→newest."""
    blobs = []
    for m in messages:
        content = m.get("content")
        if m.get("role") == "user" and isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    blobs.append(b.get("content", ""))
    return "\n".join(blobs)


def node_compose(state: PDState) -> dict:
    text = _final_text(state["messages"][-1])
    # If the ReAct loop was cut off at MAX_TOOL_HOPS, the last assistant turn is an
    # unanswered tool-call request with no prose → empty answer. Force ONE tool-free
    # synthesis from everything already gathered so the agent never returns nothing.
    # (Found on real data: a noisy "what's new in 25.2" lookup spiralled to the hop
    # ceiling and returned empty, while the baseline answered it in one shot.)
    if not text.strip():
        evidence = _gathered_evidence(state["messages"])
        q = state.get("rewritten_question") or state["question"]
        resp = client.messages.create(
            model=MODEL, max_tokens=2048, system=SYSTEM,
            messages=[{"role": "user", "content": (
                f"Question: {q}\n\nEvidence gathered from the documentation tools:\n"
                f"{evidence[:8000]}\n\nGive your FINAL answer now from this evidence, "
                "citing versions/sources. If it is insufficient, reply starting with "
                "'ABSTAIN:'.")}],
        )
        text = _final_text({"content": resp.content})
    abstained = text.strip().upper().startswith("ABSTAIN")
    if abstained:
        with open(UNANSWERABLE_LOG, "a") as f:
            f.write(json.dumps({
                "ts": datetime.utcnow().isoformat(),
                "question": state["question"],
                "rewritten": state.get("rewritten_question", ""),
            }) + "\n")
    return {"answer": text, "abstained": abstained}


# ── Build ─────────────────────────────────────────────────────────────────────

def build_graph(checkpointer=None):
    g = StateGraph(PDState)
    g.add_node("rewrite", node_rewrite)
    g.add_node("agent", node_agent)
    g.add_node("tools", node_tools)
    g.add_node("compose", node_compose)

    g.add_edge(START, "rewrite")
    g.add_edge("rewrite", "agent")
    g.add_conditional_edges("agent", route_agent, {"tools": "tools", "compose": "compose"})
    g.add_edge("tools", "agent")     # ReAct loop
    g.add_edge("compose", END)
    return g.compile(checkpointer=checkpointer)


def ask(question: str, thread_id: str = "default") -> dict:
    """Single entry point. thread_id ties follow-ups into one conversation (Session Memory)."""
    with SqliteSaver.from_conn_string(CHECKPOINT_DB) as cp:
        graph = build_graph(checkpointer=cp)
        config = {"configurable": {"thread_id": thread_id}}
        graph.invoke({"question": question}, config)
        return graph.get_state(config).values


if __name__ == "__main__":
    # Structure smoke test — compiles, nodes wired, ReAct loop present (no API key)
    graph = build_graph(checkpointer=None)
    print("OK: agentic graph compiled")
    print("Nodes:", list(graph.get_graph().nodes.keys()))
    print("Tools bound:", [t["name"] for t in TOOL_SCHEMAS])
    print("\nMermaid:")
    print(graph.get_graph().draw_mermaid())
