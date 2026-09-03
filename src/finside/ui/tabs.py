from typing import Dict, Any, List
import streamlit as st
from langgraph.checkpoint.memory import MemorySaver

from config import Config
from finside.loaders import PromptLoader
from finside.writers import ReportWriter
from finside.report_md import report_to_markdown
from finside.models import BDRRiskAnalysisReport as _Rapor
from finside.pipeline.graph import build_graph


PROMPT_FILE_NAME = "bdr_analyst_v1.md"

FAZ_ETIKETLERI = {
    "segmentle": "1 · Segmentasyon",
    "triyaj_yap": "2 · Triyaj",
    "gruplari_olustur": "2 · Gruplama",
    "map_worker": "3 · Ensemble Map çıkarımı",
    "map_topla": "3 · Map birleştirme",
    "grup_isle": "4-6 · Grounding + Uzlaştırma + Critic",
    "sentezle": "7 · Sentez",
    "qa_kontrol": "8 · Tutarlılık QA",
    "maliyet_ozetle": "10 · Maliyet özeti",
}


def render_overview_tab(bdr_name: str, is_mock_mode: bool):
    """Karşılaştırma ve Özet Metrikler sekmesini çizer."""
    st.subheader("📊 Model Karşılaştırma & Metrik Özet Tablosu")

    # Hiçbir şey bilmeyen kullanıcı için Rehber Kutusu
    with st.expander("ℹ️ Bu Sistem Nasıl Çalışır? (Kullanım Rehberi)", expanded=not bool(st.session_state.analysis_results)):
        st.markdown("""
        **Finside AI**, firmaların Bağımsız Denetim Raporlarını (BDR) Yapay Zeka modelleriyle otomatik tarar.
        - 📌 **Amacımız:** Dipnotlardaki gözden kaçabilecek dava, kefalet, kur ve likidite risklerini yakalamak ve Kredi Komitesi kararına destek olmaktır.
        - 🚀 **Nasıl Kullanılır?**
          1. Sol menüden **BDR Raporu** ve değerlendirmek istediğiniz **AI Modellerini** seçin.
          2. **🚀 ANALİZİ BAŞLAT** butonuna tıklayın.
          3. Analiz bittiğinde modellerin ürettiği risk sayılarını ve komite karar önerilerini aşağıdaki tablodan kıyaslayın.
        """)

    if st.session_state.analysis_results:
        metrics = st.session_state.metrics_summary
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("İşlenen Rapor", bdr_name)
        c2.metric("Çalıştırılan AI Modelleri", f"{len(metrics)} Model")
        avg_latency = sum(m["duration_sec"] for m in metrics) / len(metrics) if metrics else 0.0
        c3.metric("Ortalama Süre", f"{avg_latency:.2f} sn")
        c4.metric("Çalıştırma Modu", "🧪 Mock Test Modu" if is_mock_mode else "⚡ Canlı API")

        st.markdown("---")
        st.markdown("### 🏆 AI Modellerinin Performans Kıyaslaması")

        table_data = []
        for m in metrics:
            status_badge = "⚠️ Fallback (Simülasyon)" if m["is_mock_fallback"] else "✅ Gerçek Bulut API"
            table_data.append({
                "Model ID": m["model_id"],
                "Model Adı": m["model_name"],
                "Sağlayıcı": m["provider"].upper() if m.get("provider") else "N/A",
                "Analiz Süresi": f"{m['duration_sec']:.2f} saniye",
                "API Durumu": status_badge,
                "Tespit Edilen Risk": f"🔍 {m['risk_count']} Kalem Risk",
                "Denetçi Görüşü": m["denetci_gorusu"] or "Belirtilmedi",
                "Kredi Komitesi Tavsiyesi": m["karar_egilimi"]
            })
        try:
            st.dataframe(table_data, width="stretch")
        except TypeError:
            st.dataframe(table_data, use_container_width=True)
    else:
        st.info("👈 Analize başlamak için sol menüden modellerinizi seçip **🚀 ANALİZİ BAŞLAT** butonuna tıklayınız.")


