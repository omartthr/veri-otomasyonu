"""Program keşfi için yüksek-hassasiyet kalite kapısı testleri."""

from src.program_pipeline.content_sections import extract_html_sections
from src.program_pipeline.program_quality import (
    assess_program_page,
    detect_program_name,
    looks_like_program_link,
)


def test_html_sectioner_keeps_paragraphs_lists_and_tables():
    html = """
    <html><head><title>Master of Divinity | Example Seminary</title></head>
    <body><main>
      <h1>Master of Divinity</h1>
      <p>The degree requires 92 credit hours.</p>
      <h2>Admission Requirements</h2>
      <ul><li>Official transcripts are required.</li><li>Minimum GPA of 2.5.</li></ul>
      <table><tr><th>Tuition</th><td>$580 per credit hour</td></tr></table>
    </main></body></html>
    """
    sections = extract_html_sections(html, "https://example.edu/master-of-divinity")
    text = " ".join(section.text for section in sections)
    assert "92 credit hours" in text
    assert "Official transcripts" in text
    assert "Minimum GPA of 2.5" in text
    assert "$580 per credit hour" in text


def test_real_degree_page_is_accepted_with_clean_name():
    html = """
    <html><head><title>Master of Divinity | Example Seminary</title></head>
    <body><main>
      <h1>Master of Divinity</h1>
      <p>This 92 credit hour degree prepares students for pastoral ministry.</p>
      <h2>Program Requirements</h2><p>Students complete the program in three years.</p>
    </main></body></html>
    """
    url = "https://example.edu/master-of-divinity"
    sections = extract_html_sections(html, url)
    name = detect_program_name(sections, url)
    result = assess_program_page(url, sections, name)
    assert name == "Master of Divinity"
    assert result.accepted is True


def test_subject_only_title_needs_explicit_degree_context():
    html = """
    <html><head><title>Computer Science | Example University</title></head>
    <body><main>
      <h1>Computer Science</h1>
      <p>The Bachelor of Science degree in Computer Science requires 120 credit hours to complete the program.</p>
      <h2>Program Requirements</h2><p>Complete the following curriculum designed for software engineering and computer science students.</p>
      <p>Graduates are prepared for careers in technology, algorithms, system design, and software development.</p>
    </main></body></html>
    """
    url = "https://example.edu/programs/computer-science"
    sections = extract_html_sections(html, url)
    result = assess_program_page(url, sections)
    assert result.program_name == "Computer Science"
    assert result.accepted is True


def test_program_list_and_json_ld_are_not_program_rows():
    html = """
    <html><head><title>Degree Programs | Example University</title>
    <script type="application/ld+json">{"name": "Example University"}</script></head>
    <body><main><h1>Degree Programs</h1>
      <p>Explore our bachelor and master degree programs.</p>
      <a href="/programs/computer-science">Computer Science</a>
    </main></body></html>
    """
    url = "https://example.edu/degree-programs/"
    sections = extract_html_sections(html, url)
    result = assess_program_page(url, sections)
    assert result.accepted is False
    assert result.program_name is None


def test_noise_links_rejected_even_on_official_domain():
    assert not looks_like_program_link(
        "https://example.edu/insights/master-your-study-skills/",
        "Master Your Study Skills",
    )
    assert not looks_like_program_link(
        "https://example.edu/admissions/register/",
        "Register",
    )
    assert looks_like_program_link(
        "https://example.edu/programs/computer-science/",
        "Computer Science",
    )
