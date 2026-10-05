import pytest
from pydantic import ValidationError

from app.analysis.pipeline import analyze_document, analyze_parsed
from app.builder.checks import check_document
from app.builder.export_docx import render_docx
from app.builder.export_pdf import render_pdf
from app.builder.importer import document_from_text
from app.builder.layout import format_date, format_range, render_text
from app.parsers.docx_parser import parse_docx
from app.parsers.pdf_parser import parse_pdf
from app.schemas.resume import ResumeDocument
from tests.test_analysis import SAMPLE_RESUME


def test_date_formatting():
    assert format_date("2021-03") == "Mar 2021"
    assert format_date("2021") == "2021"
    assert format_date("") == ""
    assert format_range("2020-01", "", current=True) == "Jan 2020 – Present"
    assert format_range("2018", "2019-12") == "2018 – Dec 2019"
    assert format_range("", "2019") == "2019"


def test_document_rejects_malformed_dates_and_oversized_lists():
    with pytest.raises(ValidationError):
        ResumeDocument.model_validate({"experience": [{"title": "X", "start": "March 2020"}]})
    with pytest.raises(ValidationError):
        ResumeDocument.model_validate({"experience": [{"title": "X", "start": "2020-13"}]})
    with pytest.raises(ValidationError):
        ResumeDocument.model_validate({"experience": [{"bullets": ["b"] * 16}]})


def test_render_text_uses_standard_headings_and_bullets(sample_document):
    text = render_text(ResumeDocument.model_validate(sample_document))
    for heading in ("SUMMARY", "EXPERIENCE", "EDUCATION", "SKILLS", "CERTIFICATIONS"):
        assert f"\n{heading}\n" in text
    assert "• Built ETL pipelines" in text
    assert "Jan 2020 – Present | Dhaka" in text
    # Education details are plain lines, so they aren't judged as achievement bullets.
    assert "• GPA" not in text
    assert "PROJECTS" not in text  # empty sections are omitted


@pytest.mark.parametrize("render,parse", [(render_pdf, parse_pdf), (render_docx, parse_docx)])
def test_exported_files_are_ats_clean_and_score_like_the_editor(sample_document, render, parse):
    doc = ResumeDocument.model_validate(sample_document)
    editor = analyze_document(doc, None)
    parsed = parse(render(doc))
    exported = analyze_parsed(parsed, None)

    assert exported["formatting_issues"] == []
    assert all(section["found"] for section in exported["sections"])
    # What you see while editing is what the downloaded file scores.
    assert exported["content_score"] == editor["content_score"]
    assert exported["keyword_score"] == editor["keyword_score"]
    assert exported["profile"]["years_experience"] == editor["profile"]["years_experience"]


def test_pdf_export_handles_non_latin_text(sample_document):
    sample_document["basics"]["name"] = "Zoë Łukasiewicz-Müller"
    sample_document["experience"][0]["bullets"][0] = "Cut costs by €40k — “quickly” and ‘cleanly’…"
    pdf = render_pdf(ResumeDocument.model_validate(sample_document))
    assert "Zoë Łukasiewicz-Müller" in parse_pdf(pdf)["text"]


def test_pdf_export_falls_back_to_core_fonts_without_dejavu(sample_document, monkeypatch):
    monkeypatch.setattr("app.builder.export_pdf.FONT_SEARCH_DIRS", [])
    monkeypatch.setattr("app.builder.export_pdf._find_font_dir", lambda: None)
    sample_document["basics"]["name"] = "Zoë Łukasiewicz"
    text = parse_pdf(render_pdf(ResumeDocument.model_validate(sample_document)))["text"]
    assert "Zoë" in text  # Latin-1 survives; characters outside it degrade, never crash


def test_compact_template_fits_more_per_page(sample_document):
    sample_document["experience"] = sample_document["experience"] * 5
    classic = parse_pdf(render_pdf(ResumeDocument.model_validate({**sample_document, "template": "classic"})))
    compact = parse_pdf(render_pdf(ResumeDocument.model_validate({**sample_document, "template": "compact"})))
    assert compact["page_count"] <= classic["page_count"]


def test_checks_on_complete_resume(sample_document):
    assert check_document(ResumeDocument.model_validate(sample_document)) == []


def test_checks_flag_missing_contact_dates_and_bullets():
    doc = ResumeDocument.model_validate({
        "experience": [
            {"title": "Analyst", "company": "Acme", "bullets": ["Did a thing"]},
            {"title": "Engineer", "company": "Beta", "start": "2021", "end": "2019", "bullets": ["a", "b"]},
        ]
    })
    issues = check_document(doc)
    messages = " ".join(i["message"] for i in issues)
    severities = {i["severity"] for i in issues}
    assert "critical" in severities
    assert "full name" in messages
    assert "email address or phone" in messages
    assert "start date to 'Analyst at Acme'" in messages
    assert "ends before it starts" in messages
    assert "achievement bullets to 'Analyst at Acme'" in messages
    assert "skills list" in messages


def test_builder_score_reports_missing_jd_keywords(sample_document):
    doc = ResumeDocument.model_validate(sample_document)
    result = analyze_document(doc, "Seeking a data analyst with SQL, Python, Snowflake and dbt experience.")
    assert {"python", "sql"} <= set(result["keywords"]["matched"])
    assert {"snowflake", "dbt"} <= set(result["keywords"]["missing"])
    assert result["profile"]["current_title"] == "Data Analyst"
    assert result["profile"]["years_experience"] >= 6


def test_importer_on_plain_text_resume():
    doc = document_from_text(SAMPLE_RESUME)
    assert doc.basics.name == "Jane Doe"
    assert doc.basics.email == "jane.doe@example.com"
    assert doc.experience[0].title == "Data Analyst"
    assert doc.experience[0].company == "Acme Corp"
    assert doc.experience[0].current is True
    assert len(doc.experience[0].bullets) == 2
    assert doc.education[0].degree == "BSc Computer Science"
    assert doc.education[0].institution == "State University"
    assert doc.all_skills() == ["Python", "SQL", "Power BI", "Pandas"]


def test_export_then_import_roundtrip_is_lossless(sample_document):
    original = ResumeDocument.model_validate(sample_document)
    imported = document_from_text(parse_pdf(render_pdf(original))["text"])

    assert imported.basics.model_dump(exclude={"links"}) == original.basics.model_dump(exclude={"links"})
    assert [e.model_dump() for e in imported.experience] == [e.model_dump() for e in original.experience]
    assert [e.model_dump() for e in imported.education] == [e.model_dump() for e in original.education]
    assert imported.skills == original.skills
    assert imported.certifications == original.certifications


def test_importer_never_produces_an_invalid_document():
    junk = "\n".join(["EXPERIENCE", "x" * 5000, "• " + "y" * 5000] + ["• bullet"] * 40 + ["SKILLS", "z, " * 500])
    doc = document_from_text(junk)
    ResumeDocument.model_validate(doc.model_dump())
    assert len(doc.experience[0].bullets) <= 15
