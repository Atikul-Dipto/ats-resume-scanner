import io

from docx import Document


def parse_docx(file_bytes: bytes) -> dict:
    doc = Document(io.BytesIO(file_bytes))

    paragraphs = [p.text for p in doc.paragraphs]
    text = "\n".join(paragraphs)

    has_tables = len(doc.tables) > 0
    has_images = len(doc.inline_shapes) > 0

    header_footer_text = []
    for section in doc.sections:
        header_footer_text.extend(p.text for p in section.header.paragraphs if p.text.strip())
        header_footer_text.extend(p.text for p in section.footer.paragraphs if p.text.strip())

    return {
        "text": text,
        "page_count": None,
        "pages": [],  # page-level breakdown isn't available for docx without rendering
        "has_images": has_images,
        "has_tables": has_tables,
        "multi_column": False,  # not detectable from docx structure without rendering
        "in_header_footer_text": "\n".join(header_footer_text) or None,
    }
