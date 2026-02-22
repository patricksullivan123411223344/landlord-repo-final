from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable

from python.config import settings


@dataclass(frozen=True)
class KnowledgeChunk:
    source: str
    text: str
    score: float


def _knowledge_dir() -> str:
    return settings.rag_knowledge_dir


def _iter_knowledge_files() -> Iterable[str]:
    root = _knowledge_dir()
    if not os.path.isdir(root):
        return []
    out: list[str] = []
    for name in sorted(os.listdir(root)):
        lower = name.lower()
        if lower.endswith(".md") or lower.endswith(".txt"):
            out.append(os.path.join(root, name))
    return out


def _normalize_tokens(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-z0-9]{3,}", text.lower())
        if t not in {"this", "that", "with", "from", "have", "your", "landlord", "tenant"}
    }


def _chunk_text(text: str) -> list[str]:
    # Keep simple paragraph chunks for predictable source snippets.
    chunks = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return [c for c in chunks if len(c) > 80]


def search_knowledge(query: str, top_k: int = 4) -> list[KnowledgeChunk]:
    q_tokens = _normalize_tokens(query)
    if not q_tokens:
        return []

    results: list[KnowledgeChunk] = []
    for path in _iter_knowledge_files():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
        except Exception:
            continue
        for chunk in _chunk_text(raw):
            c_tokens = _normalize_tokens(chunk)
            if not c_tokens:
                continue
            overlap = q_tokens.intersection(c_tokens)
            if not overlap:
                continue
            score = len(overlap) / max(len(q_tokens), 1)
            results.append(
                KnowledgeChunk(
                    source=os.path.basename(path),
                    text=chunk,
                    score=score,
                )
            )

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:top_k]


def format_knowledge_context(chunks: list[KnowledgeChunk], max_chars: int = 8000) -> str:
    if not chunks:
        return ""
    parts: list[str] = []
    size = 0
    for ch in chunks:
        block = f"[Source: {ch.source}]\n{ch.text}\n"
        if size + len(block) > max_chars:
            break
        parts.append(block)
        size += len(block)
    return "\n".join(parts).strip()
