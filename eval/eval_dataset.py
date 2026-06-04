"""
Eval dataset — golden Q&A pairs for both agents.

Based on Databricks/agentic-tech best practice:
  - Build eval dataset BEFORE going live (min 20-50 pairs)
  - Derive cases from real failure scenarios (Matt's pain points)
  - Cover: normal cases, edge cases, gap cases, hallucination traps

Each case has:
  - input:             what gets sent to the agent
  - expected_keywords: strings that MUST appear in a good output
  - forbidden:         strings that must NOT appear (hallucination traps)
  - expected_gaps:     for RFP agent — requirements we expect to flag as gaps
  - min_confidence:    minimum confidence level we expect
  - case_type:         "normal" | "edge" | "gap" | "hallucination_trap"
  - notes:             why this case exists (derived from Matt meeting)

Run with: python eval/run_eval.py
"""

# ── RFP Agent Cases ───────────────────────────────────────────────────────────

RFP_CASES = [

    # ── Normal cases (standard Zyter capabilities) ────────────────────────────

    {
        "id": "rfp-001",
        "case_type": "normal",
        "input": "We require automated prior authorization workflow for Medicare Advantage members with 80% same-day decision rate.",
        "expected_keywords": ["Symphony", "Praxis", "prior authorization", "auto-approval"],
        "forbidden": ["Epic", "Cerner", "Cohere Health"],  # competitor names = hallucination
        "expected_gaps": [],
        "min_confidence": "high",
        "notes": "Core Zyter capability — should generate high-confidence response with Symphony/Praxis reference",
    },
    {
        "id": "rfp-002",
        "case_type": "normal",
        "input": "The platform must support Care Management workflows including post-discharge coordination and high-risk patient outreach.",
        "expected_keywords": ["Praxis", "Care Management", "CM"],
        "forbidden": [],
        "expected_gaps": [],
        "min_confidence": "high",
        "notes": "CM Praxis module — well-documented Zyter capability",
    },
    {
        "id": "rfp-003",
        "case_type": "normal",
        "input": "Require full audit trail on all AI-assisted decisions for CMS compliance reporting.",
        "expected_keywords": ["audit trail", "Symphony", "governance"],
        "forbidden": [],
        "expected_gaps": [],
        "min_confidence": "high",
        "notes": "Symphony audit trail is a named differentiator — should always appear",
    },

    # ── Edge cases (partial Zyter coverage) ───────────────────────────────────

    {
        "id": "rfp-004",
        "case_type": "edge",
        "input": "Integration with Epic EHR via certified HL7 FHIR R4 API is required.",
        "expected_keywords": ["FHIR", "integration", "confirm"],
        "forbidden": ["Epic-certified", "certified connector"],  # don't hallucinate certification status
        "expected_gaps": [],
        "min_confidence": "medium",
        "notes": "Epic integration is unconfirmed — agent must not claim certified Epic connector",
    },
    {
        "id": "rfp-005",
        "case_type": "edge",
        "input": "SSO with Azure Active Directory using SAML 2.0 is mandatory.",
        "expected_keywords": ["identity", "SSO", "confirm", "SE"],
        "forbidden": ["Azure AD certified", "SAML 2.0 supported"],  # unconfirmed
        "expected_gaps": [],
        "min_confidence": "low",
        "notes": "IdP config unconfirmed in Matt meeting — must flag for human review",
    },

    # ── Gap cases (Zyter genuinely doesn't cover this) ────────────────────────

    {
        "id": "rfp-006",
        "case_type": "gap",
        "input": "The vendor must provide a certified pharmacy benefit management (PBM) module with formulary management.",
        "expected_keywords": [],
        "forbidden": ["Zyter provides PBM", "formulary management module"],
        "expected_gaps": ["PBM", "formulary"],
        "min_confidence": "low",
        "notes": "PBM is outside Zyter's portfolio — must appear in gaps, not fabricated",
    },
    {
        "id": "rfp-007",
        "case_type": "gap",
        "input": "Require direct integration with Salesforce Health Cloud for care team coordination.",
        "expected_keywords": [],
        "forbidden": ["Zyter integrates with Salesforce", "Salesforce Health Cloud connector"],
        "expected_gaps": ["Salesforce"],
        "min_confidence": "low",
        "notes": "Salesforce connector not confirmed — should be a gap, not fabricated",
    },

    # ── Hallucination traps ────────────────────────────────────────────────────

    {
        "id": "rfp-008",
        "case_type": "hallucination_trap",
        "input": "The vendor must demonstrate 95% prior authorization auto-approval rate in a Medicare Advantage deployment.",
        "expected_keywords": ["80", "90", "audit"],
        "forbidden": ["95%", "99%", "100%"],  # Zyter claims 80-90%, not 95%
        "expected_gaps": [],
        "min_confidence": "medium",
        "notes": "Zyter's stated rate is 80-90%. Agent must NOT inflate to 95%+ to match the RFP ask",
    },
    {
        "id": "rfp-009",
        "case_type": "hallucination_trap",
        "input": "We need a solution with FDA Class II medical device certification for clinical decision support.",
        "expected_keywords": [],
        "forbidden": ["FDA Class II certified", "FDA approved", "Class II clearance"],
        "expected_gaps": ["FDA Class II", "medical device certification"],
        "min_confidence": "low",
        "notes": "FDA Class II is a critical hallucination trap — Zyter has no such certification on file",
    },
]


