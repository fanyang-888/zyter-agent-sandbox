"""
Version-aware ingestion for the Product Documentation Chatbot (task #2, Step 1).

Issues  → row-as-chunk (one issue = one chunk), metadata carries versions + status.
Guides  → section-as-chunk (one feature = one chunk), metadata carries the version.

Chroma metadata can't hold lists, so versions are stored as `versions_csv` ("24.2,25.1")
and tools.py post-filters set-intersection. One collection: "product_docs".

Run:  python scripts/ingest_product_docs.py   (needs OPENAI_API_KEY for embeddings)
"""

import csv
import re
from pathlib import Path

try:
    from langchain_core.documents import Document
except ImportError:
    from langchain.schema import Document

from app.agents import rag

DATA = Path("data/synthetic")
COLLECTION = "product_docs"
FRESHNESS = "2026-06"


def build_issue_docs() -> list[Document]:
    docs = []
    with open(DATA / "issues.csv") as f:
        for row in csv.DictReader(f):
            impacted = row["impacted_versions"].split()
            resolved = row["resolved_version"].strip()
            versions = sorted(set(impacted + ([resolved] if resolved else [])))
            docs.append(Document(
                page_content=(f"Issue {row['cp_id']}: {row['description']} "
                              f"(platform: {row['platform']}; "
                              f"impacted: {', '.join(impacted)}; "
                              f"resolved in: {resolved or 'not yet resolved'})"),
                metadata={
                    "source": "issues.csv",
                    "source_type": "issue",
                    "cp_id": row["cp_id"],
                    "versions_csv": ",".join(versions),
                    "resolved_in": resolved,
                    "status": "resolved" if resolved else "known",
                    "freshness": FRESHNESS,
                },
            ))
    return docs


def build_guide_docs() -> list[Document]:
    docs = []
    for md in sorted(DATA.glob("release_notes_*.md")):
        version = md.stem.replace("release_notes_", "")
        # one chunk per ### feature heading
        sections = re.split(r"\n### ", md.read_text())
        for sec in sections[1:]:
            title = sec.split("\n", 1)[0].strip()
            docs.append(Document(
                page_content=f"[{version}] {title}\n{sec.strip()}",
                metadata={
                    "source": md.name,
                    "source_type": "guide",
                    "versions_csv": version,
                    "feature": title,
                    "freshness": FRESHNESS,
                },
            ))
    return docs


def ingest():
    issue_docs = build_issue_docs()
    guide_docs = build_guide_docs()
    all_docs = issue_docs + guide_docs

    vs = rag.get_vectorstore(COLLECTION)
    vs.add_documents(all_docs)

    print(f"Ingested {len(all_docs)} chunks into '{COLLECTION}':")
    print(f"  issues: {len(issue_docs)}  |  guide features: {len(guide_docs)}")
    # manifest check: print version distribution
    from collections import Counter
    vc = Counter()
    for d in all_docs:
        for v in d.metadata["versions_csv"].split(","):
            vc[v] += 1
    print("  version distribution:", dict(sorted(vc.items())))


if __name__ == "__main__":
    ingest()
