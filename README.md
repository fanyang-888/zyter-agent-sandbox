# Zyter Internal Agent Sandbox — Sprint 1 Prototype

Local RAG pipeline with two agents. No AWS needed to run this.

## What's inside

| File | What it does |
|------|--------------|
| `app/agents/rag.py` | Shared RAG layer — all agents read from here |
| `app/agents/rfp_agent.py` | Agent 1: RFP & Discovery Prep |
| `app/agents/product_docs/baseline.py` | Agent 2: Document Q&A — **baseline** (fixed-chain) variant, the chosen impl |
| `app/agents/product_docs/agentic.py` | Agent 2 — **agentic** variant (ReAct loop, plans its own retrieval); the comparison arm |
| `app/agents/product_docs/tools.py` | Version-filtered retrieval tools — the **version hard-filter** (no cross-version fact mixing) |
| `eval/product_docs_eval.py` | Baseline-vs-agentic eval (golden Q&A) — the "explore different agent designs" deliverable |
| `app/main.py` | FastAPI backend (routes to agents) |
| `app/streamlit_app.py` | Streamlit UI (the clickable demo) |
| `scripts/setup_kb.py` | Builds the Chroma knowledge base from source_docs/ |
| `source_docs/` | Drop knowledge docs here (see naming convention below) |

## Setup

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API keys
cp .env.example .env
# Edit .env and add:
#   ANTHROPIC_API_KEY=...
#   OPENAI_API_KEY=...      (for embeddings only)
#   LANGCHAIN_API_KEY=...   (optional — LangSmith tracing)

# 4. Add source documents (see naming convention below)
# Then build the knowledge base:
python scripts/setup_kb.py
```

## Adding knowledge documents

Two separate ingestion paths — they don't share a directory or a script:

**`source_docs/` + `python scripts/setup_kb.py`** — universal + RFP knowledge.
Name your files with the right prefix so they go into the correct collection:

| Filename prefix | Collection | Used by |
|----------------|------------|---------|
| `universal_*` | universal | All agents |
| `rfp_*` | rfp_archive | RFP agent only |
| (no prefix) | universal | All agents |

```
source_docs/
  universal_zyter_product_overview.txt   ← already included (placeholder)
  universal_zyter_battle_cards.pdf       ← add when received from Matt
  rfp_past_responses_2024.pdf            ← add when received from SharePoint
```

**`data/synthetic/` + `python scripts/ingest_product_docs.py`** — Document Q&A
Assistant knowledge (version-tagged release notes + the known-issues CSV). See that
script's docstring for the expected file shape. This synthetic corpus is what ships
in the repo.

**`scripts/ingest_real_docs.py`** — ingests real product-documentation PDFs from a local
`documentations/{v24.1,v24.2,...}/` folder into a separate `trucare_real` collection (version
comes from the folder name). Real PDFs and the Chroma store are **gitignored** — only the
synthetic data lives in the repo. The agent's collection is selectable via the
`PRODUCT_DOCS_COLLECTION` env var (default `product_docs`).

Re-run `python scripts/setup_kb.py` after adding new files. It skips already-indexed chunks.

## Running the app

Open two terminal windows:

**Terminal 1 — API backend:**
```bash
uvicorn app.main:app --reload
```

**Terminal 2 — Streamlit UI:**
```bash
streamlit run app/streamlit_app.py
```

Open http://localhost:8501 in your browser.

## Testing agents directly (no UI)

```bash
# Test RFP agent
python -m app.agents.rfp_agent

# Test Document Q&A Assistant (baseline variant)
python -m app.agents.product_docs.baseline

# Verify the agentic graph compiles (no API key needed)
python -m app.agents.product_docs.agentic

# Run the baseline-vs-agentic comparison (needs API keys + an ingested collection)
python eval/product_docs_eval.py
```

## Architecture

```
Streamlit UI (port 8501)
       ↓ HTTP
FastAPI Backend (port 8000)
       ↓
Agent Logic (SENSE → THINK → ACT)
       ↓
Chroma (local vector store)   ←── source_docs/ (your knowledge base)
       ↓
Claude API (THINK step)
       ↓
LangSmith (tracing, optional)
```

## Sprint 2: AWS migration path

When AWS sandbox is provisioned:
- Chroma → Pinecone (swap `rag.py` vector store only)
- FastAPI local → Lambda + API Gateway
- Streamlit local → Streamlit on Render
- .env keys → AWS Secrets Manager
- SQLite checkpointer → RDS PostgreSQL (for LangGraph V2)

The agent logic (`rfp_agent.py`, `product_docs/baseline.py`) does **not change** 
between prototype and MVP. Only the infrastructure layer changes.
