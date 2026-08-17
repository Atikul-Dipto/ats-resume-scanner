import re

from app.analysis.ats_scorer import ACTION_VERBS, BULLET_LINE_RE, NUMBER_RE

MAX_FLAGS = 8
SNIPPET_LIMIT = 140


def _truncate(text: str) -> str:
    text = text.strip()
    return text if len(text) <= SNIPPET_LIMIT else text[:SNIPPET_LIMIT].rstrip() + "..."


def find_weak_bullets(text: str) -> list[dict]:
    flags = []
    for line in text.splitlines():
        match = BULLET_LINE_RE.match(line)
        if not match:
            continue
        content = match.group(1).strip()
        if not content:
            continue

        reasons = []
        first_word = content.split()[0].lower().strip(".,") if content.split() else ""
        if first_word not in ACTION_VERBS:
            reasons.append("Missing a strong action verb")
        if not NUMBER_RE.search(content):
            reasons.append("Not quantified — add a metric")

        if reasons:
            flags.append({"text": _truncate(content), "reasons": reasons})

    # Prioritize bullets flagged for both reasons, then cap the list.
    flags.sort(key=lambda f: -len(f["reasons"]))
    return flags[:MAX_FLAGS]
