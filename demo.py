"""
UI demo — no backend, no API keys needed.
Run: streamlit run demo.py
"""

import streamlit as st
import time
from datetime import date

st.set_page_config(
    page_title="Zyter Agent Sandbox",
    page_icon="🏥",
    layout="wide",
)

# ── Mock data ─────────────────────────────────────────────────────────────────

MOCK_RFP_RESULT = {
    "summary": (
        "This RFP is seeking a care management platform with prior authorization automation, "
        "EHR integration, and real-time clinical decision support for a Medicare Advantage plan. "
        "Zyter's Symphony + Praxis UM stack covers the core workflow requirements; "
        "Epic integration and the SSO requirement need SE confirmation before committing."
    ),
    "sections": [
        {
            "section_title": "Automated prior authorization workflow",
            "draft_response": (
                "Zyter Praxis UM automates prior authorization end-to-end using the "
                "SENSE→THINK→ACT loop. Clinical charts are matched against MCG/InterQual "
                "guidelines via GraphRAG retrieval, producing an approval recommendation "
                "with an audit trail. Reference: CMS WISeR deployment achieved 80–90% "
                "auto-approval rates within 8 weeks of go-live."
            ),
            "confidence": "high",
            "flag_for_review": False,
            "grounded_claims": ["80–90% auto-approval", "8 weeks to production", "MCG/InterQual"],
            "unverified_claims": [],
            "sources_used": ["universal_zyter_product_overview.txt"],
        },
        {
            "section_title": "Epic EHR integration",
            "draft_response": (
                "Symphony's Enterprise Integration layer supports HL7 FHIR-based connectors. "
                "Confirm with SE whether a certified Epic connector is available in the current "
                "release or requires custom integration work. Do not commit to timeline without "
                "engineering sign-off."
            ),
            "confidence": "medium",
            "flag_for_review": True,
            "grounded_claims": ["FHIR-based connectors"],
            "unverified_claims": ["certified Epic connector availability"],
            "sources_used": ["universal_zyter_product_overview.txt"],
        },
        {
            "section_title": "Real-time clinical decision support",
            "draft_response": (
                "Praxis surfaces decision support at each workflow node via the ReAct reasoning "
                "loop. Care managers and UM reviewers see inline recommendations with confidence "
                "scores. Human-in-the-loop checkpoints are configurable — low-confidence outputs "
                "are held for review before advancing the workflow."
            ),
            "confidence": "high",
            "flag_for_review": False,
            "grounded_claims": ["ReAct reasoning loop", "human-in-the-loop checkpoints", "confidence scores"],
            "unverified_claims": [],
            "sources_used": ["universal_zyter_product_overview.txt"],
        },
        {
            "section_title": "SSO with Azure Active Directory",
            "draft_response": (
                "Pending confirmation of identity provider config. Zyter's sandbox uses Cognito "
                "with OIDC. Azure AD federation via SAML/OIDC is technically feasible but needs "
                "IT/infra confirmation before committing to the RFP."
            ),
            "confidence": "low",
            "flag_for_review": True,
            "grounded_claims": ["Cognito with OIDC"],
            "unverified_claims": ["Azure AD SAML federation in current release"],
            "sources_used": [],
        },
        {
            "section_title": "Utilization reporting dashboard",
            "draft_response": (
                "The Adoption Measurement Dashboard tracks agent invocations, task completion "
                "rates, and time savings by care manager and department. Export to standard "
                "formats (CSV, PDF) is supported. Custom KPIs can be configured at implementation."
            ),
            "confidence": "medium",
            "flag_for_review": False,
            "grounded_claims": ["agent invocations", "time savings tracking"],
            "unverified_claims": ["CSV/PDF export", "custom KPIs"],
            "sources_used": ["universal_zyter_product_overview.txt"],
        },
    ],
    "gaps": [
        "HIPAA BAA countersigning process — requires Legal review, not a product feature",
    ],
    "knowledge_sources": [
        {
            "file": "universal_zyter_product_overview.txt",
            "doc_type": "product_spec",
            "freshness": "2026-05",
            "stale": False,
        },
        {
            "file": "rfp_past_responses_2024.pdf",
            "doc_type": "rfp_response",
            "freshness": "2024-11",
            "stale": True,
        },
    ],
    "eval_flags": {
        "groundedness_score": "87%",
        "hallucination_risk": "low",
        "stale_sources": ["rfp_past_responses_2024.pdf"],
    },
}

