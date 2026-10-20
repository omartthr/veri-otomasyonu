"""Program Pipeline v2 Excel Yazıcı Modülü.

Görevi:
- Kullanıcı tarafından yüklenen ZATEN DOLU olan Excel dosyasını (örneğin
  united_states_of_america_california_university_country_review_skill_kontrollu.xlsx)
  okur.
- Orijinal dolu olan HİÇBİR hücreyi ve veriyi DEĞİŞTİRMEZ (Zero Overwrite Guarantee).
- Sadece boş olan (None, "", "[BOŞ]", "—") hücreleri hedef alır.
- Çıkarılan verileri referans yazım tarzına (GPA için "2,25", IELTS için "6.0",
  ücretler için "USD/unit" vb.) dönüştürerek sadece boş hücrelere yazar.
- Yeni doldurulan hücrelere openpyxl Comment (Kaynak URL) ekler.
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Any

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment
from openpyxl.worksheet.worksheet import Worksheet

from src.program_pipeline.models import ExtractedField, ProgramRecord, TemplateInfo
from src.program_pipeline.program_quality import normalize_program_key

logger = logging.getLogger(__name__)

_DEGREE_NAME_TOKENS = {
    "associate", "arts", "bachelor", "business", "certificate", "degree",
    "doctor", "doctoral", "graduate", "master", "program", "science",
    "of", "in", "and", "the",
}

# Boş hücre olarak değerlendirilecek değerler
_EMPTY_SENTINELS = {None, "", "null", "none", "n/a", "na", "—", "-", "[boş]", "[bos]"}


def is_cell_empty(value: Any) -> bool:
    """Hücrenin boş/eksik olup olmadığını kontrol et."""
    if value is None:
        return True
    val_str = str(value).strip().lower()
    return val_str in _EMPTY_SENTINELS


def _program_subject_tokens(name: str) -> set[str]:
    return {
        token for token in normalize_program_key(name).split()
        if len(token) >= 3 and token not in _DEGREE_NAME_TOKENS
    }


def _build_safe_record_matches(
    worksheet: Worksheet,
    header_row: int,
    university_column: int,
    program_column: int,
    records: list[ProgramRecord],
) -> dict[int, ProgramRecord]:
    """Tam ad veya benzersiz, en az iki kelimeli konu eşleşmesi kur."""
    rows: list[tuple[int, str, str, set[str]]] = []
    for row_index in range(header_row + 1, (worksheet.max_row or header_row) + 1):
        university = worksheet.cell(row_index, university_column).value
        program = worksheet.cell(row_index, program_column).value
        if university and program:
            name = str(program).strip()
            rows.append((
                row_index,
                str(university).strip().casefold(),
                normalize_program_key(name),
                _program_subject_tokens(name),
            ))

    matches: dict[int, ProgramRecord] = {}
    used_records: set[int] = set()
    for record_index, record in enumerate(records):
        if not record.university_name or not record.program_name.value:
            continue
        university = record.university_name.strip().casefold()
        normalized = normalize_program_key(str(record.program_name.value))
        exact_rows = [row for row in rows if row[1] == university and row[2] == normalized]
        if len(exact_rows) == 1:
            matches[exact_rows[0][0]] = record
            used_records.add(record_index)

    for record_index, record in enumerate(records):
        if record_index in used_records or not record.university_name or not record.program_name.value:
            continue
        university = record.university_name.strip().casefold()
        subject_tokens = _program_subject_tokens(str(record.program_name.value))
        if len(subject_tokens) < 2:
            continue
        candidate_rows = [
            row for row in rows
            if row[0] not in matches
            and row[1] == university
            and subject_tokens.issubset(row[3])
        ]
        if len(candidate_rows) == 1:
            matches[candidate_rows[0][0]] = record

    return matches


def format_field_value_v2(field_name: str, field: ExtractedField) -> Optional[Any]:
    """Çıkarılan alan değerini referans Excel yazım stiline göre biçimlendir.

    Referans: united_states_of_america_california_university_country_review_skill_kontrollu.xlsx
    """
    if field is None or field.value is None:
        return None

    val = field.value
    if is_cell_empty(val):
        return None

    # 1. Boolean Değerler
    if isinstance(val, bool):
        return "Evet" if val else "Hayır"

    val_str = str(val).strip()

    # 2. Minimum GPA -> Türkçe virgüllü ondalık formatı ("2,25", "2,5", "3,0")
    if field_name == "Minimum GPA":
        if isinstance(val, (int, float)):
            return f"{val:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        # Metin ise nokta yerine virgül koy
        if "." in val_str and not "," in val_str:
            match = re.match(r"^(\d+)\.(\d+)$", val_str)
            if match:
                return f"{match.group(1)},{match.group(2)}"
        return val_str

    # 3. Yıllık Ücret -> USD formatını koru
    if field_name == "Yıllık Ücret":
        return val_str

    # 4. Eğitim Süresi -> "60 units", "4 yıl / 124 credits" formatları
    if field_name == "Eğitim Süresi":
        return val_str

    # 5. Dil Puanları (IELTS / TOEFL / Duolingo)
    if field_name in ("Minimum IELTS", "Minimum TOEFL", "Minimum Duolingo"):
        return val_str

    # 6. Evet/Hayır/Koşullu alanları
    if field_name in (
        "Portfolyo Gerekli Mi", "Essay Gerekli Mi", "Mülakat Gerekli Mi",
        "CV Gerekli Mi", "İngilizce Yeterlilik Gerekli Mi", "Staj İmkanı",
        "Co-op İmkanı", "Exchange İmkanı", "Çift Diploma", "Başvuru Ücreti Gerekli Mi",
        "Video Başvuru Gerekli Mi"
    ):
        val_lower = val_str.lower()
        if val_lower in ("true", "1", "yes", "evet"):
            return "Evet"
        if val_lower in ("false", "0", "no", "hayır"):
            return "Hayır"
        if "koşullu" in val_lower or "conditional" in val_lower:
            return val_str
        return val_str

    # Diğer tüm metin alanları
    return val_str


def write_missing_fields_to_populated_excel(
    populated_excel_path: Path | str,
    output_path: Path | str,
    program_records: list[ProgramRecord],
    column_map: dict[str, int],
    sheet_name: str = "Programlar",
    header_row: int = 1,
    confidence_threshold: float = 0.85,
) -> dict[str, Any]:
    """Dolu Excel dosyasındaki mevcut verilere DOKUNMADAN sadece boş hücreleri doldur.

    Args:
        populated_excel_path: Kullanıcının yüklediği dolu Excel dosyası
        output_path: Çıktının yazılacağı dosya yolu
        program_records: Çıkarılmış ve doğrulanmış program verileri
        column_map: Başlık adı -> sütun indeksi haritası
        sheet_name: İşlenecek sheet adı
        header_row: Başlık satırı numarası (1-indexed)
        confidence_threshold: Bu eşiğin altındaki güven skorları yazılmaz

    Returns:
        İstatistik sözlüğü: total_rows, existing_cells_preserved, empty_cells_filled, empty_cells_remaining
    """
    populated_excel_path = Path(populated_excel_path)
    output_path = Path(output_path)

    if not populated_excel_path.exists():
        raise FileNotFoundError(f"Dolu Excel dosyası bulunamadı: {populated_excel_path}")

    # Geçici dosyaya kopyala (atomik kayıt için)
    with tempfile.NamedTemporaryFile(
        suffix=".xlsx", delete=False, dir=output_path.parent
    ) as tmp:
        tmp_path = Path(tmp.name)

    stats = {
        "total_rows": 0,
        "existing_cells_preserved": 0,
        "empty_cells_filled": 0,
        "empty_cells_remaining": 0,
    }

    try:
        shutil.copy2(populated_excel_path, tmp_path)
        wb = load_workbook(tmp_path, data_only=False)

        if sheet_name not in wb.sheetnames:
            sheet_name = wb.sheetnames[0]

        ws: Worksheet = wb[sheet_name]

        uni_col = column_map.get("Üniversite Adı") or column_map.get("University Name") or 2
        prog_col = column_map.get("Program Adı") or column_map.get("Program Name") or 3
        row_record_map = _build_safe_record_matches(
            ws, header_row, uni_col, prog_col, program_records
        )

        max_row = ws.max_row or header_row

        for row_idx in range(header_row + 1, max_row + 1):
            uni_val = ws.cell(row=row_idx, column=uni_col).value
            prog_val = ws.cell(row=row_idx, column=prog_col).value

            if not uni_val or not prog_val:
                continue

            stats["total_rows"] += 1
            record = row_record_map.get(row_idx)

            # Eşleşen program verisi yoksa satırdaki boş hücreler kalır
            if not record:
                continue

            for field_name, col_idx in column_map.items():
                cell = ws.cell(row=row_idx, column=col_idx)
                cell_val = cell.value

                # 1. Hücre ZATEN DOLU MU?
                if not is_cell_empty(cell_val):
                    # KESİNLİKLE DOKUNMA!
                    stats["existing_cells_preserved"] += 1
                    continue

                # 2. Hücre BOŞ — Çıkarılmış alanlarda bu veri var mı?
                field = record.fields.get(field_name)
                if field and field.value is not None and field.confidence >= confidence_threshold:
                    formatted_val = format_field_value_v2(field_name, field)
                    if formatted_val is not None:
                        cell.value = formatted_val
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
                        stats["empty_cells_filled"] += 1

                        # Kaynak URL yorumu ekle
                        if field.source_url:
                            try:
                                cell.comment = Comment(
                                    f"v2 Bot Doldurma (Güven: %{int(field.confidence*100)})\nKaynak: {field.source_url[:300]}",
                                    "Üniversite Veri Botu",
                                )
                            except Exception:
                                pass
                        continue

                # 3. Veri bulunamadı veya güven düşük
                stats["empty_cells_remaining"] += 1

        # Atomik kaydet ve taşı
        wb.save(tmp_path)
        wb.close()

        if output_path.exists():
            output_path.unlink()
        shutil.move(str(tmp_path), str(output_path))

        logger.info(
            "v2 Excel Doldurma Tamamlandı: %d satır işlendi, %d hücre korundu, %d boş hücre dolduruldu, %d boş kaldı.",
            stats["total_rows"],
            stats["existing_cells_preserved"],
            stats["empty_cells_filled"],
            stats["empty_cells_remaining"],
        )
        return stats

    except Exception as e:
        logger.exception("v2 Excel yazma hatası: %s", e)
        if tmp_path.exists():
            tmp_path.unlink()
        raise e
