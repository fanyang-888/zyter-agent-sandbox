# Domain Context — Zyter Internal Agent Sandbox

## What this system does

A RAG-powered internal agent sandbox for Zyter|TruCare employees. Non-technical staff
can run pre-built agent workflows (RFP drafting, competitive intelligence briefs,
live Q&A) grounded in Zyter's proprietary product knowledge base.

## Domain vocabulary

| Term | Meaning in this codebase |
|------|--------------------------|
| **Agent** | A SENSE→THINK→ACT workflow backed by RAG retrieval + Claude LLM call |
| **Knowledge base** | Chroma vectorstore (local) / Pinecone (MVP) fed by `source_docs/` |
| **Collection** | A named Chroma namespace: `universal`, `rfp_archive`, `competitive_intel` |
| **Template** | A versioned agent workflow definition (YAML for sequential, Python for LangGraph DAG) |
| **Capability card** | The `.md` sibling of each template — describes inputs, outputs, confidence thresholds, human checkpoints |
| **Grounded claim** | A factual assertion traceable to a specific chunk in the knowledge base |
| **Unverified claim** | An assertion in agent output with no matching source chunk — flag for human review |
| **Freshness** | The `YYYY-MM` timestamp on each source doc; docs >30 days old are flagged `stale` |
| **Confidence** | Per-section signal: `high` (well-sourced) / `medium` (partial) / `low` (thin) — low always triggers human review |
| **Human-in-the-loop** | Review checkpoint surfaced when confidence < threshold; Streamlit shows Approve/Reject/Edit |
| **Universal collection** | Knowledge shared across all agents: product specs, battle cards, sales playbooks |
| **Template-specific collection** | Knowledge scoped to one agent: `rfp_archive` (RFP agent), `competitive_intel` (CI agent) |
| **Sprint** | 2-week work cycle; team proposes scope, Zyter (Matt Burt) approves go/no-go |
| **MVP** | AWS-deployed version: Lambda + API Gateway + Pinecone + RDS PostgreSQL — targeted for Sprint 2+ |

## Key external systems

| System | Role |
|--------|------|
| **Zyter Symphony** | AI orchestration control plane (42 meta-agents, model-agnostic, 8-week production SLA) |
| **Zyter Praxis** | Workflow execution engine (SENSE→THINK→ACT→LEARN); all modules currently external-facing only |
| **SmartStart** | Zyter's pre-built template accelerator for clients — internal equivalent is what we're building |
| **Document 360** | Existing customer-facing doc tool — do NOT overlap |
| **LangSmith** | Observability + tracing for all LangChain/LangGraph runs |

## Architecture decisions

See `docs/adr/` for recorded decisions.

## Agents in scope (Sprint 1)

1. **RFP & Discovery Prep** (`app/agents/rfp_agent.py`) — maps RFP requirements to Zyter capabilities, flags gaps
2. **Competitive Intelligence Brief** (`app/agents/competitive_intel_agent.py`) — win/loss analysis vs named competitor

## Out of scope (Sprint 1)

- Agent Assist Q&A bot (Sprint 2)
- AWS deployment (Sprint 2)
- LangGraph V2 DAG with conditional branching (Sprint 2)
- Any PHI or real patient data — prototype uses public + synthetic data only
