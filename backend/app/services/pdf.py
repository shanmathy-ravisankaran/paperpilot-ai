from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PdfValidationError(ValueError):
    """Raised when an upload cannot safely be treated as a PDF."""


@dataclass(frozen=True)
class ExtractedPaper:
    title: str
    author: str | None
    page_text: list[str]
    metadata: dict[str, Any]


def validate_pdf(filename: str | None, content_type: str | None, data: bytes, max_bytes: int) -> None:
    if not filename or not filename.lower().endswith(".pdf"):
        raise PdfValidationError("Please upload a file with a .pdf extension.")
    if content_type and content_type not in {"application/pdf", "application/x-pdf"}:
        raise PdfValidationError("The uploaded file must have the application/pdf content type.")
    if not data:
        raise PdfValidationError("The uploaded PDF is empty.")
    if len(data) > max_bytes:
        raise PdfValidationError(f"The PDF exceeds the {max_bytes // 1024 // 1024} MB upload limit.")
    if not data.startswith(b"%PDF-"):
        raise PdfValidationError("The uploaded file does not contain a valid PDF signature.")


def extract_pdf(data: bytes, filename: str) -> ExtractedPaper:
    try:
        import pymupdf

        document = pymupdf.open(stream=data, filetype="pdf")
        if document.needs_pass:
            raise PdfValidationError("Password-protected PDFs cannot be indexed.")
        if document.page_count == 0:
            raise PdfValidationError("The PDF has no pages.")
        page_text = [page.get_text("text").strip() for page in document]
        metadata = document.metadata or {}
        document.close()
    except PdfValidationError:
        raise
    except Exception as exc:
        raise PdfValidationError("The file could not be read as a PDF.") from exc

    if not any(page_text):
        raise PdfValidationError("No extractable text was found in this PDF. Scanned PDFs need OCR first.")
    title = str(metadata.get("title") or Path(filename).stem).strip() or Path(filename).stem
    author = str(metadata.get("author") or "").strip() or None
    return ExtractedPaper(title=title, author=author, page_text=page_text, metadata=metadata)
