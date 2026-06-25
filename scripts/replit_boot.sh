#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Replit boot — SYNTHETIC-DATA demo ONLY.
#
# SAFETY: this host is PUBLIC (anyone with the link can reach it). It must NEVER
# serve real TruCare data. Two guards make that structural, not a promise:
#   1) The real corpus (documentations/, data/real/, the trucare_real Chroma
#      collection) is gitignored, so it is not in the GitHub repo this Replit is
#      imported from — it physically isn't here.
#   2) We hard-pin PRODUCT_DOCS_COLLECTION=product_docs (the synthetic set) below
#      and rebuild only the synthetic KB. Do not change this on a public Replit.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

export PYTHONPATH=.
export PRODUCT_DOCS_COLLECTION=product_docs   # synthetic only — never trucare_real on a public link
export PRODUCT_DOCS_VARIANT="${PRODUCT_DOCS_VARIANT:-baseline}"   # baseline by default; set =agentic in Secrets to switch
export LANGCHAIN_TRACING_V2=false             # no LangSmith (avoids 403 noise)

# 1) Build the synthetic knowledge base on first boot. chroma_db/ is gitignored, so a
#    freshly imported Replit has none → ingest the 28 synthetic chunks (needs OPENAI_API_KEY).
if [ ! -d chroma_db ] || [ -z "$(ls -A chroma_db 2>/dev/null || true)" ]; then
  echo ">> First boot: building the SYNTHETIC knowledge base…"
  python scripts/ingest_product_docs.py
fi

# 2) Backend (internal only, 127.0.0.1) + Streamlit on the public port.
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
echo ">> waiting for backend to come up…"
for _ in $(seq 1 40); do
  curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && { echo ">> backend ready"; break; }
  sleep 1
done

exec streamlit run app/streamlit_app.py \
  --server.address 0.0.0.0 --server.port "${PORT:-8501}" \
  --server.headless true --server.enableCORS false --server.enableXsrfProtection false
