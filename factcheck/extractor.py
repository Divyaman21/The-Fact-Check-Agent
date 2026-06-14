"""
PDF text extraction using PyMuPDF (fitz).
Handles page-level text extraction with page markers for claim source tracking.
"""

from __future__ import annotations

import fitz


def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, int]:
    """
    Extract text content from a PDF file.

    Args:
        pdf_bytes: Raw bytes of the PDF file.

    Returns:
        A tuple of (extracted_text, page_count).
        The text includes page markers in the format:
        --- PAGE 1 ---
        <text>
        --- PAGE 2 ---
        <text>

    Raises:
        ValueError: If the PDF is encrypted, empty, or cannot be parsed.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Failed to open PDF: {e}") from e

    if doc.is_encrypted:
        doc.close()
        raise ValueError(
            "This PDF is password-protected. Please provide an unencrypted file."
        )

    page_count = len(doc)
    if page_count == 0:
        doc.close()
        raise ValueError("The PDF contains no pages.")

    text_parts: list[str] = []

    for page_num in range(page_count):
        page = doc[page_num]
        page_text = page.get_text("text").strip()

        if page_text:
            text_parts.append(f"--- PAGE {page_num + 1} ---")
            text_parts.append(page_text)

    doc.close()

    full_text = "\n\n".join(text_parts)

    if not full_text.strip():
        raise ValueError(
            "No readable text found in the PDF. "
            "It may be a scanned document (image-only). "
            "OCR is not currently supported."
        )

    return full_text, page_count


def get_pdf_metadata(pdf_bytes: bytes) -> dict:
    """
    Extract metadata from a PDF file.

    Args:
        pdf_bytes: Raw bytes of the PDF file.

    Returns:
        Dictionary with keys: title, author, subject, page_count, file_size_kb.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return {}

    metadata = doc.metadata or {}
    info = {
        "title": metadata.get("title", "").strip() or "Untitled Document",
        "author": metadata.get("author", "").strip() or "Unknown",
        "subject": metadata.get("subject", "").strip() or "",
        "page_count": len(doc),
        "file_size_kb": round(len(pdf_bytes) / 1024, 1),
    }

    doc.close()
    return info
