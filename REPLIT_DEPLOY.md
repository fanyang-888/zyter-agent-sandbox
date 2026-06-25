# Deploy the Q&A Assistant to Replit (shareable demo link)

A public, clickable demo of the Document Q&A vector approach — to send stakeholders a **link
instead of a GitHub repo** (the 6/24 ask). Runs on **synthetic data only**.

## 🔒 Why this is safe to make public
- The real TruCare corpus (`documentations/`, `data/real/`, the `trucare_real` Chroma collection)
  is **gitignored** → it is **not in the GitHub repo**, so a Replit imported from the repo
  physically does not contain it.
- `scripts/replit_boot.sh` hard-pins `PRODUCT_DOCS_COLLECTION=product_docs` (the 28-chunk synthetic
  set) and rebuilds **only** the synthetic KB. **Do not change this to `trucare_real` on a public Replit.**
- Net: this link demos the *approach* (vector retrieval + version hard-filter + per-question cost),
  not real client data. The real-data version stays the local/controlled demo for internal review.

## ⚠️ Before you start: use a BUDGET-CAPPED API key
Anyone with the link can spend your API budget. Use the **shared, budget-limited keys Mel is setting
up (~$50 each)** — NOT your personal unlimited keys. You enter them as Replit *Secrets* (below); they
are never committed to the repo.

## Steps
1. **Get the deploy files into the repo.** They're new/safe (no data, no names). From `prototype/`:
   ```bash
   git add .replit scripts/replit_boot.sh .streamlit/config.toml REPLIT_DEPLOY.md
   git status          # REVIEW: confirm CONTEXT.md / PROJECT_LOG.md / data/ are NOT staged
   git commit -m "Add Replit deploy config (synthetic demo)"
   git push
   ```
   🚫 **Never `git add .`** — your working tree has a modified `CONTEXT.md` with real staff names.
   (Zero-push alternative: import the repo first, then create these 3 files in Replit's editor by paste.)

2. **Create the Replit:** replit.com → Create → **Import from GitHub** → `fanyang-888/zyter-agent-sandbox`.
   It auto-detects Python and installs `requirements.txt`.

3. **Add Secrets** (Tools → Secrets), using the budget-capped keys:
   - `ANTHROPIC_API_KEY` = `sk-ant-…`
   - `OPENAI_API_KEY` = `sk-…`  (only used to build the 28-chunk synthetic KB once)
   - *(optional)* `PRODUCT_DOCS_VARIANT` = `agentic` to demo the ReAct variant instead of baseline.

4. **Run.** First boot builds the synthetic KB (~1 min, one OpenAI ingest), then starts the backend +
   Streamlit. Open the webview, ask e.g. *"What changed between 24.2 and 25.1?"* to confirm.

5. **Publish the link:** Deploy → **Reserved VM** (always-on, simplest for the uvicorn+Streamlit pair).
   Copy the deployment URL — that's the link you send. (Autoscale is cheaper but cold-starts re-ingest.)

## Notes
- The demo's CP-ids (e.g. CP-100001) are **synthetic**, not real defects — expected.
- The RFP agent tab will be thin (its KB isn't built here); the **Document Q&A** tab is the demo.
- To also show the **per-question cost** on the link, additionally push the (safe, code-only) updated
  `app/agents/product_docs/{baseline,agentic,tools}.py`, `app/agents/rag.py`, `app/main.py`,
  `app/streamlit_app.py` — explicit `git add` of those files only, never `git add .`.