def render_reports_tab():
    """Model Çıktı Raporları sekmesini çizer."""
    if st.session_state.analysis_results:
        st.subheader("🤖 Model Çıktı Raporları")
        results = st.session_state.analysis_results
        model_tabs = st.tabs([
            f"{r['model_name']}{' ⚠️' if r['report'].is_mock_fallback else ''}"
            for r in results
        ])
        for idx, r in enumerate(results):
            with model_tabs[idx]:
                report = r["report"]
                gorus = report.denetci_gorusu.value if report.denetci_gorusu else "Belirtilmemiş"

                if report.is_mock_fallback:
                    st.warning(f"⚠️ **Mock Fallback Uyarısı**: Gerçek API hatası nedeniyle simülasyon raporu gösterilmektedir. (Hata: {report.fallback_reason})")

                c1, c2, c3 = st.columns(3)
                c1.info(f"**Firma:** {report.firma_adi}")
                c2.success(f"**Denetçi Görüşü:** {gorus}")
                c3.warning(f"**Karar Eğilimi:** {report.karar_egilimi.value}")

                st.markdown("---")
                with st.container(height=600):
                    st.markdown(r["md_content"])
    else:
        st.info("👈 Henüz bir analiz çalıştırılmadı. Sol menüden **🚀 ANALİZİ BAŞLAT** butonuna tıklayabilirsiniz.")


def render_prompt_tab():
    """Prompt Düzenleyici sekmesini çizer."""
    st.subheader("📝 Canlı Prompt Düzenleme & İnceleme Paneli")
    st.caption("Aşağıdaki alanlardan System Prompt ve User Prompt metinlerini canlı olarak değiştirebilirsiniz:")

    col_btn1, col_btn2, _ = st.columns([1, 1, 2])
    with col_btn1:
        if st.button("💾 Değişiklikleri Dosyaya Kaydet (`prompts/bdr_analyst_v1.md`)"):
            full_prompt_md = f"# BDR Finansal Risk Analist Sistem Promptu (v1 - Dinamik)\n\n## SYSTEM_PROMPT\n{st.session_state.active_system_prompt}\n\n---\n\n## USER_PROMPT\n{st.session_state.active_user_template}\n"
            target_prompt_file = Config.BASE_DIR / "prompts" / PROMPT_FILE_NAME
            target_prompt_file.write_text(full_prompt_md, encoding="utf-8")
            PromptLoader._cache.clear()
            st.success("✅ Prompt şablonu dosyaya kalıcı olarak kaydedildi!")

    with col_btn2:
        if st.button("🔄 Orijinal Şablona Sıfırla"):
            sys_orig, usr_orig = PromptLoader.load_prompt_md(PROMPT_FILE_NAME)
            st.session_state.active_system_prompt = sys_orig
            st.session_state.active_user_template = usr_orig
            st.rerun()

    st.markdown("---")
    col_sys, col_usr = st.columns(2)
    with col_sys:
        st.markdown("#### 🟢 SYSTEM_PROMPT")
        st.session_state.active_system_prompt = st.text_area(
            "System Prompt Düzenle",
            value=st.session_state.active_system_prompt,
            height=500,
            key="sys_area"
        )
    with col_usr:
        st.markdown("#### 🔵 USER_PROMPT")
        st.session_state.active_user_template = st.text_area(
            "User Prompt Düzenle ({{bdr_text}} alanını koruyunuz)",
            value=st.session_state.active_user_template,
            height=500,
            key="usr_area"
        )


def render_input_tab(bdr_name: str, bdr_content: str):
    """BDR Metin Görünümü sekmesini çizer."""
    st.subheader(f"📄 İşlenen BDR Dosya İçeriği: `{bdr_name}`")
    st.caption(f"Karakter Sayısı: {len(bdr_content):,} | Kelime Sayısı: {len(bdr_content.split()):,}")

    st.download_button(
        "⬇️ Tam BDR Metnini İndir (.txt)",
        data=bdr_content,
        file_name=bdr_name,
        mime="text/plain",
    )

    gosterilecek = bdr_content
    if len(bdr_content) > Config.BDR_PREVIEW_CHARS:
        st.caption(
            f"Tarayıcı performansı için ilk {Config.BDR_PREVIEW_CHARS:,} karakter kaydırmalı kutuda "
            "gösteriliyor. Tamamı için indirme butonunu kullanın."
        )
        gosterilecek = bdr_content[:Config.BDR_PREVIEW_CHARS]

    with st.container(height=560):
        st.text(gosterilecek)


