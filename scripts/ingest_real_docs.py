"""
Ingest REAL TruCare documentation (task #2, real-data run).

Reads the version folders under ~/Desktop/Study/Zyter/documentations/{v24.1,...}/*.pdf,
chunks each PDF, and stores into a SEPARATE Chroma collection "trucare_real" (keeps the
synthetic eval's "product_docs" collection clean for comparison).

Version comes from the FOLDER name (v25.1 -> "25.1") and is stored as versions_csv so the
existing tools.py version hard-filter works unchanged.

SECURITY: real docs live OUTSIDE the repo (in documentations/), and Chroma output is
gitignored. Nothing here gets committed. Matt cleared product documentation (not RFP).

Usage:
  PYTHONPATH=. python scripts/ingest_real_docs.py --filter Release_Notes   # small test batch
  PYTHONPATH=. python scripts/ingest_real_docs.py                          # FULL (195 PDFs, slow/$$)
  PYTHONPATH=. python scripts/ingest_real_docs.py --versions v24.1 v24.2   # specific versions
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, ".")

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
try:
    from langchain_core.documents import Document
except ImportError:
    from langchain.schema import Document

from app.agents import rag

DOCS_DIR = Path("/Users/fanyang/Desktop/Study/Zyter/documentations")
COLLECTION = "trucare_real"
ALL_VERSIONS = ["v24.1", "v24.2", "v25.1", "v25.2"]

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000, chunk_overlap=150,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def read_pdf(path: Path) -> str:
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        print(f"  [SKIP] {path.name}: {e}")
        return ""


def ingest(versions, name_filter=None):
    all_docs = []
    for v in versions:
        vnum = v.lstrip("v")                       # v25.1 -> 25.1
        folder = DOCS_DIR / v
        if not folder.exists():
            print(f"[skip] {v} not found"); continue
        pdfs = sorted(folder.glob("*.pdf"))
        if name_filter:
            pdfs = [p for p in pdfs if name_filter.lower() in p.name.lower()]
        print(f"{v}: {len(pdfs)} PDF(s)")
        for pdf in pdfs:
            text = read_pdf(pdf)
            if not text.strip():
                continue
            chunks = splitter.split_text(text)
            for ch in chunks:
                all_docs.append(Document(
                    page_content=f"[{vnum}] {ch}",
                    metadata={
                        "source": pdf.name,
                        "source_type": "guide",
                        "versions_csv": vnum,           # tools.py version hard-filter uses this
                        "version": vnum,
                        "freshness": "2026-06",
                    },
                ))
            print(f"  {pdf.name}: {len(chunks)} chunks")

    if not all_docs:
        print("nothing to ingest"); return
    print(f"\nembedding {len(all_docs)} chunks into '{COLLECTION}'...")
    vs = rag.get_vectorstore(COLLECTION)
    # batch to avoid oversized embedding requests
    B = 200
    for i in range(0, len(all_docs), B):
        vs.add_documents(all_docs[i:i+B])
        print(f"  {min(i+B, len(all_docs))}/{len(all_docs)}")
    print("done.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", nargs="+", default=ALL_VERSIONS)
    ap.add_argument("--filter", default=None, help="only ingest PDFs whose name contains this")
    args = ap.parse_args()
    ingest(args.versions, args.filter)
