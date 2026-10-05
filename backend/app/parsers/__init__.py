from app.parsers.docx_parser import parse_docx
from app.parsers.errors import DocumentTooLarge, UnsupportedDocument
from app.parsers.pdf_parser import parse_pdf

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"  # .docx is a zip container


def parse_upload(filename: str, contents: bytes, max_pages: int | None = None) -> dict:
    """Dispatches on extension, but only after the bytes agree with it —
    the extension alone is attacker-controlled."""
    name = filename.lower()
    if name.endswith(".pdf"):
        if not contents.startswith(PDF_MAGIC):
            raise UnsupportedDocument("This file isn't a valid PDF.")
        return parse_pdf(contents, max_pages=max_pages)
    if name.endswith(".docx"):
        if not contents.startswith(ZIP_MAGIC):
            raise UnsupportedDocument("This file isn't a valid .docx document.")
        return parse_docx(contents)
    raise UnsupportedDocument("Only .pdf and .docx files are supported.")


__all__ = ["parse_upload", "parse_pdf", "parse_docx", "DocumentTooLarge", "UnsupportedDocument"]