MOCK_CI_RESULT = {
    "competitor": "Cohere Health",
    "confidence": "high",
    "executive_summary": (
        "Cohere Health dominates the prior authorization automation market with $240M ARR "
        "and hard outcome metrics (85% auto-approval, 70% faster access to care). "
        "Zyter competes on governance depth and platform breadth — Symphony covers the full "
        "orchestration layer beyond just PA, while Cohere is a point solution. "
        "Win this deal by leading with audit trail and multi-workflow coverage, not PA speed alone."
    ),
    "where_we_win": [
        "Full orchestration layer: Symphony coordinates agents, humans, and systems — Cohere is PA-only",
        "Governance + audit trail: every Symphony decision is logged and explainable; regulatory buyers care",
        "Configurable human-in-the-loop: confidence thresholds adjustable per workflow; Cohere is more black-box",
        "Platform expansion path: Praxis UM + CM + Clinical Encounter on one platform vs. point solution sprawl",
    ],
    "where_we_lose": [
        "Brand recognition in PA automation: Cohere has 240M ARR and named outcomes; Zyter has fewer public references",
        "Speed-to-value perception: Cohere's 'plug in and get 85% auto-approval' is a simpler pitch than Symphony's orchestration story",
        "Physician UX: Cohere has 94% physician satisfaction scores; Zyter has limited published provider-facing metrics",
    ],
    "recommended_positioning": (
        "Cohere solves one workflow. Symphony runs your entire operation — "
        "and every workflow you add makes the system smarter."
    ),
    "knowledge_sources": [
        "universal_zyter_product_overview.txt",
        "ci_competitor_notes.txt",
    ],
}

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🏥 Zyter Agent Sandbox")
    st.caption("Sprint 1 prototype — internal use only")
    st.divider()

    agent_choice = st.radio(
        "Select Agent",
        ["RFP & Discovery Prep", "Competitive Intelligence"],
    )

    st.divider()
    user_id = st.text_input("Your name / ID", value="fan.yang")
    st.caption("Used to save your output history")

    st.divider()
    st.markdown("**Knowledge base**")
    st.success("2 documents indexed ✅")
    st.caption("universal_zyter_product_overview.txt\nrfp_past_responses_2024.pdf")

    st.divider()
    st.markdown("**Hybrid search filters**")
    filter_doc_type = st.multiselect(
        "Doc type",
        ["product_spec", "battle_card", "rfp_response", "sales_playbook", "win_loss"],
        default=[],
        help="Leave empty to search all doc types",
    )
    filter_team = st.multiselect(
        "Team",
        ["sales", "engineering", "product", "operations", "all"],
        default=[],
        help="Filter by team-specific knowledge",
    )
    if filter_doc_type or filter_team:
        st.caption(f"Active filters: {filter_doc_type + filter_team}")

    st.divider()
    st.info("📌 Demo mode — using mock data")


# ── Agent 1: RFP ──────────────────────────────────────────────────────────────

