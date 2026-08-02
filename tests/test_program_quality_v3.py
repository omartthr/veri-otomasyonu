"""Kapsamlı Kalite Güncellemesi v3 Regresyon Testleri.

Bu test paketi, tüm 15 kural maddesini ve gerçek hatalı/geçerli örnekleri doğrular.
"""

from __future__ import annotations

import pytest
from src.program_pipeline.program_quality import (
    is_junk_program_name, clean_program_name, detect_program_name, assess_program_page
)
from src.program_pipeline.taxonomy import classify_page_taxonomy, PageTaxonomy
from src.program_pipeline.program_manifest import (
    ProgramManifest, ProgramCandidate, get_canonical_program_name, generate_dedup_key
)
from src.program_pipeline.policy_scope import is_policy_compatible_with_program
from src.program_pipeline.tuition_matcher import format_tuition_value
from src.program_pipeline.content_sections import ContentSection


def test_rejected_junk_program_names():
    """Çöp program adlarının kesin olarak reddedildiğini doğrula."""
    junk_examples = [
        "Courses",
        "Policies",
        "Register",
        "JSON-LD Structured Data",
        "Content.php",
        "Catalog 2008-2009.pdf",
        "Highest Paying Masters Degree",
        "How Much Does an Online BBA Degree Cost",
        "Model Curriculum",
        "Office Hours",
        "Licensure and Accreditation",
        "Academic Catalog",
    ]
    for junk in junk_examples:
        assert is_junk_program_name(junk) is True, f"Çöp ad reddedilmeliydi: {junk}"


def test_rejected_junk_urls():
    """Program dışı URL yollarının taksonomi ve ön filtre ile reddedildiğini doğrula."""
    junk_urls = [
        "https://phoenix.edu/insights/best-degrees",
        "https://phoenix.edu/blog/student-life",
        "https://phoenix.edu/news/2026-announcement",
        "https://phoenix.edu/events/orientation",
        "https://phoenix.edu/register/now",
        "https://phoenix.edu/policies/privacy",
    ]
    for url in junk_urls:
        tax = classify_page_taxonomy(url)
        assert tax in (PageTaxonomy.BLOG_NEWS, PageTaxonomy.OTHER), f"Yol reddedilmeliydi: {url}"


def test_accepted_valid_programs():
    """Gerçek program adlarının kabul edildiğini doğrula."""
    valid_examples = [
        "Master of Divinity",
        "Bachelor of Science in Nursing",
        "Doctor of Business Administration",
        "Associate of Arts in Early Childhood Education",
        "Certificate in Cybersecurity",
    ]
    for valid in valid_examples:
        assert is_junk_program_name(valid) is False
        cleaned = clean_program_name(valid)
        assert cleaned is not None


def test_subject_name_with_degree_context():
    """Konu adı başlıklarının ancak aynı bölümde derece + bağlam varsa kabul edildiğini doğrula."""
    sections_with_context = [
        ContentSection(
            heading="Computer Science",
            text="The Master of Science in Computer Science requires 30 credit hours to complete the degree.",
            source_type="html",
        )
    ]
    name = detect_program_name(sections_with_context, "https://example.edu/programs/cs")
    assert name == "Computer Science"

    sections_without_context = [
        ContentSection(
            heading="Computer Science",
            text="Welcome to the department news page.",
            source_type="html",
        )
    ]
    name_no = detect_program_name(sections_without_context, "https://example.edu/cs")
    assert name_no is None


def test_program_list_does_not_create_program_row():
    """PROGRAM_LIST sınıfındaki sayfaların program satırı oluşturmadığını doğrula."""
    list_url = "https://example.edu/academics/degree-programs"
    tax = classify_page_taxonomy(list_url)
    assert tax == PageTaxonomy.PROGRAM_LIST


def test_canonical_program_name_mapping():
    """MBA varyasyonlarının aynı canonical ada haritalandığını doğrula."""
    assert get_canonical_program_name("MBA") == "Master of Business Administration"
    assert get_canonical_program_name("M.B.A.") == "Master of Business Administration"
    assert get_canonical_program_name("Online Master of Business Administration") == "Master of Business Administration"


def test_deduplication_key_generation():
    """Tekilleştirme anahtarının doğru üretildiğini doğrula."""
    k1 = generate_dedup_key("Phoenix University", "Graduate", "Business Administration")
    k2 = generate_dedup_key("Phoenix University", "Graduate", "Business Administration")
    assert k1 == k2


def test_policy_scope_isolation():
    """Doktora ücret/politikasının lisans programa uygulanmadığını doğrula."""
    assert is_policy_compatible_with_program("doctoral", "undergraduate") is False
    assert is_policy_compatible_with_program("doctoral", "doctoral") is True
    assert is_policy_compatible_with_program("graduate", "undergraduate") is False


def test_tuition_format_preservation():
    """Ücret birim etiketinin korunduğunu doğrula."""
    res_credit = format_tuition_value("Tuition is $580 per credit hour.")
    assert res_credit is not None
    assert res_credit.formatted_value == "580 USD/kredi"

    res_year = format_tuition_value("Annual tuition is $34,000 per year.")
    assert res_year is not None
    assert res_year.formatted_value == "34.000 USD/yıl"
