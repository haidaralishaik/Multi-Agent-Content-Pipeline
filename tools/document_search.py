"""
Document Search Tool - PyPDF2 + FAISS semantic search

Extracts text from uploaded PDFs/text files, chunks them,
indexes them with FAISS, and retrieves relevant passages
for the Researcher agent.
"""

import io
import logging
import numpy as np
from collections import Counter
from typing import List, Dict, Optional

import faiss
import PyPDF2

logger = logging.getLogger(__name__)

CHUNK_SIZE = 500        # characters per chunk
CHUNK_OVERLAP = 100     # overlap between chunks
VOCAB_SIZE = 4096       # embedding dimension (top N words)
MIN_CHUNK_LEN = 60      # discard very short chunks


class DocumentIndexer:
    """
    Indexes uploaded documents with FAISS for semantic search.

    Pipeline:
      file bytes → PyPDF2 / plain text → chunks → TF-IDF vectors
      → FAISS IndexFlatIP (cosine similarity after L2 norm)
    """

    def __init__(self):
        self.chunks: List[str] = []
        self.index: Optional[faiss.IndexFlatIP] = None
        self.vocab: Dict[str, int] = {}
        self.doc_name: str = ""
        self.page_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, file_bytes: bytes, filename: str) -> int:
        """
        Extract, chunk, and index a document.

        Args:
            file_bytes: Raw bytes of the uploaded file.
            filename:   Original filename (used to detect PDF vs text).

        Returns:
            Number of chunks indexed.
        """
        self.doc_name = filename
        text = self._extract_text(file_bytes, filename)

        if not text.strip():
            logger.warning(f"No text extracted from {filename}")
            return 0

        self.chunks = self._chunk(text)
        if not self.chunks:
            return 0

        self.vocab = self._build_vocab(self.chunks)
        embeddings = np.array(
            [self._vectorize(c) for c in self.chunks], dtype=np.float32
        )
        faiss.normalize_L2(embeddings)

        self.index = faiss.IndexFlatIP(VOCAB_SIZE)
        self.index.add(embeddings)

        logger.info(f"Indexed '{filename}': {len(self.chunks)} chunks, {self.page_count} pages")
        return len(self.chunks)

    def search(self, query: str, k: int = 5) -> List[Dict]:
        """
        Retrieve the top-k most relevant chunks for a query.

        Returns list of dicts with keys: source, content, score.
        """
        if self.index is None or not self.chunks:
            return []

        q_vec = np.array([self._vectorize(query)], dtype=np.float32)
        faiss.normalize_L2(q_vec)

        k = min(k, len(self.chunks))
        scores, indices = self.index.search(q_vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and score > 0.05:   # filter near-zero relevance
                results.append({
                    "source": self.doc_name,
                    "content": self.chunks[idx],
                    "score": float(score),
                })
        return results

    def format_for_context(self, query: str, k: int = 5) -> str:
        """Return search results as a formatted string for the LLM context."""
        results = self.search(query, k=k)
        if not results:
            return ""

        lines = [f"## Relevant Passages from '{self.doc_name}'\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"**Passage {i}** (relevance: {r['score']:.2f}):")
            lines.append(r["content"])
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_text(self, file_bytes: bytes, filename: str) -> str:
        if filename.lower().endswith(".pdf"):
            return self._extract_pdf(file_bytes)
        # Plain text / markdown
        return file_bytes.decode("utf-8", errors="ignore")

    def _extract_pdf(self, file_bytes: bytes) -> str:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        self.page_count = len(reader.pages)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)

    def _chunk(self, text: str) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk = text[start:end].strip()
            if len(chunk) >= MIN_CHUNK_LEN:
                chunks.append(chunk)
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    def _build_vocab(self, chunks: List[str]) -> Dict[str, int]:
        all_words = " ".join(chunks).lower().split()
        most_common = Counter(all_words).most_common(VOCAB_SIZE)
        return {word: idx for idx, (word, _) in enumerate(most_common)}

    def _vectorize(self, text: str) -> np.ndarray:
        vec = np.zeros(VOCAB_SIZE, dtype=np.float32)
        for word in text.lower().split():
            idx = self.vocab.get(word)
            if idx is not None:
                vec[idx] += 1.0
        return vec
