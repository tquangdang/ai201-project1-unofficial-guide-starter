import os
import re
import html
import glob
import random

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import chromadb
from groq import Groq

load_dotenv()

# ---- config ----
DOCS_DIR    = "documents"
CHUNK_SIZE  = 300          # characters
OVERLAP     = 80           # characters
TOP_K       = 5
MIN_CHUNK   = 40           # drop fragments shorter than this
EMBED_MODEL = "all-MiniLM-L6-v2"
GEN_MODEL   = "llama-3.3-70b-versatile"   

# strip lines that are pure RMP/forum boilerplate
_JUNK = re.compile(
    r"^(helpful|report|share|flag|rating|quality|difficulty|level of difficulty|"
    r"would take again|for credit|attendance( mandatory)?|textbook( used)?|"
    r"grade(?: received)?|tags|emoji ratings|\d+\s*ratings?|[\d.]+%?|yes|no|n/?a)\s*$",
    re.IGNORECASE,
)


def load_documents():
    """Read every .txt in docs/ -> [(source_filename, raw_text), ...]."""
    paths = sorted(glob.glob(os.path.join(DOCS_DIR, "*.txt")))
    if not paths:
        raise SystemExit(
            f"No .txt files in ./{DOCS_DIR}/. "
            "Add your collected reviews there first."
        )
    return [(os.path.basename(p), open(p, encoding="utf-8").read()) for p in paths]


def clean_text(text):
    """Unescape HTML entities and drop boilerplate lines. Intentionally light."""
    text = html.unescape(text)
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln and not _JUNK.match(ln)]
    out = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def chunk_text(text, source, size=CHUNK_SIZE, overlap=OVERLAP):
    """Sentence-aware packing to ~`size` chars with `overlap`-char carryover."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, cur = [], ""
    for s in sentences:
        if not s:
            continue
        if len(cur) + len(s) + 1 <= size:
            cur = (cur + " " + s).strip()
        else:
            if cur:
                chunks.append(cur)
            tail = chunks[-1][-overlap:] if (overlap and chunks) else ""
            cur = (tail + " " + s).strip() if tail else s
    if cur:
        chunks.append(cur)
    chunks = [c for c in chunks if len(c) >= MIN_CHUNK]
    return [{"text": c, "source": source, "idx": i} for i, c in enumerate(chunks)]


def build_store():
    """Build the in-memory Chroma collection. Returns (collection, embedder)."""
    embedder = SentenceTransformer(EMBED_MODEL)

    all_chunks = []
    for source, raw in load_documents():
        all_chunks += chunk_text(clean_text(raw), source)

    docs = sorted({c["source"] for c in all_chunks})
    print(f"Loaded {len(docs)} docs -> {len(all_chunks)} chunks")

    client = chromadb.Client()
    try:
        client.delete_collection("reviews")
    except Exception:
        pass
    coll = client.create_collection("reviews", metadata={"hnsw:space": "cosine"})

    embeddings = embedder.encode([c["text"] for c in all_chunks]).tolist()
    coll.add(
        ids=[f"{c['source']}-{c['idx']}" for c in all_chunks],
        documents=[c["text"] for c in all_chunks],
        metadatas=[{"source": c["source"], "idx": c["idx"]} for c in all_chunks],
        embeddings=embeddings,
    )

    print("\n=== 5 sample chunks (Milestone 3 checkpoint) ===")
    for c in random.sample(all_chunks, min(5, len(all_chunks))):
        print(f"\n--- {c['source']} #{c['idx']} ({len(c['text'])} chars) ---\n{c['text']}")

    return coll, embedder


def retrieve(collection, embedder, query, k=TOP_K):
    """Return top-k chunks: [{text, source, idx, distance}, ...]."""
    q = embedder.encode([query]).tolist()
    res = collection.query(query_embeddings=q, n_results=k)
    return [
        {"text": d, "source": m["source"], "idx": m["idx"], "distance": dist}
        for d, m, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        )
    ]


_SYS = (
    "You answer questions using ONLY the numbered context below. "
    'If the context does not contain the answer, reply exactly: '
    '"I don\'t have enough information on that." '
    "Do not use outside knowledge. Do not guess. "
    "When you do answer, mention which source the information came from."
)


def generate(query, hits):
    """Grounded answer from retrieved chunks. Sources appended programmatically."""
    context = "\n\n".join(
        f"[{i + 1}] (source: {h['source']}) {h['text']}" for i, h in enumerate(hits)
    )
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    resp = client.chat.completions.create(
        model=GEN_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": _SYS},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
    )
    answer = resp.choices[0].message.content.strip()
    sources = sorted({h["source"] for h in hits})
    return {"answer": answer, "sources": sources, "hits": hits}


# build the store once per process, reuse across queries
_STORE = None


def ask(query, k=TOP_K):
    global _STORE
    if _STORE is None:
        _STORE = build_store()
    collection, embedder = _STORE
    hits = retrieve(collection, embedder, query, k)
    return generate(query, hits)


if __name__ == "__main__":
    coll, emb = build_store()
    print("\n=== retrieval test (Milestone 4 checkpoint) ===")
    test_q = "which professor has the hardest exams?"
    print(f"Q: {test_q}")
    for h in retrieve(coll, emb, test_q):
        print(f"  {h['distance']:.3f}  {h['source']}#{h['idx']}  {h['text'][:90]}")
