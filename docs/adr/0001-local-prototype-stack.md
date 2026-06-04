# ADR-0001: Local-first prototype stack (Sprint 1)

**Status**: Accepted  
**Date**: 2026-05-26  
**Deciders**: Fan Yang, Smridhi (CMU Capstone Team)

## Context

Sprint 1 has no AWS sandbox access and no real Zyter internal documents.
We need a working prototype that can be demoed to Matt Burt by June 6
without any external dependencies beyond API keys.

## Decision

Use a fully local stack for Sprint 1:

- **Vector store**: Chroma (local, `./chroma_db/`) — no cloud needed
- **LLM**: Claude API via Anthropic SDK (direct, no AWS Bedrock)
- **Orchestration**: LangChain LCEL sequential chain (V1 pattern) — LangGraph DAG deferred to Sprint 2
- **Backend**: FastAPI running locally on port 8000
- **Frontend**: Streamlit running locally on port 8501
- **Observability**: LangSmith (optional, gracefully disabled if key absent)
- **Knowledge base**: Public Zyter website content as placeholder; swap to real docs when SharePoint access granted

## Consequences

**Positive:**
- Zero blockers — can build and demo today
- Architecture is swap-ready: Chroma → Pinecone, local FastAPI → Lambda are one-file changes
- Agent logic (`rfp_agent.py`, `competitive_intel_agent.py`) does not change between prototype and MVP

**Negative:**
- Demo uses placeholder data — stats may differ from real Zyter knowledge base
- No multi-user isolation (single user assumed locally)
- No auth — Sprint 2 adds Cognito SSO

## Migration path (Sprint 2)

| Prototype | MVP |
|-----------|-----|
| Chroma local | Pinecone |
| FastAPI local | Lambda + API Gateway |
| Streamlit local | Streamlit on Render |
| `.env` keys | AWS Secrets Manager |
| SQLite checkpointer | RDS PostgreSQL |
