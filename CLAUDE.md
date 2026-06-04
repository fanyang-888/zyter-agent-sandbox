# Zyter Internal Agent Sandbox — Prototype

CMU AIM Capstone Project 17 × Zyter|TruCare.
Sprint 1 local prototype: RAG pipeline + two agents (RFP & CI).

## Project context

- **What**: Internal AI agent sandbox for Zyter employees — pre-built workflows grounded in Zyter's product knowledge base
- **Stack**: Python · FastAPI · Streamlit · LangGraph · Chroma (local) → Pinecone (MVP) · Claude API · AWS Lambda/S3 (MVP)
- **Sprint 1 scope**: Local prototype only — RFP agent + CI agent + eval dataset. AWS migration in Sprint 2.
- **Domain docs**: See `CONTEXT.md` for domain language, `docs/adr/` for architecture decisions

## Agent skills

### Issue tracker

Issues live in the GitHub repo under Zyter org (private). See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-label vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` at repo root + `docs/adr/`. See `docs/agents/domain.md`.
