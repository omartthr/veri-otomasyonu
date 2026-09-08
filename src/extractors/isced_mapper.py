"""UNESCO ISCED-F 2013 (Fields of Education and Training) Taksonomisi ve Eşleme Modülü.

Program adları, fakülte isimleri veya web içeriği metinlerini standart UNESCO ISCED-F 2013
kod ve başlıklarına dönüştürür.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# UNESCO ISCED-F 2013 Kod Listesi ve Anahtar Kelime Haritası
ISCED_TAXONOMY: list[dict] = [
    {
        "code": "0613",
        "title": "Software and applications development and analysis",
        "broad": "061 - Information and Communication Technologies (ICTs)",
        "keywords": [
            r"\bcomputer science\b", r"\bsoftware engineering\b", r"\bsoftware development\b",
            r"\bweb development\b", r"\bapp development\b", r"\bdata science\b",
            r"\bartificial intelligence\b", r"\bmachine learning\b", r"\bcybersecurity\b",
            r"\bcyber security\b", r"\binformation technology\b", r"\bcomputational\b",
            r"\bilgisayar\b", r"\byazılım\b", r"\byapay zeka\b", r"\bsiber güvenlik\b",
        ],
    },
    {
        "code": "0612",
        "title": "Database and network design and administration",
        "keywords": [
            r"\bdatabase\b", r"\bnetwork administration\b", r"\bcloud computing\b",
            r"\bsystem administration\b", r"\bveritabanı\b", r"\bağ yönetimi\b",
        ],
    },
    {
        "code": "0610",
        "title": "Information and Communication Technologies (ICTs) unspecified",
        "keywords": [
            r"\bict\b", r"\binformation systems\b", r"\bmanagement information systems\b",
            r"\bmis\b", r"\bbişim\b", r"\benformasyon\b",
        ],
    },
    {
        "code": "0413",
        "title": "Management and administration",
        "broad": "041 - Business and administration",
        "keywords": [
            r"\bbusiness administration\b", r"\bmba\b", r"\bmanagement\b", r"\bexecutive mba\b",
            r"\bentrepreneurship\b", r"\borganizational leadership\b", r"\bişletme\b",
            r"\byönetim\b", r"\bliderlik\b", r"\bgirişimcilik\b",
        ],
    },
    {
        "code": "0411",
        "title": "Accounting and taxation",
        "keywords": [
            r"\baccounting\b", r"\btaxation\b", r"\bauditing\b", r"\bmuhasebe\b", r"\bvergi\b",
        ],
    },
    {
        "code": "0412",
        "title": "Finance, banking and insurance",
        "keywords": [
            r"\bfinance\b", r"\bbanking\b", r"\binsurance\b", r"\bfinancial\b", r"\bfinans\b",
            r"\bbankacılık\b", r"\bsigortacılık\b",
        ],
    },
    {
        "code": "0414",
        "title": "Marketing and advertising",
        "keywords": [
            r"\bmarketing\b", r"\badvertising\b", r"\bpublic relations\b", r"\bpazarlama\b",
            r"\breklamcılık\b", r"\bhalkla ilişkiler\b",
        ],
    },
    {
        "code": "0410",
        "title": "Business and administration unspecified",
        "keywords": [
            r"\bbusiness\b", r"\bcommerce\b", r"\bttrade\b", r"\bsupply chain\b",
            r"\blogistics\b", r"\bticaret\b", r"\blojistik\b",
        ],
    },
    {
        "code": "0421",
        "title": "Law",
        "broad": "042 - Law",
        "keywords": [
            r"\blaw\b", r"\bllm\b", r"\bjuris doctor\b", r"\blegal\b", r"\bhukuk\b", r"\badalet\b",
        ],
    },
    {
        "code": "0710",
        "title": "Engineering and engineering trades",
        "broad": "071 - Engineering",
        "keywords": [
            r"\bengineering\b", r"\bmechanical engineering\b", r"\belectrical engineering\b",
            r"\bcivil engineering\b", r"\bchemical engineering\b", r"\biendustri mühendisliği\b",
            r"\bmühendislik\b", r"\bmakine mühendisliği\b", r"\belektrik mühendisliği\b",
            r"\binşaat mühendisliği\b",
        ],
    },
    {
        "code": "0731",
        "title": "Architecture and town planning",
        "broad": "073 - Architecture and construction",
        "keywords": [
            r"\barchitecture\b", r"\burban planning\b", r"\blandscape architecture\b",
            r"\bmimarlık\b", r"\bşehir planlama\b", r"\bpeyzaj mimarlığı\b",
        ],
    },
    {
        "code": "0732",
        "title": "Building and civil engineering",
        "keywords": [
            r"\bconstruction management\b", r"\bbuilding science\b", r"\byapı yönetimi\b",
        ],
    },
    {
        "code": "0912",
        "title": "Medicine",
        "broad": "091 - Health",
        "keywords": [
            r"\bmedicine\b", r"\bmedical\b", r"\bmd\b", r"\bclinical\b", r"\btıp\b", r"\bmedikal\b",
        ],
    },
    {
        "code": "0913",
        "title": "Nursing and midwifery",
        "keywords": [
            r"\bnursing\b", r"\bmidwifery\b", r"\bhemşirelik\b", r"\bebelik\b",
        ],
    },
    {
        "code": "0916",
        "title": "Pharmacy",
        "keywords": [
            r"\bpharmacy\b", r"\bpharmaceutical\b", r"\beczacılık\b",
        ],
    },
    {
        "code": "0911",
        "title": "Dental studies",
        "keywords": [
            r"\bdentistry\b", r"\bdental\b", r"\bdiş hekimliği\b",
        ],
    },
    {
        "code": "0910",
        "title": "Health unspecified",
        "keywords": [
            r"\bpublic health\b", r"\bhealth sciences\b", r"\bhealthcare\b",
            r"\bsağlık bilimleri\b", r"\bhalk sağlığı\b",
        ],
    },
    {
        "code": "0510",
        "title": "Biological and related sciences",
        "broad": "051 - Biological sciences",
        "keywords": [
            r"\bbiology\b", r"\bbiochemistry\b", r"\bbiotechnology\b", r"\bgenetics\b",
            r"\bmolecular biology\b", r"\bbiyoloji\b", r"\bbiyokimya\b", r"\bbiyoteknoloji\b",
        ],
    },
    {
        "code": "0531",
        "title": "Chemistry",
        "broad": "053 - Physical sciences",
        "keywords": [
            r"\bchemistry\b", r"\bkimya\b",
        ],
    },
    {
        "code": "0533",
        "title": "Physics",
        "keywords": [
            r"\bphysics\b", r"\bfizik\b",
        ],
    },
    {
        "code": "0541",
        "title": "Mathematics",
        "broad": "054 - Mathematics and statistics",
        "keywords": [
            r"\bmathematics\b", r"\bmath\b", r"\bmatematik\b",
        ],
    },
    {
        "code": "0542",
        "title": "Statistics",
        "keywords": [
            r"\bstatistics\b", r"\bistatistik\b", r"\banalytics\b",
        ],
    },
    {
        "code": "0311",
        "title": "Economics",
        "broad": "031 - Social sciences",
        "keywords": [
            r"\beconomics\b", r"\biktisat\b", r"\bekonomi\b",
        ],
    },
    {
        "code": "0312",
        "title": "Political sciences and civics",
        "keywords": [
            r"\bpolitical science\b", r"\binternational relations\b", r"\bsiyaset bilimi\b",
            r"\buluslararası ilişkiler\b",
        ],
    },
    {
        "code": "0313",
        "title": "Psychology",
        "keywords": [
            r"\bpsychology\b", r"\bpsikoloji\b", r"\bbehavioral science\b",
        ],
    },
    {
        "code": "0314",
        "title": "Sociology and cultural studies",
        "keywords": [
            r"\bsociology\b", r"\banthropology\b", r"\bsosyoloji\b", r"\bantropoloji\b",
        ],
    },
    {
        "code": "0321",
        "title": "Journalism and reporting",
        "broad": "032 - Journalism and information",
        "keywords": [
            r"\bjournalism\b", r"\bgazetecilik\b", r"\bmedia studies\b", r"\bmedya\b",
            r"\bmass communication\b", r"\biletişim\b",
        ],
    },
    {
        "code": "0210",
        "title": "Arts",
        "broad": "021 - Arts",
        "keywords": [
            r"\bfine arts\b", r"\bmusic\b", r"\btheater\b", r"\btheatre\b", r"\bdesign\b",
            r"\bgraphic design\b", r"\bfilm\b", r"\bcinema\b", r"\bsanat\b", r"\btiyatro\b",
            r"\bmüzik\b", r"\btasarım\b", r"\bgörsel sanatlar\b",
        ],
    },
    {
        "code": "0220",
        "title": "Humanities",
        "broad": "022 - Humanities",
        "keywords": [
            r"\bhistory\b", r"\bphilosophy\b", r"\btheology\b", r"\breligion\b",
            r"\btarih\b", r"\bfelsefe\b", r"\bilahiyat\b", r"\bdin bilimleri\b",
        ],
    },
    {
        "code": "0230",
        "title": "Languages",
        "broad": "023 - Languages",
        "keywords": [
            r"\blinguistics\b", r"\bliterature\b", r"\benglish\b", r"\bspanish\b",
            r"\bfrench\b", r"\bgerman\b", r"\bfiloloji\b", r"\bedebiyat\b", r"\bdilbilim\b",
            r"\bmütercim\b", r"\bmütercim tercümanlık\b",
        ],
    },
    {
        "code": "0110",
        "title": "Education",
        "broad": "011 - Education",
        "keywords": [
            r"\beducation\b", r"\bteaching\b", r"\bpedagogy\b", r"\beğitim bilimleri\b",
            r"\böğretmenlik\b", r"\bpedagoji\b",
        ],
    },
    {
        "code": "1015",
        "title": "Travel, tourism and leisure",
        "broad": "101 - Personal services",
        "keywords": [
            r"\btourism\b", r"\bhospitality\b", r"\bhotel management\b", r"\bturizm\b",
            r"\botelcilik\b", r"\bagirlama\b",
        ],
    },
]


def map_to_isced_code(
    program_name: str = "",
    faculty_name: str = "",
    text_content: str = "",
) -> str:
    """Program adı, fakülte adı veya sayfa içeriğine göre UNESCO ISCED-F 2013 kodunu belirle.

    Returns:
        Örnek: "0613 - Software and applications development and analysis"
    """
    combined = f"{program_name} {faculty_name} {text_content}".strip().lower()
    if not combined:
        return ""

    # Öncelik 1: Program veya Fakülte İsminde Kesin Eşleşme
    for item in ISCED_TAXONOMY:
        for kw in item["keywords"]:
            if re.search(kw, combined, re.I):
                return f"{item['code']} - {item['title']}"

    # Eğer jenerik 'School of ...' veya 'Faculty of ...' varsa
    fac_lower = faculty_name.lower()
    if "business" in fac_lower or "management" in fac_lower or "işletme" in fac_lower:
        return "0410 - Business and administration unspecified"
    if "engineering" in fac_lower or "mühendislik" in fac_lower:
        return "0710 - Engineering and engineering trades"
    if "science" in fac_lower or "fen" in fac_lower:
        return "0500 - Natural sciences, mathematics and statistics unspecified"
    if "art" in fac_lower or "sanat" in fac_lower:
        return "0210 - Arts"
    if "health" in fac_lower or "sağlık" in fac_lower:
        return "0910 - Health unspecified"

    return "0000 - Generic programmes and qualifications"
