"""
PDF Parser
----------
Extracts raw text from an uploaded compliance PDF using PyMuPDF.
Chunks the text into sections for the Planner Agent.
"""

import fitz  # PyMuPDF
from typing import List
import re


def extract_text(pdf_path: str) -> str:
    """Extract full text from a PDF file."""
    doc = fitz.open(pdf_path)
    return "\n".join(page.get_text() for page in doc)


def chunk_by_section(text: str, max_chars: int = 3000) -> List[str]:
    """
    Split compliance text into chunks at section boundaries.
    Falls back to fixed-size chunking if no section headers are found.
    """
    # Try to split on common section heading patterns (e.g., "1.", "Section 2", "CC6.1")
    section_pattern = re.compile(
        r"(?=(?:Section\s+\d+|[A-Z]{2,}\d+\.\d+|\d+\.\s+[A-Z]))", re.MULTILINE
    )
    sections = section_pattern.split(text)
    sections = [s.strip() for s in sections if s.strip()]

    if not sections:
        # Fallback: fixed-size chunks with overlap
        chunks = []
        for i in range(0, len(text), max_chars - 200):
            chunks.append(text[i : i + max_chars])
        return chunks

    # Merge tiny sections into the previous chunk
    merged: List[str] = []
    for section in sections:
        if merged and len(merged[-1]) + len(section) < max_chars:
            merged[-1] += "\n" + section
        else:
            merged.append(section)

    return merged
