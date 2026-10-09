import shutil
import subprocess
from typing import get_args

import pytest
from pydantic import ValidationError

from app.analysis.ats_scorer import BULLET_LINE_RE
from app.analysis.pipeline import analyze_document, analyze_parsed
from app.builder.checks import check_document
from app.builder.export_docx import render_docx
from app.builder.export_latex import escape, render_latex
from app.builder.export_pdf import render_pdf
from app.builder.importer import document_from_text
from app.builder.layout import build_blocks, format_date, format_range, render_text
from app.builder.templates import SECTION_KEYS, TEMPLATES, resolve_style
from app.parsers.docx_parser import parse_docx
from app.parsers.pdf_parser import parse_pdf
from app.schemas.resume import ResumeDocument, ResumeStyle, TemplateId
from tests.test_analysis import SAMPLE_RESUME

TEMPLATE_IDS = list(get_args(TemplateId))


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


@pytest.mark.parametrize("template", TEMPLATE_IDS)
@pytest.mark.parametrize("render,parse", [(render_pdf, parse_pdf), (render_docx, parse_docx)])
def test_exported_files_are_ats_clean_and_score_like_the_editor(sample_document, render, parse, template):
    doc = ResumeDocument.model_validate({**sample_document, "template": template})
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


def test_pdf_export_needs_no_system_fonts(sample_document, monkeypatch):
    monkeypatch.setattr("app.builder.export_pdf._find_font_dir", lambda: None)
    sample_document["basics"]["name"] = "Zoë Łukasiewicz-Müller"
    for template in TEMPLATE_IDS:
        pdf = render_pdf(ResumeDocument.model_validate({**sample_document, "template": template}))
        # Bundled fonts cover Latin Extended (Ivy prints names in capitals).
        assert "zoë łukasiewicz-müller" in parse_pdf(pdf)["text"].lower()


def test_pdf_export_falls_back_to_core_fonts_without_bundled_fonts(sample_document, monkeypatch, tmp_path):
    monkeypatch.setattr("app.builder.export_pdf.BUNDLED_FONT_DIR", tmp_path)
    sample_document["basics"]["name"] = "Zoë Łukasiewicz"
    text = parse_pdf(render_pdf(ResumeDocument.model_validate(sample_document)))["text"]
    assert "Zoë" in text  # Latin-1 survives; characters outside it degrade, never crash


def test_latex_fonts_have_no_ligatures_in_extracted_text(sample_document):
    sample_document["experience"][0]["bullets"][0] = "Streamlined office workflows efficiently and affordably."
    doc = ResumeDocument.model_validate({**sample_document, "template": "jake"})
    assert "Streamlined office workflows efficiently and affordably." in parse_pdf(render_pdf(doc))["text"]


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


# --- templates & design ----------------------------------------------------


def test_template_presets_match_the_schema():
    assert set(TEMPLATES) == set(TEMPLATE_IDS)
    for template_id in TEMPLATES:
        # Every preset is a complete, valid style.
        ResumeStyle.model_validate(TEMPLATES[template_id]["style"])
        resolve_style(ResumeDocument(template=template_id))


@pytest.mark.parametrize("template", TEMPLATE_IDS)
def test_export_then_import_roundtrip_holds_for_every_template(sample_document, template):
    original = ResumeDocument.model_validate({**sample_document, "template": template})
    imported = document_from_text(parse_pdf(render_pdf(original))["text"])

    assert imported.basics.name.lower() == original.basics.name.lower()  # Ivy prints names in capitals
    assert imported.basics.email == original.basics.email
    assert [e.model_dump() for e in imported.experience] == [e.model_dump() for e in original.experience]
    assert [e.model_dump() for e in imported.education] == [e.model_dump() for e in original.education]
    assert imported.skills == original.skills


def test_style_overrides_beat_the_template_and_unset_fields_inherit_it():
    doc = ResumeDocument(template="jake", style={"accent": "#0A66C2", "date_position": "below"})
    style = resolve_style(doc)
    assert style.accent == "#0A66C2"
    assert style.date_position == "below"
    assert style.font == TEMPLATES["jake"]["style"]["font"]


@pytest.mark.parametrize("bad", [
    {"accent": "red"},
    {"accent": "#12345"},
    {"font_size": 30},
    {"margin": 2},
    {"font": "comic-sans"},
    {"section_order": ["experience", "hobbies"]},
])
def test_style_rejects_invalid_values(bad):
    with pytest.raises(ValidationError):
        ResumeDocument.model_validate({"style": bad})


def test_section_order_is_normalized_and_drives_the_text(sample_document):
    sample_document["style"] = {"section_order": ["skills", "skills", "education"]}
    doc = ResumeDocument.model_validate(sample_document)
    assert resolve_style(doc).section_order[:3] == ("skills", "education", "summary")
    assert set(resolve_style(doc).section_order) == set(SECTION_KEYS)
    text = render_text(doc)
    assert text.index("SKILLS") < text.index("EDUCATION") < text.index("SUMMARY") < text.index("EXPERIENCE")


def test_right_aligned_dates_share_the_role_line(sample_document):
    doc = ResumeDocument.model_validate({**sample_document, "style": {"date_position": "right"}})
    blocks = build_blocks(doc)
    role = next(b for b in blocks if b.kind == "entry_title")
    assert (role.text, role.aside) == ("Data Analyst, Acme Corp", "Jan 2020 – Present")
    assert "Data Analyst, Acme Corp Jan 2020 – Present\nDhaka\n" in render_text(doc)


