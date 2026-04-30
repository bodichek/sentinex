"""Token-aware text chunking for embedding."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


@dataclass
class Chunk:
    index: int
    text: str
    token_count: int


def _get_encoder() -> object:
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


_ENCODER = _get_encoder()


def _count_tokens(text: str) -> int:
    if _ENCODER is None:
        # Rough heuristic: ~4 chars / token for English/Czech mix
        return max(1, len(text) // 4)
    return len(_ENCODER.encode(text))  # type: ignore[attr-defined]


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Split ``text`` into overlapping chunks of approximately ``chunk_size`` tokens.

    Uses paragraph boundaries when possible; falls back to character slicing.
    """
    if not text or not text.strip():
        return []
    chunk_size = chunk_size or settings.KNOWLEDGE_CHUNK_SIZE_TOKENS
    overlap = overlap if overlap is not None else settings.KNOWLEDGE_CHUNK_OVERLAP_TOKENS

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    current: list[str] = []
    current_tokens = 0
    idx = 0

    def flush() -> None:
        nonlocal current, current_tokens, idx
        if not current:
            return
        body = "\n\n".join(current)
        chunks.append(Chunk(index=idx, text=body, token_count=current_tokens))
        idx += 1
        # Build overlap from tail
        if overlap and chunks:
            tail = body[-overlap * 4 :]
            current = [tail]
            current_tokens = _count_tokens(tail)
        else:
            current = []
            current_tokens = 0

    for para in paragraphs:
        ptok = _count_tokens(para)
        if ptok > chunk_size:
            # Hard-split oversize paragraph by characters
            stride = chunk_size * 4
            for i in range(0, len(para), stride - (overlap * 4 if overlap else 0)):
                piece = para[i : i + stride]
                if not piece:
                    continue
                chunks.append(
                    Chunk(index=idx, text=piece, token_count=_count_tokens(piece))
                )
                idx += 1
            current = []
            current_tokens = 0
            continue
        if current_tokens + ptok > chunk_size:
            flush()
        current.append(para)
        current_tokens += ptok
    flush()
    return chunks
