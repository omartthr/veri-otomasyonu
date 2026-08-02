"""District of Columbia Uçtan Uca Doğrulama Scripti.

Bu script:
1. Kaynak Excel ve Template Excel dosyalarını okur.
2. pipeline.py'yi 'program-quality-v3' sürümü ile çalıştırır.
3. Çıktı Excel dosyasını yeniden okuyarak QA Raporu ve Reddedilen URL Raporu üretir.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from src.program_pipeline.source_excel_reader import read_source_excel
from src.program_pipeline.template_reader import read_template_excel
from src.program_pipeline.university_matcher import match_universities
from src.program_pipeline.pipeline import ProgramPipeline
from src.program_pipeline.checkpoint import CheckpointManager, PageCache
from src.program_pipeline.qa_exporter import evaluate_qa_report, save_qa_report
from openpyxl import load_workbook

logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(levelname)s — %(message)s")
logger = logging.getLogger("e2e_test")

DOWNLOADS_DIR = Path(r"C:\Users\lenovo\Downloads")
PROJECT_DIR = Path(__file__).resolve().parent

SOURCE_EXCEL = DOWNLOADS_DIR / "united_states_of_america_district_of_columbia_program_kabul_takip.xlsx"
TEMPLATE_EXCEL = DOWNLOADS_DIR / "template_united_states_of_america_district_of_columbia_university_country_review_programlar_doldurulmus.xlsx"
OUTPUT_DIR = PROJECT_DIR / "data" / "output"


async def main():
    logger.info("District of Columbia Uçtan Uca Test Başlatılıyor...")

    if not SOURCE_EXCEL.exists():
        logger.error("Kaynak Excel bulunamadı: %s", SOURCE_EXCEL)
        return

    if not TEMPLATE_EXCEL.exists():
        # Fallback: proje içindeki veya Downloads'taki alternatif template
        alt_template = list(DOWNLOADS_DIR.glob("*template*.xlsx"))
        if alt_template:
            template_path = alt_template[0]
        else:
            logger.error("Template Excel bulunamadı: %s", TEMPLATE_EXCEL)
            return
    else:
        template_path = TEMPLATE_EXCEL

    logger.info("Kaynak Excel: %s", SOURCE_EXCEL.name)
    logger.info("Template Excel: %s", template_path.name)

    # 1. Kaynak ve Template Oku
    source_rows = read_source_excel(SOURCE_EXCEL)
    template_info = read_template_excel(template_path)
    matches = match_universities(source_rows, template_info)

    logger.info("Bulunan üniversite sayısı: %d", len(source_rows))
    for row in source_rows:
        logger.info(" - %s (%s)", row.university_name, row.official_website)

    # 2. Pipeline Çalıştır
    pipeline = ProgramPipeline(confidence_threshold=0.80, resume=True)
    result = await pipeline.run(
        source_rows=source_rows,
        template_info=template_info,
        matches=matches,
        template_path=template_path,
        output_dir=OUTPUT_DIR,
    )

    logger.info("Pipeline Tamamlandı!")
    logger.info("Toplam Program: %d", result.total_programs)
    logger.info("Yazılan Hücre: %d", result.cells_written)
    logger.info("Boş Hücre: %d", result.cells_empty)
    logger.info("Çıktı Dosyası: %s", result.output_path)

    # 3. Oluşan Excel'i Yeniden Oku ve Doğrula
    if result.output_path and Path(result.output_path).exists():
        wb = load_workbook(result.output_path, read_only=True)
        sheet_name = template_info.sheet_name if template_info.sheet_name in wb.sheetnames else wb.sheetnames[0]
        ws = wb[sheet_name]

        row_count = ws.max_row - 1
        logger.info("Excel Satır Sayısı (Başlık hariç): %d", row_count)
        wb.close()

    qa_report_path = OUTPUT_DIR / "qa_report.json"
    if qa_report_path.exists():
        with open(qa_report_path, encoding="utf-8") as f:
            qa_data = json.load(f)
            logger.info("--- QA RAPORU ÖZETİ ---")
            logger.info("QA Geçti mi?: %s", qa_data.get("passed_qa"))
            logger.info("Üniversite Başına Program Sayısı: %s", qa_data.get("programs_per_university"))
            logger.info("Çöp Program Adı Sayısı: %d", qa_data.get("junk_program_names_count"))
            logger.info("Duplicate Program Sayısı: %d", qa_data.get("duplicate_count"))
            logger.info("Resmî Kaynak Oranı: %.2f", qa_data.get("official_program_source_ratio"))


if __name__ == "__main__":
    asyncio.run(main())
