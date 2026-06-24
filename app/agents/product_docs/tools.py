"""
Retrieval tools for the Product Documentation Chatbot (task #2).

These are the agent's HANDS — the agentic variant (agentic.py) lets Claude decide
which to call, with what versions, how many times. The baseline (baseline.py) calls
one of them once.

Each tool wraps rag.retrieve(collection_name="product_docs", filters=...). Version is
the HARD FILTER (Context-Engineering "Conflict" defense): a 25.1-vs-25.2 answer must
never surface a v24 chunk. Chroma metadata can't hold lists, so ingestion stores
`versions_csv` ("24.2,25.1") and we post-filter set-intersection here in code.
"""

import os

from app.agents import rag

# Which Chroma collection the tools read. Default = synthetic eval corpus.
# Set PRODUCT_DOCS_COLLECTION=trucare_real to run against real TruCare PDFs.
# Kept configurable so the synthetic comparison (baseline 7/7 vs agentic 5/7)
# stays reproducible while the real-data run uses a separate collection.
COLLECTION = os.getenv("PRODUCT_DOCS_COLLECTION", "product_docs")

# Real release-notes/guide PDFs are all ingested as source_type="guide" (there is
# no separate issue/row structure like the synthetic issues.csv). So on real data
# a source_type="issue" filter returns nothing. REAL_DATA flips search_issues to
# search the guide chunks instead, so a bug-status question still retrieves the
# release-note prose that describes the fix.
REAL_DATA = COLLECTION != "product_docs"


def _version_match(doc, asked: list[str]) -> bool:
    """True iff the doc's versions intersect the asked versions."""
    doc_versions = {v.strip() for v in doc.metadata.get("versions_csv", "").split(",") if v.strip()}
    return bool(doc_versions & set(asked))


def _cite(doc) -> dict:
    """Citation handle the model must carry back into the answer."""
    m = doc.metadata
    return {
        "text": doc.page_content,
        "cp_id": m.get("cp_id", ""),
        "source": m.get("source", ""),
        "versions": m.get("versions_csv", ""),
        "status": m.get("status", ""),
        "freshness": m.get("freshness", ""),
    }


# ── Tools (also exposed as Anthropic tool schemas below) ──────────────────────

def search_issues(query: str, versions: list[str], status: str = None) -> list[dict]:
    """Find known/resolved bugs scoped to the given versions.

    status: "known" | "resolved" | None (both). Version filter is hard.
    """
    # score_threshold=-1.0: Chroma can return negative relevance scores; version
    # is already a HARD filter, so don't let a score cutoff drop valid results.
    # Real data has no source_type="issue" chunks (release notes describe fixes in
    # prose), so on real data search the guide chunks instead and skip the
    # non-existent status metadata — otherwise this tool always returns empty.
    src_filter = {"source_type": "guide"} if REAL_DATA else {"source_type": "issue"}
    docs = rag.retrieve(query, collection_name=COLLECTION, k=10,
                        score_threshold=-1.0, filters=src_filter)
    out = [d for d in docs if _version_match(d, versions)]
    if status and not REAL_DATA:
        out = [d for d in out if d.metadata.get("status") == status]
    return [_cite(d) for d in out]


def search_features(query: str, versions: list[str]) -> list[dict]:
    """Find new/changed features scoped to the given versions. Version filter is hard."""
    docs = rag.retrieve(query, collection_name=COLLECTION, k=10,
                        score_threshold=-1.0, filters={"source_type": "guide"})
    out = [d for d in docs if _version_match(d, versions)]
    return [_cite(d) for d in out]


def compare(area: str, version_a: str, version_b: str) -> dict:
    """Side-by-side feature pull for two versions — the multi-hop comparison primitive."""
    return {
        version_a: search_features(area, [version_a]),
        version_b: search_features(area, [version_b]),
    }


# ── Anthropic tool-use schemas (bound by the agentic variant) ─────────────────

TOOL_SCHEMAS = [
    {
        "name": "search_issues",
        "description": "Find known or resolved bugs/issues scoped to specific TruCare versions. "
                       "Use for questions about bugs, defects, what's broken, what's fixed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "what to search for"},
                "versions": {"type": "array", "items": {"type": "string"},
                             "description": "versions to scope to, e.g. ['25.1','25.2']"},
                "status": {"type": "string", "enum": ["known", "resolved"],
                           "description": "optional: only known (open) or only resolved issues"},
            },
            "required": ["query", "versions"],
        },
    },
    {
        "name": "search_features",
        "description": "Find new or changed features/functionality scoped to specific TruCare "
                       "versions. Use for 'what's new', 'what changed', capability questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "versions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query", "versions"],
        },
    },
    {
        "name": "compare",
        "description": "Pull features for two versions side-by-side to compare them. "
                       "Use when the user asks what changed BETWEEN two versions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "area": {"type": "string", "description": "feature area or module to compare"},
                "version_a": {"type": "string"},
                "version_b": {"type": "string"},
            },
            "required": ["area", "version_a", "version_b"],
        },
    },
]

# Dispatch table: tool name -> callable
TOOL_FNS = {
    "search_issues": search_issues,
    "search_features": search_features,
    "compare": compare,
}
