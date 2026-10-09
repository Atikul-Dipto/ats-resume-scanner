import re

ACTION_VERBS = {
    "achieved", "analyzed", "automated", "built", "created", "designed", "developed",
    "delivered", "drove", "engineered", "established", "executed", "founded", "implemented",
    "improved", "increased", "launched", "led", "managed", "optimized", "reduced", "resolved",
    "spearheaded", "streamlined", "generated", "grew", "negotiated", "orchestrated",
}

BULLET_LINE_RE = re.compile(r"^\s*[•\-\*•●‣–›▪◦]\s*(.+)")
NUMBER_RE = re.compile(r"\d")

SEVERITY_PENALTY = {"critical": 15, "warning": 7, "info": 2}


def _content_score(text: str, sections: list[dict]) -> tuple[float, dict]:
    found_sections = sum(1 for s in sections if s["found"])
    section_ratio = found_sections / len(sections) if sections else 0

    bullet_lines = [m.group(1) for line in text.splitlines() if (m := BULLET_LINE_RE.match(line))]
    action_verb_hits = sum(
        1 for line in bullet_lines if line.split() and line.split()[0].lower().strip(".,") in ACTION_VERBS
    )
    quantified_hits = sum(1 for line in bullet_lines if NUMBER_RE.search(line))

    action_verb_ratio = action_verb_hits / len(bullet_lines) if bullet_lines else 0
    quantified_ratio = quantified_hits / len(bullet_lines) if bullet_lines else 0

    score = (
        section_ratio * 50
        + action_verb_ratio * 25
        + quantified_ratio * 25
    )
    details = {
        "found_sections": found_sections,
        "bullet_count": len(bullet_lines),
        "action_verb_ratio": round(action_verb_ratio, 2),
        "quantified_ratio": round(quantified_ratio, 2),
    }
    return round(score, 1), details


def _formatting_score(issues: list[dict]) -> float:
    score = 100.0
    for issue in issues:
        score -= SEVERITY_PENALTY.get(issue["severity"], 5)
    return max(score, 0.0)


def score_resume(
    text: str,
    sections: list[dict],
    formatting_issues: list[dict],
    keyword_result: dict,
    has_job_description: bool,
) -> dict:
    formatting_score = _formatting_score(formatting_issues)
    content_score, content_details = _content_score(text, sections)
    keyword_score = keyword_result["match_score"]

    if has_job_description:
        weights = {"formatting": 0.3, "content": 0.35, "keyword": 0.35}
    else:
        weights = {"formatting": 0.4, "content": 0.4, "keyword": 0.2}

    overall = (
        formatting_score * weights["formatting"]
        + content_score * weights["content"]
        + keyword_score * weights["keyword"]
    )

    suggestions = _build_suggestions(sections, formatting_issues, keyword_result, content_details)

    return {
        "ats_score": round(overall, 1),
        "formatting_score": round(formatting_score, 1),
        "content_score": content_score,
        "keyword_score": keyword_score,
        "suggestions": suggestions,
    }


def _build_suggestions(sections, formatting_issues, keyword_result, content_details) -> list[str]:
    suggestions = []

    for section in sections:
        if not section["found"]:
            suggestions.append(f"Add a clearly labeled '{section['name']}' section.")

    for issue in formatting_issues:
        if issue["severity"] in ("critical", "warning"):
            suggestions.append(issue["message"])

    if content_details["bullet_count"] == 0:
        suggestions.append("Use bullet points to list achievements instead of paragraphs.")
    elif content_details["action_verb_ratio"] < 0.4:
        suggestions.append("Start more bullet points with strong action verbs (e.g. 'Led', 'Built', 'Increased').")

    if content_details["quantified_ratio"] < 0.3:
        suggestions.append("Quantify more achievements with numbers, percentages, or dollar amounts.")

    if keyword_result["missing"]:
        top_missing = ", ".join(keyword_result["missing"][:8])
        suggestions.append(f"Consider adding these role-relevant keywords if genuinely applicable: {top_missing}.")

    return suggestions
