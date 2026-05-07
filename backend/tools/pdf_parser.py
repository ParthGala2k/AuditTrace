"""
PDF Parser
----------
Extracts raw text from an uploaded compliance PDF using PyMuPDF.
Chunks the text into sections for the Planner Agent.
"""

import fitz  # PyMuPDF
from typing import List
import re

MAX_PAGES = int(__import__("os").environ.get("PDF_MAX_PAGES", "30"))
MAX_CHUNKS = int(__import__("os").environ.get("PDF_MAX_CHUNKS", "20"))


def extract_text(pdf_path: str) -> str:
    """Extract text from a PDF, capped at MAX_PAGES to keep LLM calls manageable."""
    doc = fitz.open(pdf_path)
    pages = list(doc)[:MAX_PAGES]
    print(f"[pdf_parser] reading {len(pages)}/{len(doc)} pages from {pdf_path}")
    return "\n".join(page.get_text() for page in pages)


def chunk_by_section(text: str, max_chars: int = 3000) -> List[str]:
    """
    Split compliance text into chunks at section boundaries, capped at MAX_CHUNKS.
    Falls back to fixed-size chunking if no section headers are found.
    """
    section_pattern = re.compile(
        r"(?=(?:Section\s+\d+|[A-Z]{2,}\d+\.\d+|\d+\.\s+[A-Z]))", re.MULTILINE
    )
    sections = section_pattern.split(text)
    sections = [s.strip() for s in sections if s.strip()]

    if not sections:
        chunks = []
        for i in range(0, len(text), max_chars - 200):
            chunks.append(text[i : i + max_chars])
        return chunks[:MAX_CHUNKS]

    merged: List[str] = []
    for section in sections:
        if merged and len(merged[-1]) + len(section) < max_chars:
            merged[-1] += "\n" + section
        else:
            merged.append(section)

    result = merged[:MAX_CHUNKS]
    print(f"[pdf_parser] produced {len(result)} chunks (capped at {MAX_CHUNKS})")
    return result
