"""
Product Documentation Chatbot — BASELINE variant (the control arm for task #2).

Fixed chain, NO agent loop: extract versions+intent once → single retrieve →
compose once. Same tools and data as agentic.py; the only difference is the agent
does NOT plan its own retrieval. This is what we compare the agentic variant against.

ask() has the same signature as agentic.ask() so the eval can swap them.
"""

import os
import json

import anthropic
from dotenv import load_dotenv

from app.agents.product_docs.tools import search_issues, search_features

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-opus-4-5"


def _plan(question: str) -> dict:
    """One call: pull the versions and whether this is a feature or issue question."""
    prompt = f"""Extract from this TruCare question:
- versions: list of version strings mentioned (e.g. ["24.2","25.1"]); [] if none
- intent: "issue" if about bugs/defects/what's fixed, else "feature"
Return JSON only: {{"versions": [...], "intent": "issue|feature"}}

Question: {question}"""
    resp = client.messages.create(model=MODEL, max_tokens=256,
                                  messages=[{"role": "user", "content": prompt}])
    try:
        return json.loads(resp.content[0].text.strip())
    except Exception:
        return {"versions": [], "intent": "feature"}


def ask(question: str, thread_id: str = "default") -> dict:
    """Fixed chain: plan → one retrieve → compose. (thread_id ignored — no memory.)"""
    p = _plan(question)
    versions = p.get("versions") or ["24.2", "25.1", "25.2"]   # fallback: all
    intent = p.get("intent", "feature")

    evidence = (search_issues(question, versions) if intent == "issue"
                else search_features(question, versions))

    if not evidence:
        return {"answer": "ABSTAIN: no matching documentation found.",
                "abstained": True, "tool_hops": 1, "rewritten_question": question}

    compose_prompt = f"""Answer the question using ONLY this evidence. Cite cp_id/source
for every claim. If evidence is insufficient, start with "ABSTAIN:". Never guess a
version fact.

Question: {question}

Evidence (JSON):
{json.dumps(evidence)[:6000]}"""
    resp = client.messages.create(model=MODEL, max_tokens=1536,
                                  messages=[{"role": "user", "content": compose_prompt}])
    answer = resp.content[0].text
    return {
        "answer": answer,
        "abstained": answer.strip().upper().startswith("ABSTAIN"),
        "tool_hops": 1,                 # fixed chain always retrieves exactly once
        "rewritten_question": question,
    }


if __name__ == "__main__":
    r = ask("what changed between 24.2 and 25.1?")
    print("TOOL HOPS:", r["tool_hops"], "| ABSTAINED:", r["abstained"])
    print(r["answer"])
