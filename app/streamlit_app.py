"""
Streamlit UI — Zyter Internal Agent Sandbox (Sprint 1 prototype)

Two agents accessible from one interface:
  1. RFP & Discovery Prep
  2. Competitive Intelligence Brief

Run with: streamlit run app/streamlit_app.py
"""

import streamlit as st
import httpx
import json

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="Zyter Agent Sandbox",
    page_icon="🏥",
    layout="wide",
)

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
    user_id = st.text_input("Your name / ID", value="anonymous")
    st.caption("Used to save your output history")

    st.divider()
    st.markdown("**Knowledge base status**")
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=2)
        if r.status_code == 200:
            st.success("API connected ✅")
        else:
            st.warning("API returned error")
    except Exception:
        st.error("API offline — run `uvicorn app.main:app --reload`")


# ── Agent 1: RFP ──────────────────────────────────────────────────────────────

if agent_choice == "RFP & Discovery Prep":
    st.title("📋 RFP & Discovery Prep")
    st.markdown(
        "Paste an incoming RFP below. The agent will map each requirement to Zyter's "
        "portfolio, flag gaps, and produce a structured draft response."
    )

    rfp_text = st.text_area(
        "Paste RFP text here",
        height=250,
        placeholder="Paste the full RFP or a section of requirements...",
    )

    if st.button("Generate Draft Response", type="primary", disabled=not rfp_text.strip()):
        with st.spinner("Retrieving knowledge + drafting response..."):
            try:
                response = httpx.post(
                    f"{API_BASE}/agent/rfp",
                    json={"rfp_text": rfp_text, "user_id": user_id},
                    timeout=120,
                )
                response.raise_for_status()
                result = response.json()

                st.success("Draft complete")

                st.subheader("Summary")
                st.info(result["summary"])

                # Gaps banner
                if result.get("gaps"):
                    with st.expander(f"⚠️ {len(result['gaps'])} gap(s) — no Zyter coverage"):
                        for g in result["gaps"]:
                            st.markdown(f"- {g}")

                st.subheader("Section-by-Section Draft")
                for section in result.get("sections", []):
                    conf = section["confidence"]
                    color = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")
                    review_flag = " — **⚠️ REVIEW REQUIRED**" if section["flag_for_review"] else ""

                    with st.expander(f"{color} {section['section_title']}{review_flag}"):
                        st.markdown(section["draft_response"])
                        st.caption(f"Confidence: {conf}")

                # Sources
                with st.expander("📚 Knowledge sources used"):
                    for s in result.get("knowledge_sources", []):
                        st.markdown(f"- `{s}`")

                # Feedback
                st.divider()
                st.subheader("Rate this output")
                col1, col2 = st.columns([1, 3])
                with col1:
                    rating = st.slider("Quality (1-5)", 1, 5, 3)
                with col2:
                    if st.button("Submit Rating"):
                        httpx.post(
                            f"{API_BASE}/feedback",
                            json={"user_id": user_id, "agent": "rfp_agent",
                                  "rating": rating, "edited_sections": []},
                        )
                        st.success("Thanks — feedback recorded!")

            except httpx.HTTPStatusError as e:
                st.error(f"API error: {e.response.text}")
            except Exception as e:
                st.error(f"Error: {str(e)}")


# ── Agent 2: Competitive Intelligence ────────────────────────────────────────

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
            placeholder="e.g. Cohere Health, Freed, Ambience Healthcare",
        )
    with col2:
        deal_context = st.text_input(
            "Deal context (optional)",
            placeholder="e.g. Medicare Advantage, 100k members, UM focus",
        )

    if st.button("Generate Brief", type="primary", disabled=not competitor_name.strip()):
        with st.spinner("Retrieving intel + drafting brief..."):
            try:
                response = httpx.post(
                    f"{API_BASE}/agent/competitive",
                    json={
                        "competitor_name": competitor_name,
                        "deal_context": deal_context,
                        "user_id": user_id,
                    },
                    timeout=120,
                )
                response.raise_for_status()
                result = response.json()

                conf = result.get("confidence", "medium")
                conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")
                st.success(f"Brief complete — confidence: {conf_icon} {conf.upper()}")

                st.subheader("Executive Summary")
                st.info(result["executive_summary"])

                col_win, col_lose = st.columns(2)

                with col_win:
                    st.subheader("✅ Where We Win")
                    for w in result.get("where_we_win", []):
                        st.markdown(f"- {w}")

                with col_lose:
                    st.subheader("❌ Where We Lose")
                    for l in result.get("where_we_lose", []):
                        st.markdown(f"- {l}")

                st.divider()
                st.subheader("💬 Recommended Positioning")
                st.success(result["recommended_positioning"])

                with st.expander("📚 Knowledge sources used"):
                    for s in result.get("knowledge_sources", []):
                        st.markdown(f"- `{s}`")

                # Feedback
                st.divider()
                col1, col2 = st.columns([1, 3])
                with col1:
                    rating = st.slider("Quality (1-5)", 1, 5, 3, key="ci_rating")
                with col2:
                    if st.button("Submit Rating", key="ci_fb"):
                        httpx.post(
                            f"{API_BASE}/feedback",
                            json={"user_id": user_id, "agent": "ci_agent",
                                  "rating": rating, "edited_sections": []},
                        )
                        st.success("Thanks — feedback recorded!")

            except httpx.HTTPStatusError as e:
                st.error(f"API error: {e.response.text}")
            except Exception as e:
                st.error(f"Error: {str(e)}")
