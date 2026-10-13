from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

HEADING = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+)?[A-Z][A-Za-z0-9 ,:;()/-]{2,100}$")


@dataclass(frozen=True)
class Chunk:
    id: str
    paper_id: str
    page: int
    section: str
    text: str


def _section_blocks(text: str) -> list[tuple[str, str]]:
    section = "Document"
    blocks: list[tuple[str, str]] = []
    current: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if HEADING.match(line) and len(line.split()) <= 12:
            if current:
                blocks.append((section, " ".join(current)))
                current = []
            section = line
        else:
            current.append(line)
    if current:
        blocks.append((section, " ".join(current)))
    return blocks


def chunk_pages(paper_id: str, pages: list[str], chunk_size: int = 900, overlap: int = 150) -> list[Chunk]:
    """Deterministic, page-bounded chunks; text never crosses a source page."""
    chunks: list[Chunk] = []
    for page_number, page_text in enumerate(pages, start=1):
        for section, block in _section_blocks(page_text):
            start = 0
            while start < len(block):
                end = min(start + chunk_size, len(block))
                if end < len(block):
                    boundary = block.rfind(" ", start + chunk_size - 180, end)
                    if boundary > start:
                        end = boundary
                text = block[start:end].strip()
                if text:
                    identity = f"{paper_id}|{page_number}|{section}|{len(chunks)}|{text}"
                    chunks.append(Chunk(hashlib.sha256(identity.encode()).hexdigest()[:24], paper_id, page_number, section, text))
                if end >= len(block):
                    break
                start = max(end - overlap, start + 1)
    return chunks
