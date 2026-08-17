def check_formatting(parsed: dict) -> list[dict]:
    issues = []
    text = parsed["text"]

    if len(text.strip()) < 200:
        issues.append({
            "severity": "critical",
            "message": (
                "Very little text could be extracted from this file. It may be a scanned "
                "image or use a format ATS parsers can't read reliably."
            ),
        })

    if parsed.get("has_images"):
        issues.append({
            "severity": "warning",
            "message": (
                "Images or graphics detected (e.g. a photo or icons). Many ATS parsers "
                "ignore image content, and some flag photos for compliance reasons."
            ),
        })

    if parsed.get("has_tables"):
        issues.append({
            "severity": "warning",
            "message": (
                "Table-based layout detected. ATS parsers often read tables out of order, "
                "scrambling the text."
            ),
        })

    if parsed.get("multi_column"):
        issues.append({
            "severity": "warning",
            "message": (
                "Possible multi-column layout detected. Single-column layouts are safer — "
                "some ATS parsers read across columns instead of down them."
            ),
        })

    if parsed.get("in_header_footer_text"):
        issues.append({
            "severity": "critical",
            "message": (
                "Contact info appears to be placed in a document header/footer. Many ATS "
                "parsers skip headers and footers entirely, so this information may be lost."
            ),
        })

    if parsed.get("page_count") and parsed["page_count"] > 2:
        issues.append({
            "severity": "info",
            "message": f"Resume is {parsed['page_count']} pages. 1-2 pages is standard for most ATS-screened roles.",
        })

    return issues
