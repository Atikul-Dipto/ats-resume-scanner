import io

import pdfplumber

from app.parsers.errors import DocumentTooLarge

# Gaps between words in one visual line narrower than this (in PDF points)
# are ordinary word spacing; a column gutter is wider.
GUTTER_MIN_WIDTH = 12
LINE_TOLERANCE = 2.5
SCAN_RANGE = (0.2, 0.8)  # fraction of page width searched for a gutter
MAX_CROSSING_RATIO = 0.15
MIN_SPLIT_RATIO = 0.35


def _visual_lines(words: list[dict]) -> list[list[tuple[float, float]]]:
    """Groups words into visual lines, each as a list of contiguous (x0, x1) runs."""
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(lines[-1][0]["top"] - word["top"]) <= LINE_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])

    runs_per_line = []
    for line in lines:
        line.sort(key=lambda w: w["x0"])
        runs = [[line[0]["x0"], line[0]["x1"]]]
        for word in line[1:]:
            if word["x0"] - runs[-1][1] < GUTTER_MIN_WIDTH:
                runs[-1][1] = max(runs[-1][1], word["x1"])
            else:
                runs.append([word["x0"], word["x1"]])
        runs_per_line.append([(a, b) for a, b in runs])
    return runs_per_line


def _detect_multi_column(page) -> bool:
    """True when a vertical gutter splits many lines and almost no text crosses it.

    Counting words left vs. right of the midline (the obvious approach) flags
    every dense single-column page, because full-width lines have words on
    both sides. A real column layout instead has an x position that text
    almost never crosses while many lines have text on both sides of it.
    Right-aligned dates don't trip this: the bullets below them cross the gap.
    """
    words = page.extract_words()
    if len(words) < 20:
        return False
    lines = _visual_lines(words)
    total = len(lines)
    if total < 6:
        return False

    lo, hi = (int(page.width * f) for f in SCAN_RANGE)
    for x in range(lo, hi, 3):
        crossing = split = 0
        for runs in lines:
            if any(a < x < b for a, b in runs):
                crossing += 1
            elif any(b <= x for _, b in runs) and any(a >= x for a, _ in runs):
                split += 1
        if crossing <= total * MAX_CROSSING_RATIO and split >= total * MIN_SPLIT_RATIO:
            return True
    return False


def parse_pdf(file_bytes: bytes, max_pages: int | None = None) -> dict:
    text_chunks = []
    pages_info = []
    has_images = False
    has_tables = False
    multi_column_pages = 0

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        page_count = len(pdf.pages)
        # Checked before any per-page work: page count is what bounds the
        # CPU cost of a request, so an oversized upload is rejected cheaply.
        if max_pages is not None and page_count > max_pages:
            raise DocumentTooLarge(f"This PDF has {page_count} pages; the limit is {max_pages}.")

        for i, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)

            page_has_images = bool(page.images)
            page_has_tables = bool(page.find_tables())
            page_multi_column = _detect_multi_column(page)

            has_images = has_images or page_has_images
            has_tables = has_tables or page_has_tables
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
