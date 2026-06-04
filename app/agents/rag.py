"""
Shared RAG layer for all Zyter agents.

Implements:
  - Hybrid search: semantic similarity + metadata filters
  - "Lost in the Middle" reranking: highest-scored docs at top and bottom of context
  - Freshness check: flags stale docs (>30 days) before they poison LLM context
  - Source citation: every chunk carries doc_type, team, freshness metadata

Collections:
  - "universal"         -> product docs, battle cards, sales playbooks (all agents)
  - "rfp_archive"       -> past RFP responses (RFP agent only)
  - "competitive_intel" -> win/loss notes, competitor snapshots (CI agent only)

Context Engineering defenses (from agentic-tech.md):
  Poisoning  → freshness_days check flags stale content before it enters context
  Distraction → score_threshold=0.5 (raised from 0.3) cuts irrelevant noise
  Confusion  → standardized chunk format with mandatory source + metadata header
  Conflict   → source citations surface to user so human can adjudicate
"""

import os
from datetime import datetime, date
from typing import Optional

from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document

load_dotenv()

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
EMBEDDING_MODEL = "text-embedding-3-large"
FRESHNESS_WARN_DAYS = 30   # flag docs not updated in 30+ days


def get_embeddings():
    return OpenAIEmbeddings(model=EMBEDDING_MODEL)


def get_vectorstore(collection_name: str = "universal") -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_PERSIST_DIR,
    )


def _is_stale(doc: Document) -> bool:
    """Returns True if the doc's freshness date is older than FRESHNESS_WARN_DAYS."""
    freshness_str = doc.metadata.get("freshness", "")
    if not freshness_str:
        return False
    try:
        doc_date = datetime.strptime(freshness_str, "%Y-%m").date().replace(day=1)
        delta = (date.today() - doc_date).days
        return delta > FRESHNESS_WARN_DAYS
    except ValueError:
        return False


def retrieve(
    query: str,
    collection_name: str = "universal",
    k: int = 5,
    score_threshold: float = 0.5,
    filters: Optional[dict] = None,
) -> list[Document]:
    """
    Hybrid search: semantic similarity + optional metadata filters.

    Args:
        query:           natural language search query
        collection_name: which Chroma collection to search
        k:               number of results to return
        score_threshold: minimum relevance score (0.5 default — raised from 0.3
                         to reduce Distraction failure mode)
        filters:         metadata filter dict, e.g. {"doc_type": "battle_card"}
                         or {"team": "sales"} — narrows results to matching docs

    Returns:
        List of Document objects, sorted high→low by score.
        Stale docs (>30 days) are flagged with metadata["stale"] = True
        but still returned — the LLM prompt will surface the warning to the user.
    """
    vs = get_vectorstore(collection_name)

    if filters:
        results = vs.similarity_search_with_relevance_scores(
            query, k=k, filter=filters
        )
    else:
        results = vs.similarity_search_with_relevance_scores(query, k=k)

    # Filter by score threshold and tag stale docs
    filtered = []
    for doc, score in results:
        if score < score_threshold:
            continue
        doc.metadata["relevance_score"] = round(score, 3)
        doc.metadata["stale"] = _is_stale(doc)
        filtered.append(doc)

    # Sort descending by score (highest-confidence docs will go first in context)
    filtered.sort(key=lambda d: d.metadata["relevance_score"], reverse=True)
    return filtered


def format_context(docs: list[Document], max_chars: int = 8000) -> str:
    """
    Formats retrieved docs into a context block, applying "Lost in the Middle"
    reranking: most relevant docs placed at the START and END of context,
    less relevant docs in the middle.

    Also prepends a [STALE] warning for docs older than FRESHNESS_WARN_DAYS.
    This prevents stale data from silently poisoning the LLM output.

    Reference: Liu et al., TACL 2024 — accuracy drops ~20pp for docs in the
    middle of the context window vs. first/last positions.
    """
    if not docs:
        return "No relevant context found."

    # "Lost in the Middle" reranking:
    # interleave high→low so top docs land at index 0 and -1
    if len(docs) > 2:
        reranked = []
        lo, hi = 0, len(docs) - 1
        toggle = True
        while lo <= hi:
            if toggle:
                reranked.append(docs[lo]); lo += 1
            else:
                reranked.append(docs[hi]); hi -= 1
            toggle = not toggle
        docs = reranked

    parts = []
    total = 0
    for i, doc in enumerate(docs):
        source    = doc.metadata.get("source", "unknown")
        doc_type  = doc.metadata.get("doc_type", "")
        freshness = doc.metadata.get("freshness", "")
        stale     = doc.metadata.get("stale", False)

        stale_tag = " [⚠️ STALE — verify before using]" if stale else ""
        meta_line = f"source={source}"
        if doc_type:  meta_line += f" | type={doc_type}"
        if freshness: meta_line += f" | updated={freshness}{stale_tag}"

        chunk = f"[{meta_line}]\n{doc.page_content}\n"
        if total + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total += len(chunk)

    return "\n---\n".join(parts)


def get_stale_sources(docs: list[Document]) -> list[str]:
    """Returns list of stale source filenames for UI warning display."""
    return [
        doc.metadata.get("source", "unknown")
        for doc in docs
        if doc.metadata.get("stale", False)
    ]


# ── Knowledge base router ─────────────────────────────────────────────────────

def route(query: str) -> list[str]:
    """
    Classifies query intent and returns which collections to search.

    Uses keyword heuristics for Sprint 1 — no extra LLM call, no latency cost.
    Sprint 2: replace with a lightweight Claude classifier once use cases stabilize.

    Always appends "universal" (product knowledge every agent needs).
    Returns a deduplicated list, universal last so it acts as fallback.

    Examples:
        route("RFI for Medicare Advantage plan")
            → ["rfp_archive", "universal"]
        route("Compare Zyter vs Cohere Health")
            → ["competitive_intel", "universal"]
        route("How does Symphony handle prior auth?")
            → ["universal"]
    """
    q = query.lower()
    collections: list[str] = []

    # RFI / RFP signals
    if any(w in q for w in [
        "rfi", "rfp", "proposal", "request for information",
        "request for proposal", "requirements", "vendor selection",
        "past response", "response template",
    ]):
        collections.append("rfp_archive")

    # Competitive intelligence signals
    if any(w in q for w in [
        "competitor", " vs ", "compare", "versus",
        "cohere", "freed", "ambience", "glean", "klue", "crayon",
        "win", "lose", "battle card", "differentiat",
    ]):
        collections.append("competitive_intel")

    # Universal is always included (product specs, battle cards, playbooks)
    if "universal" not in collections:
        collections.append("universal")

    return collections


def retrieve_routed(
    query: str,
    k: int = 5,
    filters: Optional[dict] = None,
) -> list[Document]:
    """
    Auto-routes query to relevant collections, merges and deduplicates results.

    Agents call this when they don't know which collection to use.
    Individual retrieve() calls remain available for explicit collection targeting.

    Deduplication: by chunk_hash metadata (set at ingest time).
    Re-sorts merged results by relevance_score descending.
    Returns at most k documents total.
    """
    collections = route(query)
    all_docs: list[Document] = []
    seen: set[str] = set()

    for col in collections:
        docs = retrieve(query, collection_name=col, k=k, filters=filters)
        for doc in docs:
            key = doc.metadata.get("chunk_hash") or doc.page_content[:80]
            if key not in seen:
                all_docs.append(doc)
                seen.add(key)

    all_docs.sort(key=lambda d: d.metadata.get("relevance_score", 0), reverse=True)
    return all_docs[:k]
