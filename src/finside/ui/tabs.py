from typing import Dict, Any, List
import streamlit as st
from langgraph.checkpoint.memory import MemorySaver

from config import Config
from finside.loaders import PromptLoader
from finside.writers import ReportWriter
from finside.report_md import report_to_markdown
from finside.models import BDRRiskAnalysisReport as _Rapor
from finside.pipeline.graph import build_graph
from finside.pipeline.ilerleme import (
    FAZ_ETIKETLERI,
    asama_ozeti,
    ilerleme_takipcisi,
    model_rolleri_satiri,
)


PROMPT_FILE_NAME = "bdr_analyst_v1.md"


def render_overview_tab(bdr_name: str, is_mock_mode: bool):
    """Karşılaştırma ve Özet Metrikler sekmesini çizer."""
    st.subheader("📊 Model Karşılaştırma & Metrik Özet Tablosu")

    # Hiçbir şey bilmeyen kullanıcı için Rehber Kutusu
    with st.expander("ℹ️ Bu Sistem Nasıl Çalışır? (Kullanım Rehberi & Mimari)", expanded=not bool(st.session_state.analysis_results)):
        st.markdown("""
        **Finside AI**, kurumsal Bağımsız Denetim Raporlarını (BDR) Yapay Zeka modelleriyle otomatik tarayan otonom bir karar destek sistemidir.
        
        #### 🎯 1. Model Kıyaslama (Benchmark) Ne İşe Yarar ve Nasıl Çalışır?
        - **Ne İşe Yarar?** Farklı Yapay Zeka modellerinin (Google Gemini, OpenAI GPT, DeepSeek, Qwen vb.) aynı BDR raporunu incelerken **hangisinin daha hızlı, hangisinin daha detaylı ve kaç kalem risk yakaladığını** şeffafça kıyaslamanızı sağlar.
        - **Arka Planda Parçadan Nihai Rapora Gidiş (Map-Reduce & Konsolidasyon):**
          1. ✂️ **Bölme (Chunking):** 200+ sayfalık dev BDR raporu dipnot ve finansal tablo bütünlüğü bozulmadan `Context Window` sınırlarına uygun parçalara ayrılır.
          2. 🗺️ **Parçalı Çıkarım (Map):** Modeller her parçayı tatarak 30-40 adet ham risk bulgusu ve dipnot referansı çıkarır.
          3. 🔄 **Konsolidasyon & Deduplikasyon (Reduce):** Birbirini tekrarlayan veya aynı finansal riske değinen ham bulgular akıllı eşleştirme ile tek bir başlıkta birleştirilir (Örn: 35 ham parçalı bulgudan 14 konsolide executive risk kategorisi türetilir).
          4. 📋 **Nihai Rapor:** Konsolide edilen tüm riskler tek bir **Kredi Komitesi Raporu** halinde Performans Özet Tablosunda ve detay sekmelerinde sunulur.

        #### 🔗 2. Multi-Agent Pipeline Adım Adım Akış Şeması
        - **Ne İşe Yarar?** Modeller birbiriyle yarışmak yerine **uzman bir ekip (Ensemble) gibi el ele verir**.
        - **Adım Adım Nasıl Çalışır?**
          1. ✂️ **Segmentasyon (Segmenting):** 200+ sayfalık dev BDR raporu dipnot ve finansal tablo sınırlarına göre mantıksal bölümlere ayrılır.
          2. 🎯 **Triyaj (Triage):** Metin parçaları taranarak risk taşıma ihtimali yüksek kilit dipnotlar önceliklendirilir.
          3. 🗺️ **Ensemble Map (Çoklu Model Çıkarımı):** Seçilen uzman modeller (Gemini, GPT-4o, DeepSeek, Qwen vb.) eşzamanlı çalışarak ham risk bulgularını ve dipnot alıntılarını toplar.
          4. 🔍 **Grounding / Uzlaştırma / Critic / Sanitizer (Doğrulama, Eleştiri & Temizlik):** Üretilen alıntılar ham BDR metninde 3 katmanlı motorla doğrulanır (`Grounding`), modeller arasındaki çelişkiler giderilir (`Uzlaştırma`), eleştirmen ajan (`Critic`) eksik dipnot taraması yapar ve temizlik ajanı (`Sanitizer`) jenerik etki cümlelerini ile risk içermeyen salt bilanço kalemlerini rapordan temizler.
          5. 🧩 **Sentez (Synthesis):** Tüm doğrulanmış riskler, finansal rasyolar ve komite kararları tek bir **Nihai Kredi Komitesi Raporu** halinde birleştirilir.
          6. 🛡️ **QA Kontrolü (Quality Assurance):** Kural tabanlı mantık denetimi yapılarak çelişkili komite kararları ve eksik alanlar son kez kontrol edilir.

        #### 🛠️ 3. Sistemde Aktif Kullanılan Algoritmik Teknoloji Motorları
        - 📐 **Cosine Similarity & Vector Embeddings:** Metin parçaları, dipnotlar ve risk cümleleri arasındaki anlamsal kosinüs benzerliğini hesaplar (`text-embedding-3-small` / TF-IDF Vector Cosine Sim).
        - 🎯 **Numerical Fingerprinting (Sayısal İmza Motoru):** BDR dipnotlarındaki 4+ haneli tutarları (TL/USD/EUR) ve rakamları regex ile kanonik forma indirgeyerek %100 rakamsal doğruluk denetimi yapar.
        - ⚡ **RapidFuzz Lexical Engine:** Türkçe çoğul ekleri (-lar/-ler) ve yazım varyasyonlarına takılmadan başlık bazlı bulanık metin eşleştirmesi yapar.
        - 🔍 **Multi-Layer Hybrid Grounding Engine:** Üretilen her iddianın ham BDR metnindeki dipnot parçalarıyla uyuşup uyuşmadığını 3 katmanlı doğrulama ile denetler.
        - 🛡️ **Post-Hoc Reconciler Guard & Sanitizer Agent:** LLM uzlaştırma adımından sonra kod seviyesinde özet/roll-up eleme filtresi ve Regex + LLM Sanitizer Süzgeci uygulayarak jenerik/şablon cümleleri eler ve mükemmel kaliteyi garanti eder.
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
    st.caption("Aşağıdaki alanlardan System Prompt ve User Prompt metinlerini canlı olarak düzenleyebilirsiniz:")

    # Dosyadaki mevcut halini oku (Senkronizasyon kontrolü için)
    target_prompt_file = Config.BASE_DIR / "prompts" / PROMPT_FILE_NAME
    disk_sys, disk_usr = PromptLoader.load_prompt_md(PROMPT_FILE_NAME)
    
    is_modified = (
        st.session_state.active_system_prompt != disk_sys
        or st.session_state.active_user_template != disk_usr
    )

    if is_modified:
        st.warning("🟡 **Değişiklik Algılandı:** Prompt üzerinde düzenleme yaptınız. Analizde kullanılacaktır. Kalıcı kaydetmek veya iptal etmek için aşağıdaki butonları kullanabilirsiniz.")
    else:
        st.success("🟢 **Senkronize:** Ekranda gördüğünüz prompt metinleri dosya içeriği ile tamamen aynıdır.")

    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
    with col_btn1:
        if st.button("💾 1. Değişiklikleri Kaydet", help="Yaptığınız değişiklikleri `prompts/bdr_analyst_v1.md` dosyasına kalıcı olarak yazar."):
            full_prompt_md = f"# BDR Finansal Risk Analist Sistem Promptu (v1 - Dinamik)\n\n## SYSTEM_PROMPT\n{st.session_state.active_system_prompt}\n\n---\n\n## USER_PROMPT\n{st.session_state.active_user_template}\n"
            target_prompt_file.write_text(full_prompt_md, encoding="utf-8")
            PromptLoader._cache.clear()
            st.success("✅ Değişiklikler dosyaya kalıcı olarak kaydedildi!")
            st.rerun()

    with col_btn2:
        if st.button("↩️ 2. Değişiklikleri İptal Et", disabled=not is_modified, help="Henüz kaydedilmemiş ekran değişikliklerini siler ve dosyadaki son haline geri döner."):
            PromptLoader._cache.clear()
            fresh_sys, fresh_usr = PromptLoader.load_prompt_md(PROMPT_FILE_NAME)
            st.session_state.active_system_prompt = fresh_sys
            st.session_state.active_user_template = fresh_usr
            st.info("ℹ️ Kaydedilmemiş değişiklikler iptal edildi, dosyadaki son durum yüklendi.")
            st.rerun()

    with col_btn3:
        if st.button("🔄 3. Fabrika Ayarlarına Dön", help="Promptları ilk orijinal şablon haline sıfırlar."):
            PromptLoader._cache.clear()
            sys_orig, usr_orig = PromptLoader.load_prompt_md(PROMPT_FILE_NAME)
            st.session_state.active_system_prompt = sys_orig
            st.session_state.active_user_template = usr_orig
            st.success("✅ Promptlar orijinal şablona sıfırlandı!")
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
    karakter_sayisi = len(bdr_content)
    kelime_sayisi = len(bdr_content.split())
    token_sayisi = round(karakter_sayisi / 3.8)
    st.caption(f"📊 **Metin Büyüklüğü:** {karakter_sayisi:,} Karakter | {kelime_sayisi:,} Kelime | **~{token_sayisi:,} Token**")

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
    bdr_karakter = len(bdr_content)
    _deg = {m["id"]: Config.model_bdr_degerlendirmesi(m, bdr_karakter) for m in all_models if m.get("id")}

    model_secenekleri = [mid for mid in _deg if _deg[mid]["secilebilir"]]
    varsayilan_ensemble = [m for m in pipeline_cfg.get("map_models", []) if m in model_secenekleri]
    secili_ensemble = st.multiselect(
        f"Ensemble Map Modelleri (Eşzamanlı Taramayı Yapacak AI Modelleri)  ·  BDR ~{bdr_karakter // 1000}k karakter",
        options=model_secenekleri,
        default=varsayilan_ensemble or model_secenekleri[:1],
        format_func=lambda mid: f"{_deg[mid]['rozet']} {mid} — {_deg[mid]['ozet']}",
        help="Bu alanda işaretlediğiniz tüm modeller BDR metnini eşzamanlı olarak tarar. config.json dosyasındaki 'map_models' yalnızca ilk varsayılan seçimdir; buradan yaptığınız seçim geçerli olur."
    )
    st.info("💡 **Bilgi:** Burada seçtiğiniz modeller `Ensemble Map` aşamasında BDR parçalarını eşzamanlı tarar. Uzlaştırma, Critic ve Sentez rollerini aşağıdan özelleştirebilirsiniz.")

    for mid in secili_ensemble:
        for uyari in _deg[mid]["uyarilar"]:
            st.caption(f"⚠️ {mid}: {uyari}")

    with st.expander("🎛️ Pipeline Ajan Rollerini Özelleştir (Reconciler / Critic / Sanitizer / Sentez Modelleri)"):
        st.caption("Uzlaştırma, Eleştirmen (Critic), Temizlik (Sanitizer) ve Sentez aşamalarında kullanılacak modelleri seçebilirsiniz:")
        r_idx = model_secenekleri.index(pipeline_cfg.get("reconciler_model")) if pipeline_cfg.get("reconciler_model") in model_secenekleri else 0
        c_idx = model_secenekleri.index(pipeline_cfg.get("critic_model")) if pipeline_cfg.get("critic_model") in model_secenekleri else 0
        san_default = pipeline_cfg.get("sanitizer_model", pipeline_cfg.get("critic_model"))
        san_idx = model_secenekleri.index(san_default) if san_default in model_secenekleri else 0
        s_idx = model_secenekleri.index(pipeline_cfg.get("synthesis_model")) if pipeline_cfg.get("synthesis_model") in model_secenekleri else 0

        pipe_reconciler = st.selectbox(
            "🤝 Uzlaştırma (Reconciler) Modeli",
            options=model_secenekleri,
            index=r_idx,
            help="Ensemble modellerinden gelen ham risk bulgularını eşleştirir, tekrarları eler ve çelişkileri uzlaştırır."
        )
        st.caption("💡 **Uzlaştırma Ajanı:** Farklı modellerin bulduğu ham riskleri anlamsal kümeleyip deduplikasyon yapar.")

        pipe_critic = st.selectbox(
            "🕵️ Eleştirmen (Critic) Modeli",
            options=model_secenekleri,
            index=c_idx,
            help="Uzlaştırılmış bulguları BDR dipnot metinleriyle çapraz denetler; halüsinasyon ve asılsız iddiaları eler."
        )
        st.caption("💡 **Eleştirmen Ajanı:** Bulguları BDR orijinal metniyle grounding testine tabi tutar, kanıtsız riskleri geri çevirir.")

        pipe_sanitizer = st.selectbox(
            "🧹 Temizlik (Sanitizer) Modeli",
            options=model_secenekleri,
            index=san_idx,
            help="Jenerik etki cümlelerini ve risk mekanizması içermeyen yalın bilanço kalemlerini süzen hızlı filtre ajanı."
        )
        st.caption("💡 **Temizlik Ajanı:** Jenerik/şablon cümleleri somut etki analizleriyle günceller ve salt bilanço bakiyelerini rapordan temizler.")

        pipe_synthesis = st.selectbox(
            "🧩 Sentez (Synthesis) Modeli",
            options=model_secenekleri,
            index=s_idx,
            help="Tüm onaylı riskleri, finansal rasyoları ve denetçi görüşünü birleştirerek nihai kredilendirme raporunu oluşturur."
        )
        st.caption("💡 **Sentez Ajanı:** Doğrulanmış tüm bulguları ve rasyoları konsolide edip Kredi Komite Raporunu ve Karar Eğilimini yazar.")

        # Config pipeline ayarlarını oturum içi dinamik güncelle
        Config.update_pipeline_config(
            reconciler=pipe_reconciler,
            critic=pipe_critic,
            sanitizer=pipe_sanitizer,
            synthesis=pipe_synthesis,
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

        st.caption(f"Modeller — {model_rolleri_satiri(secili_ensemble)}")
        durum_alani = st.empty()
        log_alani = st.empty()
        yapilan = set()
        son_guncelleme = {}
        log_satirlari: List[str] = []
        takipci = ilerleme_takipcisi(log_satirlari.append, secili_ensemble)
        with st.spinner("🔗 Pipeline çalışıyor…"):
            for adim in pipe_graph.stream(pipe_baslangic, config=pipe_cfg_run, stream_mode="updates"):
                for node, guncelleme in adim.items():
                    yapilan.add(node)
                    if guncelleme:
                        son_guncelleme[node] = guncelleme
                    takipci(node, guncelleme or {})
                with durum_alani.container():
                    for node, etiket in FAZ_ETIKETLERI.items():
                        ozet = asama_ozeti(node, son_guncelleme.get(node, {}))
                        isaret = "✅ " if node in yapilan else "⏳ "
                        st.write(isaret + etiket + (f" — {ozet}" if ozet and node in yapilan else ""))
                log_alani.code("\n".join(log_satirlari), language="text")

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
