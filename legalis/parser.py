"""
legalis/parser.py
─────────────────
Thin file-parsing helpers.
Supports PDF, DOCX, and plain-text uploads.
"""
from __future__ import annotations

import io


def extract_text(raw: bytes, filename: str) -> str:
    """Return plain text from an uploaded file's raw bytes."""
    name = filename.lower()

    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            return f"[PDF parse error: {exc}]"

    if name.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as exc:
            return f"[DOCX parse error: {exc}]"

    # Plain text fallback
    try:
        return raw.decode("utf-8")
    except Exception:
        return raw.decode("latin-1", errors="replace")
