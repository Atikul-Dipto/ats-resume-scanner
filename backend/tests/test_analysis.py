from app.analysis.formatting_checker import check_formatting
from app.analysis.keyword_matcher import match_keywords
from app.analysis.profile_extractor import (
    extract_emails,
    extract_skills,
    extract_years_experience,
)
from app.analysis.section_detector import detect_sections

SAMPLE_RESUME = """
Jane Doe
jane.doe@example.com | +1 415-555-0182

Summary
Data analyst with 4 years of experience in Python and SQL.

Experience
Data Analyst, Acme Corp
2020 - Present
- Built ETL pipelines with Python and Airflow, reducing report latency by 40%.
- Led migration of dashboards to Power BI, saving 10 hours per week.

Education
BSc Computer Science, State University, 2016 - 2020

Skills
Python, SQL, Power BI, Pandas
"""


def test_extract_emails():
    assert extract_emails(SAMPLE_RESUME) == ["jane.doe@example.com"]


def test_extract_skills_finds_known_skills():
    skills = extract_skills(SAMPLE_RESUME)
    assert "python" in skills
    assert "sql" in skills
    assert "power bi" in skills


def test_extract_years_experience():
    years = extract_years_experience(SAMPLE_RESUME)
    assert years is not None
    assert years >= 4


def test_detect_sections_finds_all_core_sections():
    sections = detect_sections(SAMPLE_RESUME)
    found = {s["name"]: s["found"] for s in sections}
    assert found["Work Experience"] is True
    assert found["Education"] is True
    assert found["Skills"] is True


def test_check_formatting_flags_short_text():
    issues = check_formatting({
        "text": "too short",
        "has_images": False,
        "has_tables": False,
        "multi_column": False,
        "in_header_footer_text": None,
        "page_count": 1,
    })
    assert any(i["severity"] == "critical" for i in issues)


def test_check_formatting_clean_resume_has_no_critical_issues():
    issues = check_formatting({
        "text": SAMPLE_RESUME * 3,
        "has_images": False,
        "has_tables": False,
        "multi_column": False,
        "in_header_footer_text": None,
        "page_count": 1,
    })
    assert not any(i["severity"] == "critical" for i in issues)


def test_match_keywords_without_job_description():
    result = match_keywords(SAMPLE_RESUME, None)
    assert result["match_score"] > 0
    assert "python" in result["matched"]


def test_match_keywords_with_job_description():
    jd = "Looking for a Data Analyst skilled in Python, SQL, and Tableau."
    result = match_keywords(SAMPLE_RESUME, jd)
    assert "python" in result["matched"]
    assert "tableau" in result["missing"]