# ── Competitive Intelligence Agent Cases ─────────────────────────────────────

CI_CASES = [

    # ── Normal cases ──────────────────────────────────────────────────────────

    {
        "id": "ci-001",
        "case_type": "normal",
        "input": {"competitor_name": "Cohere Health", "deal_context": "Medicare Advantage plan, prior authorization automation RFP"},
        "expected_in_win": ["Symphony", "orchestration", "governance", "audit"],
        "expected_in_lose": ["ARR", "revenue", "brand", "outcomes"],
        "forbidden_in_win": ["Cohere Health is better", "they beat us"],
        "expected_confidence": "high",
        "notes": "Cohere Health is the primary PA competitor — win/lose should be balanced and honest",
    },
    {
        "id": "ci-002",
        "case_type": "normal",
        "input": {"competitor_name": "Freed", "deal_context": "Clinical encounter documentation, small practice"},
        "expected_in_win": ["Praxis", "enterprise", "payer"],
        "expected_in_lose": ["clinician", "adoption", "physician"],
        "forbidden_in_win": [],
        "expected_confidence": "medium",
        "notes": "Freed is a clinical scribe tool — Zyter competes on enterprise/payer angle",
    },

    # ── Edge cases ────────────────────────────────────────────────────────────

    {
        "id": "ci-003",
        "case_type": "edge",
        "input": {"competitor_name": "Glean", "deal_context": "Internal knowledge search for sales team"},
        "expected_in_win": [],
        "expected_in_lose": ["knowledge search", "enterprise search"],
        "forbidden_in_win": ["Zyter beats Glean on search"],  # not true
        "expected_confidence": "low",
        "notes": "Glean is an enterprise search tool — limited battle card data, should return low confidence",
    },

    # ── Hallucination traps ────────────────────────────────────────────────────

    {
        "id": "ci-004",
        "case_type": "hallucination_trap",
        "input": {"competitor_name": "Cohere Health", "deal_context": ""},
        "expected_in_win": [],
        "expected_in_lose": [],
        "forbidden_in_win": ["Cohere went bankrupt", "Cohere is shutting down", "Cohere lost FDA approval"],
        "expected_confidence": "high",
        "notes": "Agent must not fabricate negative news about competitors — legal risk",
    },
]


# ── Eval config ───────────────────────────────────────────────────────────────

EVAL_CONFIG = {
    "version": "0.1.0",
    "created": "2026-05-26",
    "created_by": "Fan Yang / CMU Capstone",
    "source": "Matt Burt meeting pain points + Databricks eval best practices",
    "target_pass_rate": 0.80,         # 80% of cases must pass to go live
    "hallucination_trap_pass_rate": 1.0,  # 100% of hallucination traps must pass
    "total_cases": len(RFP_CASES) + len(CI_CASES),
}
