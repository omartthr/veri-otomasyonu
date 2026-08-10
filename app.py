"""Üniversite Veri Otomasyonu — Streamlit Ana Uygulama.

Çalışma Modları:
  1. URL Bulma         — Eksik URL'leri kural tabanlı olarak araştırır
  2. Program Doldurma — Kaynak Excel + Template Excel ile program verilerini çıkarır
  3. URL Bul + Program Doldur — Her iki modu sırayla çalıştırır

Tamamen kural tabanlı, deterministik, API anahtarı gerektirmez.
"""

from __future__ import annotations

import asyncio
import io
import logging
import sys
from pathlib import Path

import streamlit as st

# Proje kök dizinini Python yoluna ekle
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.excel_reader import read_excel, count_missing_fields, get_universities_needing_research
from src.excel_writer import write_results, generate_output_filename
from src.manual_review import approve_manual_url, reject_manual_url, bot_verify_manual_results
from src.models import (
    CandidateResult, DecisionType, PipelineProgress,
    ResearchCategory, RowStatus, UniversityResearchResult, UniversityRow,
)
from src.pipeline import ResearchPipeline

# ─────────────────── Sayfa Yapılandırması ───────────────────

st.set_page_config(
    page_title="Üniversite Veri Otomasyonu",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
LOG_FILE = PROJECT_ROOT / "data" / "research.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
root_logger = logging.getLogger()
if not any(
    isinstance(handler, logging.FileHandler)
    and Path(handler.baseFilename).resolve() == LOG_FILE.resolve()
    for handler in root_logger.handlers
):
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s — %(name)s — %(levelname)s — %(message)s")
    )
    root_logger.addHandler(file_handler)
logger = logging.getLogger(__name__)


# ─────────────────── Durum Yönetimi (Session State) ───────────────────

from src.program_pipeline.checkpoint import PIPELINE_SCHEMA_VERSION