def render_pipeline_tab(bdr_name: str, bdr_content: str):
    """Multi-Agent Pipeline sekmesini çizer."""
    st.subheader("🔗 Multi-Agent BDR Analiz Pipeline")
    st.caption("Segmentasyon → Triyaj → Ensemble Map → Grounding / Uzlaştırma / Critic → Sentez → QA.")
    st.warning("Bu sekme Karşılaştırma Paneli'nden bağımsızdır.")

    config_data = Config.load_config()
    all_models = config_data.get("models", [])
    pipeline_cfg = config_data.get("pipeline", {})
    model_secenekleri = [m.get("id") for m in all_models]
    varsayilan_ensemble = [m for m in pipeline_cfg.get("map_models", []) if m in model_secenekleri]
    secili_ensemble = st.multiselect(
        "Ensemble Map Modelleri",
        options=model_secenekleri,
        default=varsayilan_ensemble or model_secenekleri[:1],
    )
    maliyet_onay = st.checkbox("Yüksek token maliyetini anladım, pipeline'ı çalıştır")

    try:
        pipeline_btn = st.button("🔗 PIPELINE BAŞLAT", type="primary", width="stretch", disabled=not maliyet_onay)
    except TypeError:
        pipeline_btn = st.button("🔗 PIPELINE BAŞLAT", type="primary", use_container_width=True, disabled=not maliyet_onay)

    if pipeline_btn and secili_ensemble:
        pipe_session_dir, _ = ReportWriter.create_session_directory(bdr_name)
        pipe_graph = build_graph(checkpointer=MemorySaver())
        pipe_baslangic = {
            "bdr_id": bdr_name,
            "bdr_adi": bdr_name,
            "ham_metin": bdr_content,
            "session_dir": str(pipe_session_dir),
            "secili_map_modelleri": secili_ensemble,
        }
        pipe_cfg_run = {"configurable": {"thread_id": bdr_name}, "recursion_limit": 150}

        durum_alani = st.empty()
        yapilan = set()
        son_guncelleme = {}
        with st.spinner("🔗 Pipeline çalışıyor…"):
            for adim in pipe_graph.stream(pipe_baslangic, config=pipe_cfg_run, stream_mode="updates"):
                for node, guncelleme in adim.items():
                    yapilan.add(node)
                    if guncelleme:
                        son_guncelleme[node] = guncelleme
                with durum_alani.container():
                    for node, etiket in FAZ_ETIKETLERI.items():
                        st.write(("✅ " if node in yapilan else "⏳ ") + etiket)

        nihai = (son_guncelleme.get("maliyet_ozetle") or {}).get("nihai_rapor") \
            or (son_guncelleme.get("qa_kontrol") or {}).get("nihai_rapor")
        st.session_state.pipeline_sonucu = {"nihai": nihai, "dizin": str(pipe_session_dir)}
        st.success(f"✅ Pipeline tamamlandı: `{pipe_session_dir}`")

    pipe_sonuc = st.session_state.get("pipeline_sonucu")
    if pipe_sonuc and pipe_sonuc.get("nihai"):
        nr = pipe_sonuc["nihai"]
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.info(f"**Firma:** {nr.get('firma_adi')}")
        c2.success(f"**Denetçi Görüşü:** {nr.get('denetci_gorusu') or '—'}")
        c3.warning(f"**Karar Eğilimi:** {nr.get('karar_egilimi')}")

        try:
            _md = report_to_markdown(_Rapor.model_validate(nr), pipeline_izi=nr.get("pipeline_izi"))
        except Exception:
            _md = None

        if _md:
            st.download_button("⬇️ Nihai Raporu İndir (.md)", data=_md, file_name="nihai_rapor.md", mime="text/markdown")
            with st.container(height=600):
                st.markdown(_md)
        with st.expander("Nihai rapor (JSON)"):
            st.json(nr)
