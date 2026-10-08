"""
Tiny RAG engine (no model downloads, works offline).

* Loads .txt / .md / .pdf files from backend/rag_docs/
* Splits them into overlapping chunks
* Retrieves with TF-IDF + cosine similarity (scikit-learn)
* Sends the top chunks to the LLM to write the answer (or returns the chunks if no LLM)

Want embeddings + ChromaDB instead? Replace `_retrieve()` only - the rest stays the same.
"""
from pathlib import Path
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import config, llm

CHUNK_WORDS = 160
OVERLAP_WORDS = 30

_chunks: List[dict] = []      # {"source": str, "text": str}
_vectorizer = None
_matrix = None


def _read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return path.read_text(encoding="utf-8", errors="ignore")


def _split(text: str) -> List[str]:
    words = text.split()
    out, i = [], 0
    while i < len(words):
        out.append(" ".join(words[i:i + CHUNK_WORDS]))
        i += CHUNK_WORDS - OVERLAP_WORDS
    return [c for c in out if len(c.split()) > 5]


def build_index() -> dict:
    """(Re)build the index from every document in rag_docs/."""
    global _chunks, _vectorizer, _matrix
    _chunks = []
    files = [p for p in Path(config.RAG_DOCS_DIR).glob("*") if p.suffix.lower() in {".txt", ".md", ".pdf"}]
    for p in files:
        try:
            for piece in _split(_read_file(p)):
                _chunks.append({"source": p.name, "text": piece})
        except Exception as e:
            print(f"[rag] could not read {p.name}: {e}")
    if _chunks:
        _vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        _matrix = _vectorizer.fit_transform([c["text"] for c in _chunks])
    else:
        _vectorizer = _matrix = None
    return {"documents": len(files), "chunks": len(_chunks)}


def _retrieve(question: str, k: int = 4) -> List[dict]:
    if _vectorizer is None:
        build_index()
    if _vectorizer is None:
        return []
    sims = cosine_similarity(_vectorizer.transform([question]), _matrix)[0]
    top = sims.argsort()[::-1][:k]
    return [{**_chunks[i], "score": float(sims[i])} for i in top if sims[i] > 0]


def answer(question: str, language: str = "English") -> dict:
    hits = _retrieve(question)
    if not hits:
        return {"answer": "I could not find this in the loaded guidelines. "
                          "Call 112 (national emergency) or 1070 / 1077 (disaster control room).",
                "sources": [], "mode": "no-context"}

    context = "\n\n".join(f"[{h['source']}] {h['text']}" for h in hits)
    sources = sorted({h["source"] for h in hits})

    if llm.llm_enabled():
        try:
            system = (
                "You are a disaster-safety assistant. Answer ONLY from the provided context. "
                "Give short, numbered, actionable steps. If the context does not contain the answer, say so. "
                f"Reply in {language}. For life-threatening situations always remind the user to call 112."
            )
            text = llm.ask_llm(system, f"Context:\n{context}\n\nQuestion: {question}")
            return {"answer": text, "sources": sources, "mode": "rag+llm"}
        except Exception as e:
            print(f"[rag] LLM failed, returning raw passages: {e}")

    return {"answer": "Most relevant guidance found:\n\n" + "\n\n".join(h["text"] for h in hits[:2]),
            "sources": sources, "mode": "retrieval-only"}