def _init_session():
    defaults = {
        "research_results": [],
        "excel_rows": [],
        "input_file_path": None,
        "output_file_path": None,
        "source_excel_path": None,
        "template_excel_path": None,
        "program_results": None,
        "program_output_path": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

_init_session()
st.sidebar.caption(f"🚀 Pipeline Sürümü: `{PIPELINE_SCHEMA_VERSION}`")


def _save_session_results() -> Path:
    """Bellekteki güncel kararları yeni bir Excel çıktısına kaydet."""
    input_path = st.session_state.input_file_path
    if not input_path:
        raise ValueError("Önce bir Excel dosyası yüklenmelidir.")

    settings = get_settings()
    output_name = generate_output_filename(input_path)
    output_path = settings.data_output_dir / output_name.name
    saved_path = write_results(
        input_path,
        output_path,
        st.session_state.research_results,
    )
    st.session_state.output_file_path = saved_path
    return saved_path


# ─────────────────── Yardımcı: Güvenli Tablo Renderer ───────────────────

def _render_table(data: list[dict], height: int = 400) -> None:
    """st.dataframe() yerine pandas/pyarrow gerektirmeyen HTML tablo renderer.
    Windows App Control ortamında st.dataframe() ve st.table() pyarrow DLL yükler
    ve engellenir; bu fonksiyon saf HTML ile çalışır."""
    if not data:
        st.info("Gösterilecek veri yok.")
        return
    headers = list(data[0].keys())
    rows_html = ""
    for row in data:
        cells = "".join(
            f"<td style='padding:4px 10px;border:1px solid #333;white-space:nowrap;'>{row.get(h, '')}</td>"
            for h in headers
        )
        rows_html += f"<tr>{cells}</tr>"
    header_html = "".join(
        f"<th style='padding:6px 10px;border:1px solid #444;background:#1e1e2e;text-align:left;'>{h}</th>"
        for h in headers
    )
    table_html = (
        f"<div style='overflow:auto;max-height:{height}px;'>"
        f"<table style='border-collapse:collapse;font-size:0.85em;width:100%;'>"
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)


# ─────────────────── Ana Arayüz ───────────────────

def main():
    st.title("🎓 Üniversite Veri Otomasyonu")
    st.caption("Kural Tabanlı Motor — API Anahtarı Gerektirmez — Tamamen Deterministik")

    settings = get_settings()

    # Kenar çubuğu
    with st.sidebar:
        st.header("⚙️ Sistem")
        st.success("✅ Kural Motoru Aktif")
        st.markdown("**Kaynak:** `Sitemap + Resmî Site + DDG + Bing + Google`")
        st.markdown(f"**Kural Eşiği:** `{settings.rule_accept_threshold}/100`")
        st.markdown(f"**Paralel Üniversite:** `{settings.max_concurrency}`")
        st.markdown(
            f"**Derin Tarama:** `{settings.deep_crawl_max_depth} seviye / "
            f"{settings.deep_crawl_max_pages} sayfa`"
        )
        st.divider()
        st.header("🎯 Çalışma Modu")
        work_mode = st.radio(
            "Mod Seç",
            options=[
                "🔍 URL Bulma",
                "📋 Program Verilerini Doldurma (v1 — Boş Şablon)",
                "⚡ Program Verilerini Doldurma (v2 — Dolu Excel Eksik Sütunlar)",
                "🔍+📋 URL Bul + Program Doldur",
            ],
            index=0,
        )

    # ─── Sekme yapısı moda göre değişiyor ───
    if work_mode == "🔍 URL Bulma":
        tab_upload, tab_research, tab_manual = st.tabs([
            "📂 Excel Yükle", "🔍 URL Araştırma & Sonuçlar", "🛠️ Manuel Kontrol"
        ])
        _render_upload_tab(tab_upload, settings)
        _render_research_tab(tab_research, settings)
        _render_manual_tab(tab_manual)

    elif work_mode == "📋 Program Verilerini Doldurma (v1 — Boş Şablon)":
        tab_prog, tab_prog_manual = st.tabs([
            "📋 Program Verilerini Doldur (v1)", "🛠️ Program Manuel İnceleme"
        ])
        _render_program_fill_tab(tab_prog, settings)
        _render_program_manual_tab(tab_prog_manual)

    elif work_mode == "⚡ Program Verilerini Doldurma (v2 — Dolu Excel Eksik Sütunlar)":
        tab_v2, tab_prog_manual = st.tabs([
            "⚡ v2 Eksik Sütun Doldur (Dolu Excel)", "🛠️ Program Manuel İnceleme"
        ])
        _render_program_fill_v2_tab(tab_v2, settings)
        _render_program_manual_tab(tab_prog_manual)

    else:  # URL Bul + Program Doldur
        tab_upload, tab_research, tab_prog, tab_v2, tab_manual = st.tabs([
            "📂 Excel Yükle", "🔍 URL Araştırma", "📋 Program Doldur (v1)", "⚡ Eksik Doldur (v2)", "🛠️ Manuel Kontrol"
        ])
        _render_upload_tab(tab_upload, settings)
        _render_research_tab(tab_research, settings)
        _render_program_fill_tab(tab_prog, settings)
        _render_program_fill_v2_tab(tab_v2, settings)
        _render_manual_tab(tab_manual)


# ─────────────────── Sekme 1: Excel Yükle ───────────────────

def _render_upload_tab(tab, settings):
    with tab:
        st.header("📂 URL Araştırma — Excel Dosyası Yükle")
        uploaded_file = st.file_uploader(
            "Üniversite verilerini içeren .xlsx dosyasını yükleyin",
            type=["xlsx"],
            help="A-T sütun yapısına sahip orijinal dosya",
            key="url_excel_upload",
        )

        if uploaded_file is not None:
            settings.ensure_directories()
            temp_path = settings.data_input_dir / uploaded_file.name
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            st.session_state.input_file_path = temp_path

            try:
                rows = read_excel(temp_path)
                st.session_state.excel_rows = rows

                stats = count_missing_fields(rows)
                needing_research = get_universities_needing_research(rows)

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Toplam Üniversite", len(rows))
                with col2:
                    st.metric("Araştırma Gereken", len(needing_research))
                with col3:
                    st.metric("Toplam Eksik Alan", stats["total"])
                with col4:
                    st.metric("Tamamlanmış", len(rows) - len(needing_research))

                st.subheader("📋 Yüklenen Veri Önizlemesi")
                table_data = []
                for row in rows[:10]:
                    missing = row.get_missing_categories()
                    table_data.append({
                        "ID": row.university_id or "—",
                        "Üniversite": row.university_name,
                        "Şehir": row.city or "—",
                        "Web Sitesi": row.website or "—",
                        "Eksik Alanlar": ", ".join(c.value for c in missing) if missing else "Yok",
                        "Durum": row.status or "Bekliyor",
                    })
                _render_table(table_data)

            except Exception as e:
                st.error(f"❌ Excel okuma hatası: {e}")


# ─────────────────── Sekme 2: URL Araştırma ───────────────────

def _render_research_tab(tab, settings):
    with tab:
        st.header("🔍 Üniversite URL Araştırma")

        if not st.session_state.excel_rows:
            st.info("👆 Lütfen önce 'Excel Yükle' sekmesinden bir dosya yükleyin.")
            return

        needing_research = get_universities_needing_research(st.session_state.excel_rows)

        auto_bot_verify = st.checkbox(
            "🤖 Tarama bitince Manuel Kontrol kalan URL'leri Bot ikincil taramasından geçir",
            value=True,
        )

        if st.button("🚀 URL Araştırmasını Başlat", type="primary"):
            st.info("Kural tabanlı motor başlatıldı. Lütfen bekleyin...")

            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(p: PipelineProgress):
                if p.total_universities > 0:
                    pct = p.processed_universities / p.total_universities
                    progress_bar.progress(pct)
                status_text.text(
                    f"İşleniyor: {p.current_university or ''} "
                    f"({p.processed_universities}/{p.total_universities})"
                )

            pipeline = ResearchPipeline(progress_callback=update_progress)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(
                pipeline.run(needing_research, auto_verify_manual_with_bot=auto_bot_verify)
            )
            loop.close()

            st.session_state.research_results = results
            st.success("🎉 Araştırma tamamlandı!")

            if st.session_state.input_file_path:
                out_name = generate_output_filename(st.session_state.input_file_path)
                out_path = settings.data_output_dir / out_name.name
                try:
                    out_path = write_results(
                        st.session_state.input_file_path,
                        out_path,
                        results,
                    )
                    st.session_state.output_file_path = out_path
                    st.success(f"💾 Excel oluşturuldu: {out_path.name}")

                    with open(out_path, "rb") as f:
                        st.download_button(
                            "⬇️ Sonuç Excel'ini İndir",
                            data=f,
                            file_name=out_path.name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                except PermissionError:
                    st.error("Excel kaydedilemedi. Dosya kilitli olabilir.")

            # Özet rapor
            initial_missing = sum(len(row.get_missing_categories()) for row in needing_research)
            filled_count = sum(
                1 for result in results
                for candidate in result.best_results.values()
                if candidate and candidate.decision == DecisionType.ACCEPTED
            )
            st.subheader("📋 Tamamlama Raporu")
            r1, r2, r3 = st.columns(3)
            r1.metric("Toplam Kurum", len(needing_research))
            r2.metric("Başlangıç Eksik Alan", initial_missing)
            r3.metric("Doldurulan Alan", filled_count)

        # Sonuçlar gösterimi
        if st.session_state.research_results:
            st.divider()
            st.subheader("📊 Araştırma Sonuçları")

            if st.session_state.input_file_path and st.button(
                "💾 Mevcut Sonuçları Excel'e Kaydet"
            ):
                try:
                    saved_path = _save_session_results()
                    st.success(f"Kaydedildi: {saved_path.name}")
                except PermissionError:
                    st.error("Çıktı klasörü kilitli.")

            for res in st.session_state.research_results:
                with st.expander(f"🎓 {res.university_name} — {res.status.value}"):
                    for cat, cand_res in res.best_results.items():
                        st.markdown(f"### 📌 {cat.value.upper()}")
                        if cand_res is None:
                            st.warning("Kaynak bulunamadı.")
                            continue
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown(f"**Karar:** `{cand_res.decision.value}`")
                            st.markdown(f"**Puan:** `{cand_res.score.total if cand_res.score else 0}/100`")
                            st.markdown(f"**İçerik Yılı:** `{cand_res.content_year or 'Bulunamadı'}`")
                        with col_b:
                            st.markdown(f"**URL:** [{cand_res.candidate.url}]({cand_res.candidate.url})")
                            if cand_res.rejection_reason:
                                st.caption(f"Gerekçe: {cand_res.rejection_reason}")
                        if cand_res.rule_evidence:
                            st.markdown("**Kanıt:**")
                            for ev in cand_res.rule_evidence:
                                st.markdown(f"- *\"{ev}\"*")
                        audit = res.audit_records.get(cat)
                        if audit and audit.alternatives:
                            with st.popover("🔗 Alternatif URL'ler"):
                                for alt in audit.alternatives:
                                    st.markdown(f"- [{alt['url']}]({alt['url']}) (Puan: {alt['score']})")


# ─────────────────── Sekme 3: Program Verilerini Doldurma ───────────────────

def _render_program_fill_tab(tab, settings):
    with tab:
        st.header("📋 Program Verilerini Doldurma")
        st.info(
            "URL Kaynak Excel'indeki üniversitelerin program, kabul, dil ve ücret bilgilerini "
            "otomatik olarak keşfeder ve Template Excel'deki `Programlar` sheetine yazar."
        )

        col_src, col_tmpl = st.columns(2)

        with col_src:
            st.subheader("1️⃣ URL Kaynak Excel")
            source_file = st.file_uploader(
                "Daha önce botla doldurduğunuz URL Excel dosyasını yükleyin",
                type=["xlsx"],
                key="prog_source_excel",
                help="program_url, admission_url, language_url, tuition_url sütunlarını içeren dosya",
            )
            if source_file:
                settings.ensure_directories()
                src_path = settings.data_input_dir / f"source_{source_file.name}"
                with open(src_path, "wb") as f:
                    f.write(source_file.getbuffer())
                st.session_state.source_excel_path = src_path
                st.success(f"✅ Kaynak yüklendi: {source_file.name}")

        with col_tmpl:
            st.subheader("2️⃣ Template Excel")
            template_file = st.file_uploader(
                "Programlar sheetini içeren boş şablon dosyasını yükleyin",
                type=["xlsx"],
                key="prog_template_excel",
                help="Programlar isimli sheet ve 48 sütun başlığı içeren dosya",
            )
            if template_file:
                settings.ensure_directories()
                tmpl_path = settings.data_input_dir / f"template_{template_file.name}"
                with open(tmpl_path, "wb") as f:
                    f.write(template_file.getbuffer())
                st.session_state.template_excel_path = tmpl_path
                st.success(f"✅ Template yüklendi: {template_file.name}")

        # Dosya analizi
        if st.session_state.source_excel_path and st.session_state.template_excel_path:
            _render_program_analysis(settings)


def _render_program_analysis(settings):
    """Yüklenen dosyaları analiz et ve işlemi yönet."""
    from src.program_pipeline.source_excel_reader import read_source_excel
    from src.program_pipeline.template_reader import read_template_excel
    from src.program_pipeline.university_matcher import match_universities
    from src.program_pipeline.pipeline import ProgramPipeline

    st.divider()
    st.subheader("🔍 Dosya Analizi")

    try:
        source_rows = read_source_excel(st.session_state.source_excel_path)
        template_info = read_template_excel(st.session_state.template_excel_path)

        matches = match_universities(source_rows, template_info.university_names)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Kaynak Üniversite", len(source_rows))
        col2.metric("Template Sheet", template_info.sheet_name)
        col3.metric("Eşleşen Üniversite", len([m for m in matches if m.match_type != "no_match"]))
        col4.metric("Eşleşemeyen", len([m for m in matches if m.match_type == "no_match"]))

        # Eşleşmeyen veya belirsiz olanları göster
        ambiguous = [m for m in matches if m.match_type == "needs_manual"]
        if ambiguous:
            st.warning(f"⚠️ {len(ambiguous)} üniversite için belirsiz eşleşme — manuel inceleme gerekebilir:")
            for m in ambiguous[:5]:
                st.write(f"  • `{m.source_name}` → {[c.name for c in m.candidates]}")

        # Ayarlar
        st.divider()
        st.subheader("⚙️ Pipeline Ayarları")
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            threshold = st.slider(
                "Confidence Eşiği",
                min_value=0.50, max_value=1.00, value=settings.program_auto_write_threshold,
                step=0.05,
                help="Bu değerin altındaki alanlar Excel'e yazılmaz, manuel incelemeye gider",
            )
        with col_s2:
            resume_mode = st.checkbox(
                "Checkpoint'ten Devam Et",
                value=True,
                help="Daha önce tamamlanan üniversiteleri atla",
            )
        with col_s3:
            clear_cache = st.checkbox(
                "Cache'i Temizle",
                value=False,
                help="Önceki sayfalar tekrar indirilsin",
            )

        if st.button("🚀 Program Doldurma İşlemini Başlat", type="primary"):
            _run_program_pipeline(
                settings=settings,
                source_rows=source_rows,
                template_info=template_info,
                matches=matches,
                threshold=threshold,
                resume=resume_mode,
                clear_cache=clear_cache,
            )

    except Exception as e:
        st.error(f"❌ Dosya analiz hatası: {e}")
        logger.exception("Program analiz hatası")


def _run_program_pipeline(settings, source_rows, template_info, matches, threshold, resume, clear_cache):
    """Program pipeline'ını çalıştır ve sonuçları göster."""
    from src.program_pipeline.pipeline import ProgramPipeline
    from src.program_pipeline.checkpoint import CheckpointManager
    import json

    settings.ensure_directories()

    if clear_cache:
        import shutil
        cache_dirs = ["html", "pdf", "playwright", "extracted"]
        for d in cache_dirs:
            p = settings.data_cache_dir / d
            if p.exists():
                shutil.rmtree(p)
                p.mkdir(parents=True, exist_ok=True)
        CheckpointManager(settings.checkpoint_dir).reset()
        st.info("🗑️ Cache ve Checkpoint temizlendi.")

    uni_progress = st.progress(0.0)
    prog_progress = st.progress(0.0)
    status_text = st.empty()
    log_area = st.empty()
    stats_cols = st.columns(4)
    log_lines: list[str] = []

    def on_progress(event: dict):
        uni_done = event.get("uni_done", 0)
        uni_total = event.get("uni_total", 1)
        prog_done = event.get("prog_done", 0)
        prog_total = event.get("prog_total", 1)
        uni_progress.progress(uni_done / max(uni_total, 1))
        prog_progress.progress(prog_done / max(prog_total, 1))
        status_text.text(
            f"🏛️ {event.get('uni_name', '')} | "
            f"Üniversite: {uni_done}/{uni_total} | "
            f"Program: {prog_done}/{prog_total}"
        )
        msg = event.get("log", "")
        if msg:
            log_lines.append(msg)
            log_area.code("\n".join(log_lines[-30:]), language=None)

    pipeline = ProgramPipeline(
        confidence_threshold=threshold,
        resume=resume,
        progress_callback=on_progress,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            pipeline.run(
                source_rows=source_rows,
                template_info=template_info,
                matches=matches,
                template_path=st.session_state.template_excel_path,
                output_dir=settings.data_output_dir,
            )
        )
    finally:
        loop.close()

    st.session_state.program_results = result

    st.success(f"🎉 Program doldurma tamamlandı!")

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Toplam Program", result.total_programs)
    s2.metric("Yazılan Hücre", result.cells_written)
    s3.metric("Boş Bırakılan Hücre", result.cells_empty)
    s4.metric("Manuel İnceleme", result.needs_review_count)

    # ── İndirme Butonları — her zaman göster ──────────────────────
    if result.output_path and Path(result.output_path).exists():
        st.session_state.program_output_path = result.output_path
        st.success(f"💾 Dosya hazır: `{result.output_path}`")
        with open(result.output_path, "rb") as f:
            st.download_button(
                "⬇️ Doldurulmuş Excel'i İndir",
                data=f,
                file_name=Path(result.output_path).name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_program_excel",
            )
    else:
        st.warning("⚠️ Excel çıktısı oluşturulamadı — hiç program bulunamadı veya yazma hatası oluştu.")

    if result.audit_path and Path(result.audit_path).exists():
        with open(result.audit_path, "rb") as f:
            st.download_button(
                "⬇️ Audit JSONL İndir",
                data=f,
                file_name=Path(result.audit_path).name,
                mime="application/jsonlines",
                key="download_audit",
            )

    # ── Görsel QA Paneli ──────────────────────────────────────────
    try:
        qa_json_path = settings.data_output_dir / "qa_report.json"
        if qa_json_path.exists():
            import json as _json
            with open(qa_json_path, encoding="utf-8") as _f:
                qa_data = _json.load(_f)

            st.divider()
            st.subheader("🔬 Kalite Kontrol Raporu (8 Kural)")

            passed = qa_data.get("passed_qa", False)
            failure_reasons = qa_data.get("failure_reasons", [])
            warning_reasons = qa_data.get("warning_reasons", [])

            if passed:
                st.success("✅ Sert kalite kuralları geçildi — Excel dosyası oluşturuldu ve hazır!")
                if warning_reasons:
                    for warn in warning_reasons:
                        st.info(f"ℹ️ {warn}")
            else:
                st.error(f"⛔ {len(failure_reasons)} sert kural ihlali nedeniyle Excel çıktısı engellendi:")
                for reason in failure_reasons:
                    st.error(f"  • {reason}")

            # 8 kural uyum tablosu
            st.markdown("#### 📋 8 Kural Uyum Kontrolü")
            fill_rates = qa_data.get("fill_rates_by_field", {})
            duration_rate = fill_rates.get("Eğitim Süresi", 0)
            gpa_rate = fill_rates.get("Minimum GPA", 0)
            source_rate = fill_rates.get("Kabul Verisi Kaynağı", 0)
            lang_rate = max(
                fill_rates.get("Minimum IELTS", 0),
                fill_rates.get("Minimum TOEFL", 0),
            )

            rules_data = [
                ("Kural 1", "Yüksek Doluluk",
                 duration_rate > 0.30 and gpa_rate > 0.20,
                 f"Eğitim Süresi: %{duration_rate*100:.0f} | GPA: %{gpa_rate*100:.0f}"),
                ("Kural 2", "Yalnızca Gerçek+Doğrulanmış Programlar",
                 qa_data.get("junk_program_names_count", 0) == 0,
                 f"Çöp program: {qa_data.get('junk_program_names_count', 0)}"),
                ("Kural 3", "Resmî Kaynaklar",
                 qa_data.get("official_program_source_ratio", 0) >= 0.95,
                 f"Resmî kaynak oranı: %{qa_data.get('official_program_source_ratio',0)*100:.0f}"),
                ("Kural 4", "Kapsama Uygun Kabul/Dil/Ücret",
                 lang_rate > 0.50,
                 f"Dil testi doluluk: %{lang_rate*100:.0f}"),
                ("Kural 5", "Kaynak Yorumları",
                 source_rate > 0.80,
                 f"Kabul Verisi Kaynağı: %{source_rate*100:.0f}"),
                ("Kural 6", "Tekilleştirme + Çöp Filtresi",
                 qa_data.get("duplicate_count", 0) == 0,
                 f"Duplicate: {qa_data.get('duplicate_count', 0)}"),
                ("Kural 7", "Uydurma Yok — Boş Bırak",
                 qa_data.get("fake_derived_count", 0) == 0,
                 f"Sahte türetilmiş hücre: {qa_data.get('fake_derived_count', 0)}"),
                ("Kural 8", "Otomatik + Görsel QA",
                 True,
                 "Bu panel ✅"),
            ]

            col_r1, col_r2 = st.columns(2)
            for i, (rule_id, rule_name, ok, detail) in enumerate(rules_data):
                col = col_r1 if i % 2 == 0 else col_r2
                icon = "✅" if ok else "❌"
                col.markdown(
                    f"""<div style="
                        background: {'#0d2b1a' if ok else '#2b0d0d'};
                        border: 1px solid {'#1a7a3a' if ok else '#7a1a1a'};
                        border-radius: 8px; padding: 10px 14px; margin-bottom: 8px;
                    ">
                    <b>{icon} {rule_id}</b> — {rule_name}<br>
                    <small style="color: #aaa;">{detail}</small>
                    </div>""",
                    unsafe_allow_html=True,
                )

            if fill_rates:
                st.markdown("#### 📊 Alan Bazlı Doluluk Oranları")
                labels = list(fill_rates.keys())
                data = [{"Alan": k, "Doluluk (%)": round(fill_rates[k] * 100, 1)} for k in labels]
                data.sort(key=lambda x: x["Doluluk (%)"])

                _render_table(data, height=min(600, len(labels) * 38 + 40))

            # İstatistikler
            st.markdown("#### 📈 İstatistikler")
            ic1, ic2, ic3, ic4 = st.columns(4)
            ic1.metric("Tekrar Eden Program", qa_data.get("duplicate_count", 0))
            ic2.metric("Çöp Program Adı", qa_data.get("junk_program_names_count", 0))
            ic3.metric("Sahte Türetilmiş Hücre", qa_data.get("fake_derived_count", 0))
            ic4.metric("Tarihsel Kaynak", qa_data.get("historical_source_count", 0))

    except Exception as _qa_err:
        st.caption(f"ℹ️ QA paneli yüklenirken hata: {_qa_err}")


# ─────────────────── Sekme: v2 Program Verilerini Doldurma (Dolu Excel) ───────────────────


def _render_program_fill_v2_tab(tab, settings):
    with tab:
        st.header("⚡ Program Verilerini Doldurma (v2 — Dolu Excel / Eksik Sütun Doldurucu)")
        st.info(
            "Bu mod, halihazırda dolu olan Excel dosyanızdaki "
            "(`united_states_of_america_california_university_country_review_skill_kontrollu.xlsx` vb.) "
            "**mevcut verilere kesinlikle dokunmadan**, yalnızca **boş/eksik kalan sütunları ve hücreleri** "
            "referans biçiminde doldurur."
        )

        col_pop, col_src = st.columns(2)

        with col_pop:
            st.subheader("1️⃣ Dolu Program Excel'i (Zorunlu)")
            populated_file = st.file_uploader(
                "Zaten dolu olan ve eksik sütunları doldurulacak .xlsx dosyasını yükleyin",
                type=["xlsx"],
                key="v2_populated_excel_upload",
                help="United States / California veya benzeri dolu program Excel dosyası",
            )
            if populated_file:
                settings.ensure_directories()
                pop_path = settings.data_input_dir / f"v2_populated_{populated_file.name}"
                with open(pop_path, "wb") as f:
                    f.write(populated_file.getbuffer())
                st.session_state["v2_populated_excel_path"] = pop_path
                st.success(f"✅ Dolu Excel yüklendi: {populated_file.name}")

        with col_src:
            st.subheader("2️⃣ URL Kaynak Excel'i (Opsiyonel — v1 gibi)")
            v2_source_file = st.file_uploader(
                "Üniversite URL'lerini içeren kaynak Excel dosyasını yükleyin (Opsiyonel)",
                type=["xlsx"],
                key="v2_source_excel_upload",
                help="program_url, admission_url, language_url, tuition_url içeren dosya",
            )
            if v2_source_file:
                settings.ensure_directories()
                v2_src_path = settings.data_input_dir / f"v2_source_{v2_source_file.name}"
                with open(v2_src_path, "wb") as f:
                    f.write(v2_source_file.getbuffer())
                st.session_state["v2_source_excel_path"] = v2_src_path
                st.success(f"✅ URL Kaynak Excel yüklendi: {v2_source_file.name}")

        pop_path = st.session_state.get("v2_populated_excel_path")
        if pop_path:
            _render_v2_analysis(pop_path, settings)


def _render_v2_analysis(pop_path: Path, settings):
    from src.program_pipeline.template_reader import read_template_excel
    from src.program_pipeline.excel_writer_v2 import is_cell_empty
    from openpyxl import load_workbook

    st.divider()
    st.subheader("🔍 Dolu Excel Analizi & Doluluk Oranları")

    try:
        tmpl_info = read_template_excel(pop_path)
        wb = load_workbook(pop_path, data_only=True)
        ws = wb[tmpl_info.sheet_name]
        header_row = tmpl_info.header_row
        col_map = tmpl_info.column_map

        total_rows = max(0, (ws.max_row or header_row) - header_row)

        fill_stats: dict[str, int] = {}
        for h, c_idx in col_map.items():
            filled_cnt = sum(
                1 for r in range(header_row + 1, (ws.max_row or header_row) + 1)
                if not is_cell_empty(ws.cell(row=r, column=c_idx).value)
            )
            fill_stats[h] = filled_cnt
        wb.close()

        total_cells = total_rows * len(col_map) if total_rows > 0 else 1
        filled_cells_total = sum(fill_stats.values())
        empty_cells_total = total_cells - filled_cells_total

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Toplam Program Satırı", total_rows)
        c2.metric("Mevcut Dolu Hücre (Korunan)", filled_cells_total)
        c3.metric("Boş Hücre (Hedeflenen)", empty_cells_total)
        c4.metric("Genel Doluluk Oranı", f"%{(filled_cells_total / total_cells)*100:.1f}")

        # Sütun Bazlı Doluluk Önizlemesi
        with st.expander("📊 Sütun Bazlı Mevcut Doluluk Durumu"):
            table_data = [
                {
                    "Sütun Adı": h,
                    "Dolu Hücre": cnt,
                    "Boş Hücre": total_rows - cnt,
                    "Doluluk (%)": round((cnt / max(total_rows, 1)) * 100, 1),
                }
                for h, cnt in fill_stats.items()
            ]
            _render_table(table_data)

        st.divider()
        st.subheader("⚙️ v2 Pipeline Ayarları")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            threshold = st.slider(
                "Confidence Eşiği",
                min_value=0.50, max_value=1.00, value=settings.program_auto_write_threshold,
                step=0.05,
                key="v2_threshold_slider",
                help="Bu güven skorunun altındaki veriler boş bırakılır",
            )
        with col_s2:
            clear_cache = st.checkbox(
                "Cache'i Temizle",
                value=False,
                key="v2_clear_cache",
                help="Önceki indirilen sayfalar yeniden çekilsin",
            )

        source_path = st.session_state.get("v2_source_excel_path")

        if st.button("🚀 v2 Eksik Sütunları Doldurma İşlemini Başlat", type="primary", key="btn_run_v2"):
            _run_v2_pipeline(
                pop_path=pop_path,
                source_path=source_path,
                threshold=threshold,
                clear_cache=clear_cache,
                settings=settings,
            )

    except Exception as e:
        st.error(f"❌ Excel analizi hatası: {e}")
        logger.exception("v2 analiz hatası")


def _run_v2_pipeline(pop_path: Path, source_path: Optional[Path], threshold: float, clear_cache: bool, settings):
    from src.program_pipeline.pipeline_v2 import ProgramPipelineV2
    from src.program_pipeline.checkpoint import CheckpointManager

    if clear_cache:
        import shutil
        cache_dirs = ["html", "pdf", "playwright", "extracted"]
        for d in cache_dirs:
            p = settings.data_cache_dir / d
            if p.exists():
                shutil.rmtree(p)
                p.mkdir(parents=True, exist_ok=True)
        CheckpointManager(settings.checkpoint_dir).reset()
        st.info("🗑️ Cache temizlendi.")

    uni_progress = st.progress(0.0)
    prog_progress = st.progress(0.0)
    status_text = st.empty()
    log_area = st.empty()
    log_lines: list[str] = []

    def on_progress(event: dict):
        uni_done = event.get("uni_done", 0)
        uni_total = event.get("uni_total", 1)
        prog_done = event.get("prog_done", 0)
        prog_total = event.get("prog_total", 1)
        uni_progress.progress(uni_done / max(uni_total, 1))
        prog_progress.progress(prog_done / max(prog_total, 1))
        status_text.text(
            f"⚡ v2 Dolduruluyor: {event.get('uni_name', '')} | "
            f"Üniversite: {uni_done}/{uni_total}"
        )
        msg = event.get("log", "")
        if msg:
            log_lines.append(msg)
            log_area.code("\n".join(log_lines[-30:]), language=None)

    v2_pipeline = ProgramPipelineV2(
        confidence_threshold=threshold,
        progress_callback=on_progress,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            v2_pipeline.run(
                populated_excel_path=pop_path,
                output_dir=settings.data_output_dir,
                source_excel_path=source_path,
            )
        )
    finally:
        loop.close()

    st.session_state.program_results = result

    st.success("🎉 v2 Eksik Sütun Doldurma Tamamlandı!")

    if result.output_path and Path(result.output_path).exists():
        st.session_state.program_output_path = result.output_path
        st.success(f"💾 v2 Doldurulmuş Dosya Hazır: `{result.output_path}`")
        with open(result.output_path, "rb") as f:
            st.download_button(
                "⬇️ v2 Doldurulmuş Excel'i İndir",
                data=f,
                file_name=Path(result.output_path).name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_v2_program_excel",
            )


# ─────────────────── Program Manuel İnceleme ───────────────────


def _render_program_manual_tab(tab):
    with tab:
        st.header("🛠️ Program Manuel İnceleme")

        result = st.session_state.get("program_results")
        if not result:
            st.info("Önce 'Program Verilerini Doldur' sekmesinden işlemi başlatın.")
            return

        try:
            from src.audit.review_queue import ReviewQueue
            queue = ReviewQueue(result.review_queue_path)
            items = queue.get_pending()

            st.write(f"🔍 Manuel İnceleme Bekleyen: **{len(items)}** alan")

            if not items:
                st.success("✅ Tüm alanlar otomatik işlendi veya boş bırakıldı.")
                return

            for item in items:
                with st.container(border=True):
                    st.subheader(f"🏛️ {item.university_name} — {item.program_name}")
                    st.markdown(f"**Alan:** `{item.field_name}`")

                    col_val, col_conf = st.columns(2)
                    with col_val:
                        st.markdown(f"**Önerilen Değer:** `{item.proposed_value}`")
                        st.markdown(f"**Kaynak:** [{item.source_url}]({item.source_url})")
                    with col_conf:
                        st.markdown(f"**Confidence:** `{item.confidence:.2f}`")
                        st.markdown(f"**Kapsam:** `{item.scope}`")

                    st.markdown("**Kanıt:**")
                    st.markdown(f"> *{item.evidence}*")

                    new_val = st.text_input(
                        "Değeri Düzenle",
                        value=str(item.proposed_value or ""),
                        key=f"edit_{item.item_id}",
                    )

                    col_approve, col_reject = st.columns(2)
                    with col_approve:
                        if st.button("✅ Onayla", key=f"approve_{item.item_id}"):
                            queue.approve(item.item_id, new_val.strip() or item.proposed_value)
                            st.rerun()
                    with col_reject:
                        if st.button("❌ Reddet (boş bırak)", key=f"reject_{item.item_id}"):
                            queue.reject(item.item_id)
                            st.rerun()

        except Exception as e:
            st.error(f"Manuel inceleme kuyruğu yüklenemedi: {e}")


# ─────────────────── Sekme: URL Manuel Kontrol ───────────────────

def _render_manual_tab(tab):
    with tab:
        st.header("🛠️ URL Manuel Kontrol ve Karşılaştırma Ekranı")

        if not st.session_state.research_results:
            st.info("Manuel kontrol ekranı için önce URL araştırması çalıştırılmalıdır.")
            return

        manual_results = [
            r for r in st.session_state.research_results
            if r.status == RowStatus.MANUAL_REVIEW or any(
                cr and cr.decision == DecisionType.MANUAL_REVIEW
                for cr in r.best_results.values()
            )
        ]

        st.write(f"🔍 Manuel Kontrol Bekleyen Üniversiteler ({len(manual_results)})")

        if manual_results:
            with st.container(border=True):
                st.subheader("🔍 Bot İkincil Derin Taraması")
                st.caption(
                    "Manuel Kontrol durumundaki URL'leri Bot kural motoruyla tekrar taramadan geçirin."
                )
                if st.button("🚀 Bot ile Tekrar Tara", type="primary"):
                    st.info("Bot ikincil taraması başlatıldı...")
                    bot_bar = st.progress(0)
                    bot_status = st.empty()

                    def update_bot_p(curr, tot, name):
                        pct = curr / tot if tot > 0 else 1.0
                        bot_bar.progress(pct)
                        bot_status.text(f"Bot Taraması: {name} ({curr}/{tot})")

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    updated_results, stats = loop.run_until_complete(
                        bot_verify_manual_results(st.session_state.research_results, update_bot_p)
                    )
                    loop.close()

                    st.session_state.research_results = updated_results
                    settings = get_settings()
                    saved_path = _save_session_results()
                    st.success(
                        f"🎉 Bot İkincil Taraması Tamamlandı!\n\n"
                        f"• İncelenen üniversite: {stats['checked_universities']}\n"
                        f"• Doğrulanan alan: {stats['verified_fields']}\n"
                        f"• Kalan manuel: {stats['remaining_manual']}\n\n"
                        f"💾 {saved_path.name}"
                    )
                    st.rerun()

        for res in manual_results:
            with st.container(border=True):
                st.subheader(f"🏛️ {res.university_name}")
                for cat, cand_res in res.best_results.items():
                    if cand_res and cand_res.decision != DecisionType.MANUAL_REVIEW:
                        continue
                    st.markdown(f"#### `{cat.value.upper()}`")
                    if cand_res:
                        st.write(f"Aday URL: [{cand_res.candidate.url}]({cand_res.candidate.url})")
                        st.caption(f"Gerekçe: {cand_res.rejection_reason or '—'}")

                        audit = res.audit_records.get(cat)
                        alt_urls = [cand_res.candidate.url]
                        if audit:
                            alt_urls.extend([a["url"] for a in audit.alternatives])

                        selected_url = st.selectbox(
                            f"URL Seç ({res.university_name} - {cat.value})",
                            options=alt_urls,
                            key=f"select_{res.row_number}_{cat.value}",
                        )
                        custom_input = st.text_input(
                            "Veya Yeni URL Girin:",
                            key=f"input_{res.row_number}_{cat.value}",
                        )

                        col_act1, col_act2 = st.columns(2)
                        with col_act1:
                            if st.button("✅ Onayla", key=f"approve_{res.row_number}_{cat.value}"):
                                final_url = custom_input.strip() or selected_url
                                try:
                                    approved = approve_manual_url(res, cat, final_url)
                                    saved = _save_session_results()
                                    st.success(f"Onaylandı: {approved} → {saved.name}")
                                except (ValueError, PermissionError) as exc:
                                    st.error(f"Onay hatası: {exc}")
                        with col_act2:
                            if st.button("❌ Reddet", key=f"reject_{res.row_number}_{cat.value}"):
                                try:
                                    reject_manual_url(res, cat)
                                    saved = _save_session_results()
                                    st.warning(f"Reddedildi → {saved.name}")
                                except (ValueError, PermissionError) as exc:
                                    st.error(f"Ret hatası: {exc}")


if __name__ == "__main__":
    main()
