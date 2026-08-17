import io

import pdfplumber


def _detect_multi_column(page) -> bool:
    words = page.extract_words()
    if len(words) < 20:
        return False
    mid = page.width / 2
    left = sum(1 for w in words if w["x1"] < mid - 15)
    right = sum(1 for w in words if w["x0"] > mid + 15)
    total = len(words)
    return left > total * 0.2 and right > total * 0.2


def parse_pdf(file_bytes: bytes) -> dict:
    text_chunks = []
    pages_info = []
    has_images = False
    has_tables = False
    multi_column_pages = 0
    page_count = 0

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)

            page_has_images = bool(page.images)
            page_has_tables = bool(page.find_tables())
            page_multi_column = _detect_multi_column(page)

            if page_has_images:
                has_images = True
            if page_has_tables:
                has_tables = True
            if page_multi_column:
                multi_column_pages += 1

            pages_info.append({
                "page_number": i,
                "has_images": page_has_images,
                "has_tables": page_has_tables,
                "multi_column": page_multi_column,
            })

    return {
        "text": "\n".join(text_chunks),
        "page_count": page_count,
        "pages": pages_info,
        "has_images": has_images,
        "has_tables": has_tables,
        "multi_column": multi_column_pages > 0,
        "in_header_footer_text": None,  # not reliably extractable from PDF
    }
