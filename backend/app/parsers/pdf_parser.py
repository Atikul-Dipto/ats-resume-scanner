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
    has_images = False
    has_tables = False
    multi_column_pages = 0
    page_count = 0

    with pdfplumber.open(__import__("io").BytesIO(file_bytes)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)

            if page.images:
                has_images = True
            if page.find_tables():
                has_tables = True
            if _detect_multi_column(page):
                multi_column_pages += 1

    return {
        "text": "\n".join(text_chunks),
        "page_count": page_count,
        "has_images": has_images,
        "has_tables": has_tables,
        "multi_column": multi_column_pages > 0,
        "in_header_footer_text": None,  # not reliably extractable from PDF
    }
