"""
Stage 2 of the pipeline: splitting documents into chunks.

⚠️ THIS IS THE FILE YOU CHANGE IN MILESTONE 3.

`split_documents` below is deliberately plain. It cuts every document into
fixed-size pieces with a fixed overlap and pays no attention to where sentences
or paragraphs end. It works, and it is not good.

On a corpus of short posts it may not cut anything at all: `campus_life` comes
out as 88 documents and 88 chunks, because almost nothing in it reaches 800
characters. That is the baseline, not a bug — Milestone 3 is where you decide
whether one post should stay one chunk.

Your job in Milestone 3 is to replace the *body* of `split_documents` with a
strategy that fits the documents you actually read in Milestone 1. Keep the
name and the shape of what it returns — the rest of the pipeline calls it, and
your README has to name the function that produced your chunks.

If you get stuck for 30 minutes, `fallback_split` is the original. Switch back
to it, write down what you saw, and move on. That's a real observation about
your pipeline, not giving up.
"""

from dataclasses import dataclass

import config
import re
from ingest import Document


@dataclass
class Chunk:
    """One piece of one document."""

    text: str
    source: str        # which file it came from
    index: int         # which chunk within that file, starting at 0
    produced_by: str   # the function that made it — cite this in your README

    @property
    def label(self) -> str:
        return f"{self.source}#{self.index}"


def fallback_split(
    documents: list[Document],
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """
    The starter's original chunker. Fixed-size character windows with overlap.

    Keep this function. Milestone 3's stop rule points back at it, and having
    something to compare your own strategy against is useful in unit 2.
    """
    chunk_size = chunk_size or config.CHUNK_SIZE
    overlap = overlap or config.CHUNK_OVERLAP

    if overlap >= chunk_size:
        raise ValueError("overlap has to be smaller than chunk_size")

    chunks: list[Chunk] = []
    for doc in documents:
        start = 0
        index = 0
        while start < len(doc.text):
            piece = doc.text[start : start + chunk_size].strip()
            if piece:
                chunks.append(
                    Chunk(
                        text=piece,
                        source=doc.source,
                        index=index,
                        produced_by="chunker.py::fallback_split",
                    )
                )
                index += 1
            start += chunk_size - overlap

    return chunks


def split_documents(documents: list[Document]) -> list[Chunk]:
    import re

# Matches a line like: --- reply 3 (22 votes) ---
REPLY_HEADER_RE = re.compile(
    r"^-{2,}\s*reply\s*\d+\s*\(\s*(\d+)\s*votes?\s*\)\s*-{2,}$",
    re.IGNORECASE,
)
# Matches a line like: THREAD: Is a bike worth it for a 20 minute walk commute?
THREAD_TITLE_RE = re.compile(r"^THREAD:\s*(.+)$", re.IGNORECASE)


def _split_thread(doc: Document) -> list[Chunk] | None:
    """
    Split one THREAD-style document into (question, reply) chunks.
    Returns None if the document doesn't look like a thread, so the
    caller can fall back to fallback_split for that one file.
    """
    lines = doc.text.splitlines()

    title = None
    body_start = 0
    for i, line in enumerate(lines):
        m = THREAD_TITLE_RE.match(line.strip())
        if m:
            title = m.group(1).strip()
            body_start = i + 1
            break
    if title is None:
        return None

    replies: list[tuple[str, list[str]]] = []  # (votes, body_lines)
    current_votes = None
    current_body: list[str] = []
    for line in lines[body_start:]:
        m = REPLY_HEADER_RE.match(line.strip())
        if m:
            if current_votes is not None:
                replies.append((current_votes, current_body))
            current_votes = m.group(1)
            current_body = []
        elif line.strip():
            current_body.append(line.strip())
    if current_votes is not None:
        replies.append((current_votes, current_body))

    if not replies:
        return None

    chunks: list[Chunk] = []
    for idx, (votes, body_lines) in enumerate(replies):
        reply_text = " ".join(body_lines).strip()
        if not reply_text:
            continue
        chunk_text = f"Q: {title}\n({votes} votes) A: {reply_text}"
        chunks.append(
            Chunk(
                text=chunk_text,
                source=doc.source,
                index=idx,
                produced_by="chunker.py::split_documents",
            )
        )
    return chunks


def split_documents(documents: list[Document]) -> list[Chunk]:
    """
    Each document is a THREAD with several short replies. Rather than
    slicing by character count, split on the reply boundaries and pair
    every reply with its thread's question — a reply alone doesn't carry
    enough meaning to be a useful retrieval unit on its own.

    Falls back to fallback_split for any document that doesn't match the
    THREAD / "--- reply N (X votes) ---" shape, so a malformed or
    differently-structured file doesn't just vanish.
    """
    chunks: list[Chunk] = []
    for doc in documents:
        thread_chunks = _split_thread(doc)
        if thread_chunks is None:
            fallback_chunks = fallback_split([doc])
            for c in fallback_chunks:
                c.produced_by = "chunker.py::split_documents (fallback_split, non-thread doc)"
            chunks.extend(fallback_chunks)
        else:
            chunks.extend(thread_chunks)
    return chunks
    return fallback_split(documents)


def describe(chunks: list[Chunk]) -> str:
    """A one-line summary, printed after indexing."""
    if not chunks:
        return "0 chunks"
    lengths = [len(c.text) for c in chunks]
    return (
        f"{len(chunks)} chunks, "
        f"{sum(lengths) // len(lengths)} characters on average "
        f"(shortest {min(lengths)}, longest {max(lengths)}), "
        f"produced by {chunks[0].produced_by}"
    )


if __name__ == "__main__":
    from ingest import load_documents

    chunks = split_documents(load_documents())
    print(describe(chunks))