def test_heading_and_name_case_are_part_of_the_scored_text(sample_document):
    sample_document["style"] = {"heading_case": "normal", "name_case": "upper"}
    text = render_text(ResumeDocument.model_validate(sample_document))
    assert text.startswith("JANE DOE\n")
    assert "\nExperience\n" in text


def test_skill_groups_carry_their_label_for_bold_rendering(sample_document):
    blocks = build_blocks(ResumeDocument.model_validate(sample_document))
    skill = next(b for b in blocks if b.kind == "skill")
    assert (skill.label, skill.text) == ("Languages", "Languages: Python, SQL")


@pytest.mark.parametrize("paper,width_pt", [("a4", 595.28), ("letter", 612.0)])
def test_paper_size_option(sample_document, paper, width_pt):
    import io

    import pdfplumber

    doc = ResumeDocument.model_validate({**sample_document, "style": {"paper": paper}})
    with pdfplumber.open(io.BytesIO(render_pdf(doc))) as pdf:
        assert pdf.pages[0].width == pytest.approx(width_pt, abs=0.5)


# --- LaTeX source export ------------------------------------------------------


def test_latex_escapes_every_special_character():
    assert escape(r"R&D 40% $5 #1 a_b {x} ~ ^ \ <|>") == (
        r"R\&D 40\% \$5 \#1 a\_b \{x\} \textasciitilde{} \textasciicircum{} \textbackslash{} "
        r"\textless{}\textbar{}\textgreater{}"
    )


@pytest.mark.parametrize("template", TEMPLATE_IDS)
def test_latex_source_is_ats_hardened(sample_document, template):
    tex = render_latex(ResumeDocument.model_validate({**sample_document, "template": template})).decode()
    assert tex.startswith("% !TEX program = pdflatex")
    for required in (r"\pdfgentounicode=1", r"\pdfinterwordspaceon", r"\DisableLigatures", r"\pagestyle{empty}"):
        assert required in tex
    for forbidden in (r"\begin{tabular", r"\fancyhead", r"\includegraphics", r"\begin{multicols"):
        assert forbidden not in tex
    assert r"\href{mailto:jane@example.com}{jane@example.com}" in tex
    assert r"\href{https://linkedin.com/in/janedoe}{linkedin.com/in/janedoe}" in tex


def test_latex_switches_to_lualatex_for_scripts_pdflatex_cannot_set(sample_document):
    sample_document["basics"]["name"] = "Пётр Иванов"
    tex = render_latex(ResumeDocument.model_validate(sample_document)).decode()
    assert tex.startswith("% !TEX program = lualatex")


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="needs a TeX installation")
@pytest.mark.parametrize("template", TEMPLATE_IDS)
def test_latex_source_compiles_to_an_ats_clean_pdf(sample_document, template, tmp_path):
    doc = ResumeDocument.model_validate({**sample_document, "template": template})
    (tmp_path / "resume.tex").write_bytes(render_latex(doc))
    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "resume.tex"],
        cwd=tmp_path, capture_output=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout.decode(errors="replace")[-2000:]
    exported = analyze_parsed(parse_pdf((tmp_path / "resume.pdf").read_bytes()), None)
    editor = analyze_document(doc, None)
    assert exported["formatting_issues"] == []
    assert all(section["found"] for section in exported["sections"])
    assert exported["content_score"] == editor["content_score"]
    assert exported["keyword_score"] == editor["keyword_score"]

# Every combination of the newer design options still exports ATS-clean and
# scores like the editor (the per-template tests only cover the presets).
@pytest.mark.parametrize("options", [
    {"heading_style": "double", "bullet": "–", "contact_separator": "·", "headline_color": "accent"},
    {"heading_style": "short", "heading_align": "center", "bullet": "›", "contact_separator": "•"},
    {"heading_style": "short", "font": "robotoslab", "heading_case": "smallcaps", "date_position": "below"},
    {"heading_style": "line", "font": "ebgaramond", "heading_align": "center", "name_case": "upper"},
])
@pytest.mark.parametrize("render,parse", [(render_pdf, parse_pdf), (render_docx, parse_docx)])
def test_design_options_stay_ats_clean(sample_document, options, render, parse):
    doc = ResumeDocument.model_validate({**sample_document, "style": options})
    editor = analyze_document(doc, None)
    exported = analyze_parsed(parse(render(doc)), None)
    assert exported["formatting_issues"] == []
    assert all(section["found"] for section in exported["sections"])
    assert exported["content_score"] == editor["content_score"]
    assert exported["keyword_score"] == editor["keyword_score"]


@pytest.mark.parametrize("bullet", ["•", "–", "›"])
def test_every_bullet_glyph_counts_as_a_bullet(sample_document, bullet):
    doc = ResumeDocument.model_validate({**sample_document, "style": {"bullet": bullet}})
    text = render_text(doc)
    assert f"\n{bullet} Built ETL pipelines" in text
    assert sum(1 for line in text.splitlines() if BULLET_LINE_RE.match(line)) == 4


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="needs a TeX installation")
def test_latex_design_options_compile(sample_document, tmp_path):
    style = {"heading_style": "double", "bullet": "›", "contact_separator": "·", "headline_color": "accent"}
    for i, extra in enumerate([{}, {"heading_style": "short", "heading_align": "center", "bullet": "–"}]):
        doc = ResumeDocument.model_validate({**sample_document, "style": {**style, **extra}})
        (tmp_path / f"r{i}.tex").write_bytes(render_latex(doc))
        result = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"r{i}.tex"],
                                cwd=tmp_path, capture_output=True, timeout=180)
        assert result.returncode == 0, result.stdout.decode(errors="replace")[-2000:]
        assert "Built ETL pipelines" in parse_pdf((tmp_path / f"r{i}.pdf").read_bytes())["text"]