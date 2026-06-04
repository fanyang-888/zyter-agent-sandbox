"""
Eval runner — checks agent outputs against golden dataset.

Usage:
  python eval/run_eval.py              # run all cases
  python eval/run_eval.py --agent rfp  # RFP agent only
  python eval/run_eval.py --agent ci   # CI agent only
  python eval/run_eval.py --type hallucination_trap  # only traps

Scoring:
  - PASS: all expected_keywords present AND no forbidden strings found
  - FAIL: any expected keyword missing OR any forbidden string found
  - Target: 80% overall pass rate, 100% on hallucination_trap cases

Based on agentic-tech.md best practice:
  "Build eval dataset BEFORE going live.
   Derive cases from real failure scenarios.
   Re-run eval after every prompt change."
"""

import sys
import argparse
import json
from typing import Optional

# Add project root to path
sys.path.insert(0, ".")

from eval.eval_dataset import RFP_CASES, CI_CASES, EVAL_CONFIG
from app.agents import rfp_agent, competitive_intel_agent


def check_rfp_case(case: dict, result: dict) -> dict:
    """Evaluates one RFP agent output against its golden spec."""
    failures = []
    full_text = json.dumps(result).lower()

    # Check expected keywords
    for kw in case.get("expected_keywords", []):
        if kw.lower() not in full_text:
            failures.append(f"MISSING keyword: '{kw}'")

    # Check forbidden strings (hallucination check)
    for forbidden in case.get("forbidden", []):
        if forbidden.lower() in full_text:
            failures.append(f"HALLUCINATION: found forbidden string '{forbidden}'")

    # Check expected gaps
    for gap_kw in case.get("expected_gaps", []):
        gap_text = json.dumps(result.get("gaps", [])).lower()
        if gap_kw.lower() not in gap_text:
            failures.append(f"MISSING gap: '{gap_kw}' should appear in gaps list")

    # Check confidence level
    min_conf = case.get("min_confidence", "low")
    conf_rank = {"high": 2, "medium": 1, "low": 0}
    sections = result.get("sections", [])
    if sections:
        actual_confs = [conf_rank.get(s.get("confidence", "low"), 0) for s in sections]
        avg_conf = sum(actual_confs) / len(actual_confs)
        if avg_conf < conf_rank.get(min_conf, 0) - 0.5:
            failures.append(f"CONFIDENCE too low: expected avg >= {min_conf}")

    return {
        "case_id":   case["id"],
        "case_type": case["case_type"],
        "passed":    len(failures) == 0,
        "failures":  failures,
        "notes":     case.get("notes", ""),
    }


def check_ci_case(case: dict, result: dict) -> dict:
    """Evaluates one CI agent output against its golden spec."""
    failures = []
    win_text  = json.dumps(result.get("where_we_win", [])).lower()
    lose_text = json.dumps(result.get("where_we_lose", [])).lower()
    full_text = json.dumps(result).lower()

    for kw in case.get("expected_in_win", []):
        if kw.lower() not in full_text:
            failures.append(f"MISSING win keyword: '{kw}'")

    for kw in case.get("expected_in_lose", []):
        if kw.lower() not in full_text:
            failures.append(f"MISSING loss keyword: '{kw}'")

    for forbidden in case.get("forbidden_in_win", []):
        if forbidden.lower() in full_text:
            failures.append(f"HALLUCINATION: found forbidden string '{forbidden}'")

    return {
        "case_id":   case["id"],
        "case_type": case["case_type"],
        "passed":    len(failures) == 0,
        "failures":  failures,
        "notes":     case.get("notes", ""),
    }


def run_rfp_eval(cases: list[dict]) -> list[dict]:
    results = []
    for case in cases:
        try:
            output = rfp_agent.run({"rfp_text": case["input"], "user_id": "eval"})
            result = check_rfp_case(case, output)
        except Exception as e:
            result = {"case_id": case["id"], "case_type": case["case_type"],
                      "passed": False, "failures": [f"EXCEPTION: {e}"], "notes": ""}
        results.append(result)
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"  {status}  {result['case_id']} ({result['case_type']})")
        for f in result["failures"]:
            print(f"          → {f}")
    return results


def run_ci_eval(cases: list[dict]) -> list[dict]:
    results = []
    for case in cases:
        try:
            output = competitive_intel_agent.run({**case["input"], "user_id": "eval"})
            result = check_ci_case(case, output)
        except Exception as e:
            result = {"case_id": case["id"], "case_type": case["case_type"],
                      "passed": False, "failures": [f"EXCEPTION: {e}"], "notes": ""}
        results.append(result)
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"  {status}  {result['case_id']} ({result['case_type']})")
        for f in result["failures"]:
            print(f"          → {f}")
    return results


def print_summary(all_results: list[dict]):
    total = len(all_results)
    passed = sum(1 for r in all_results if r["passed"])
    traps  = [r for r in all_results if r["case_type"] == "hallucination_trap"]
    traps_passed = sum(1 for r in traps if r["passed"])

    print("\n" + "=" * 50)
    print(f"EVAL SUMMARY  (v{EVAL_CONFIG['version']})")
    print("=" * 50)
    print(f"Overall:             {passed}/{total} passed  ({100*passed//total}%)")
    print(f"Hallucination traps: {traps_passed}/{len(traps)} passed")
    print(f"Target pass rate:    {int(EVAL_CONFIG['target_pass_rate']*100)}%")

    target_met = (passed / total) >= EVAL_CONFIG["target_pass_rate"]
    traps_met  = (not traps) or (traps_passed == len(traps))

    if target_met and traps_met:
        print("\n🟢 READY TO DEMO — all targets met")
    elif not traps_met:
        print("\n🔴 NOT READY — hallucination trap(s) failing. Fix before any demo.")
    else:
        print(f"\n🟡 PARTIAL — pass rate below {int(EVAL_CONFIG['target_pass_rate']*100)}% target")

    failed = [r for r in all_results if not r["passed"]]
    if failed:
        print(f"\nFailed cases to fix:")
        for r in failed:
            print(f"  {r['case_id']}: {r['failures']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=["rfp", "ci", "all"], default="all")
    parser.add_argument("--type", choices=["normal", "edge", "gap", "hallucination_trap", "all"], default="all")
    args = parser.parse_args()

    all_results = []

    if args.agent in ("rfp", "all"):
        cases = RFP_CASES if args.type == "all" else [c for c in RFP_CASES if c["case_type"] == args.type]
        if cases:
            print(f"\n── RFP Agent ({len(cases)} cases) ──")
            all_results += run_rfp_eval(cases)

    if args.agent in ("ci", "all"):
        cases = CI_CASES if args.type == "all" else [c for c in CI_CASES if c["case_type"] == args.type]
        if cases:
            print(f"\n── CI Agent ({len(cases)} cases) ──")
            all_results += run_ci_eval(cases)

    print_summary(all_results)
