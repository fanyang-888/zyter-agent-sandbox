"""
Eval: baseline (fixed chain) vs agentic (plans own retrieval) — task #2 deliverable.

Golden Q&A over the synthetic corpus. Each case checks three things:
  - contains:  expected facts present
  - forbid:    cross-version leaks absent (the critical correctness test)
  - abstain:   matches expected abstention

Scores both variants on pass-rate / cross-version leaks / avg tool-hops.
This comparison IS the "explore different ways to set up agents" midterm output.

Run:  PYTHONPATH=. python eval/product_docs_eval.py   (needs ANTHROPIC_API_KEY + ingested KB)
"""

import sys
sys.path.insert(0, ".")

from app.agents.product_docs import agentic, baseline

# ── Golden Q&A (grounded in data/synthetic) ───────────────────────────────────

CASES = [
    {"id": "feat-251", "q": "What new features are in 25.1?",
     "contains": ["Temporary Member", "Personal Medication"],
     "forbid":   ["Special Instructions", "UM Compliance"],   # those are 25.2
     "abstain": False},
    {"id": "compare", "q": "What changed between 24.2 and 25.1?",
     "contains": ["InterQual", "Temporary Member"],
     "forbid":   ["Special Instructions", "Historical Service Level"],  # 25.2
     "abstain": False},
    {"id": "bugs-251", "q": "What bugs were resolved in 25.1?",
     "contains": ["CP-100001"],
     "forbid":   [],
     "abstain": False},
    {"id": "feat-252", "q": "What's new in 25.2?",
     "contains": ["Special Instructions", "UM Compliance"],
     "forbid":   ["Temporary Member Record Edit", "Personal Medication"],  # 25.1
     "abstain": False},
    {"id": "trap-242", "q": "What features are in 24.2?",
     "contains": ["CareWebQI"],
     "forbid":   ["Temporary Member Record Edit", "Special Instructions"],  # 25.1/25.2 leak
     "abstain": False},
    {"id": "hcs-issue", "q": "What known issues affect Home and Community Services in 25.1?",
     "contains": ["CP-100006"],
     "forbid":   [],
     "abstain": False},
    {"id": "abstain", "q": "What pharmacy claims adjudication features are in 25.1?",
     "contains": [],
     "forbid":   [],
     "abstain": True},   # no such thing in the corpus → must abstain, not invent
]


def score(answer: str, abstained: bool, case: dict) -> tuple[bool, list[str]]:
    a = answer.lower()
    fails = []
    if case["abstain"]:
        if not abstained:
            fails.append("should have abstained")
        return (len(fails) == 0, fails)
    for kw in case["contains"]:
        if kw.lower() not in a:
            fails.append(f"missing '{kw}'")
    for kw in case["forbid"]:
        if kw.lower() in a:
            fails.append(f"LEAK '{kw}'")
    if abstained:
        fails.append("abstained unexpectedly")
    return (len(fails) == 0, fails)


def run(variant_name: str, ask_fn) -> dict:
    passed = leaks = hops_total = 0
    print(f"\n── {variant_name} ──")
    for i, c in enumerate(CASES):
        r = ask_fn(c["q"], thread_id=f"eval-{variant_name}-{i}")
        ok, fails = score(r.get("answer", ""), r.get("abstained", False), c)
        hops_total += r.get("tool_hops", 0)
        if ok:
            passed += 1
        leaks += sum(1 for f in fails if f.startswith("LEAK"))
        print(f"  {'✅' if ok else '❌'} {c['id']:12} hops={r.get('tool_hops',0)}"
              + ("" if ok else f"  → {fails}"))
    return {"passed": passed, "total": len(CASES), "leaks": leaks,
            "avg_hops": round(hops_total / len(CASES), 1)}


if __name__ == "__main__":
    b = run("baseline", baseline.ask)
    a = run("agentic", agentic.ask)

    print("\n" + "=" * 52)
    print(f"{'':12}{'pass':>10}{'leaks':>10}{'avg_hops':>12}")
    print(f"{'baseline':12}{b['passed']}/{b['total']:>8}{b['leaks']:>10}{b['avg_hops']:>12}")
    print(f"{'agentic':12}{a['passed']}/{a['total']:>8}{a['leaks']:>10}{a['avg_hops']:>12}")
    print("=" * 52)
    print("Cross-version leaks must be 0 for both (correctness gate).")
    print("avg_hops: agentic > baseline = it plans multi-step retrieval.")