if agent_choice == "RFP & Discovery Prep":
    st.title("📋 RFP & Discovery Prep")
    st.markdown(
        "Paste an incoming RFP. The agent maps each requirement to Zyter's portfolio, "
        "flags coverage gaps, and drafts a structured response."
    )

    rfp_text = st.text_area(
        "Paste RFP text here",
        height=220,
        value=(
            "We are seeking a Care Management platform with the following capabilities:\n"
            "1. Automated prior authorization workflow for Medicare Advantage members\n"
            "2. Integration with Epic EHR for patient data ingestion\n"
            "3. Real-time clinical decision support during care manager workflows\n"
            "4. HIPAA-compliant data storage and audit logging\n"
            "5. SSO integration with Azure Active Directory\n"
            "6. Reporting dashboard for utilization metrics by care manager"
        ),
    )

    if st.button("Generate Draft Response", type="primary"):
        with st.spinner("Retrieving knowledge + drafting response..."):
            time.sleep(2)

        result = MOCK_RFP_RESULT

        # ── Eval flags banner ─────────────────────────────────────────────────
        ef = result.get("eval_flags", {})
        col_g, col_h, col_s = st.columns(3)
        with col_g:
            st.metric("Groundedness", ef.get("groundedness_score", "—"),
                      help="% of claims backed by knowledge base sources")
        with col_h:
            risk = ef.get("hallucination_risk", "unknown")
            risk_color = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk, "⚪")
            st.metric("Hallucination risk", f"{risk_color} {risk.upper()}")
        with col_s:
            stale = ef.get("stale_sources", [])
            st.metric("Stale sources", len(stale),
                      delta=f"{len(stale)} need refresh" if stale else None,
                      delta_color="inverse")

        if stale:
            st.warning(f"⚠️ Stale knowledge detected: `{'`, `'.join(stale)}` — verify stats before sending to client")

        st.divider()
        st.subheader("Summary")
        st.info(result["summary"])

        if result.get("gaps"):
            with st.expander(f"⚠️ {len(result['gaps'])} gap(s) — no Zyter coverage found"):
                for g in result["gaps"]:
                    st.markdown(f"- {g}")

        st.subheader("Section-by-Section Draft")

        for section in result["sections"]:
            conf = section["confidence"]
            color = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")
            review_tag = "  ⚠️ **REVIEW REQUIRED**" if section["flag_for_review"] else ""

            with st.expander(f"{color} {section['section_title']}{review_tag}"):
                st.markdown(section["draft_response"])

                # Groundedness breakdown
                grounded   = section.get("grounded_claims", [])
                unverified = section.get("unverified_claims", [])

                if grounded or unverified:
                    st.divider()
                    gcol, ucol = st.columns(2)
                    with gcol:
                        if grounded:
                            st.markdown("**✅ Grounded claims**")
                            for c in grounded:
                                st.caption(f"• {c}")
                    with ucol:
                        if unverified:
                            st.markdown("**⚠️ Unverified — check before sending**")
                            for c in unverified:
                                st.caption(f"• {c}")

                st.caption(f"Confidence: {conf.upper()}  |  Sources: {', '.join(section.get('sources_used', ['-']))}")

        with st.expander("📚 Knowledge sources used"):
            for s in result.get("knowledge_sources", []):
                if isinstance(s, dict):
                    stale_tag = " ⚠️ STALE" if s.get("stale") else " ✅"
                    st.markdown(
                        f"- `{s['file']}` — {s.get('doc_type','?')} | "
                        f"updated {s.get('freshness','?')}{stale_tag}"
                    )
                else:
                    st.markdown(f"- `{s}`")

        st.divider()
        st.subheader("Rate this output")
        col1, col2 = st.columns([1, 3])
        with col1:
            rating = st.select_slider(
                "Quality",
                options=["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"],
                value="⭐⭐⭐⭐",
            )
        with col2:
            if st.button("Submit Rating"):
                st.success("Thanks — feedback recorded!")


# ── Agent 2: Competitive Intelligence ─────────────────────────────────────────

elif agent_choice == "Competitive Intelligence":
    st.title("🔍 Competitive Intelligence Brief")
    st.markdown(
        "Enter a competitor name and optional deal context. The agent retrieves Zyter's "
        "battle cards and produces a structured win/loss brief."
    )

    col1, col2 = st.columns(2)
    with col1:
        competitor_name = st.text_input(
            "Competitor name",
            value="Cohere Health",
        )
    with col2:
        deal_context = st.text_input(
            "Deal context (optional)",
            value="Medicare Advantage, 100k members, prior authorization automation RFP",
        )

    if st.button("Generate Brief", type="primary"):
        with st.spinner("Retrieving intel + drafting brief..."):
            time.sleep(2)

        result = MOCK_CI_RESULT

        conf = result["confidence"]
        conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")

        st.success(f"Brief complete — confidence: {conf_icon} {conf.upper()}")
        st.divider()

        st.subheader("Executive Summary")
        st.info(result["executive_summary"])

        col_win, col_lose = st.columns(2)

        with col_win:
            st.subheader("✅ Where We Win")
            for w in result["where_we_win"]:
                st.markdown(f"- {w}")

        with col_lose:
            st.subheader("❌ Where We Lose")
            for l in result["where_we_lose"]:
                st.markdown(f"- {l}")

        st.divider()
        st.subheader("💬 Recommended Positioning")
        st.success(f'"{result["recommended_positioning"]}"')

        with st.expander("📚 Knowledge sources used"):
            for s in result["knowledge_sources"]:
                st.markdown(f"- `{s}`")

        st.divider()
        col1, col2 = st.columns([1, 3])
        with col1:
            rating = st.select_slider(
                "Quality",
                options=["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"],
                value="⭐⭐⭐⭐",
                key="ci_rating",
            )
        with col2:
            if st.button("Submit Rating", key="ci_fb"):
                st.success("Thanks — feedback recorded!")
