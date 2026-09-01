import os
import sys
import signal
from pathlib import Path

# Anında Anlık Kesinti (Instant Ctrl+C Exit) - Event Loop Kilitlenmesi ve Traceback Önleyici
def force_immediate_exit(signum, frame):
    try:
        sys.stdout.write("\n👋 Finside AI kapatıldı.\n")
        sys.stdout.flush()
    except Exception:
        pass
    os._exit(0)

try:
    signal.signal(signal.SIGINT, force_immediate_exit)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, force_immediate_exit)
except Exception:
    pass

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import streamlit as st
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_PARALLEL_MODELS = 8
BDR_PREVIEW_CHARS = 20000

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="Finside AI — Kurumsal Kredi Tahsis Karar Destek",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Set Path Resolution
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from config import Config
from finside.loaders import BDRLoader, PromptLoader
from finside.analyzer import BDRAnalyzer
from finside.writers import ReportWriter


def run_model_analysis(
    model_id,
    all_models,
    config_data,
    is_mock_mode,
    hyperparams,
    system_prompt,
    user_template,
    bdr_content,
    session_dir,
):
    model_cfg = Config.get_model_by_id(model_id)
    if not model_cfg:
        for item in all_models:
            if item.get("id") == model_id:
                model_cfg = {**config_data, **item}
                break

    if is_mock_mode:
        model_cfg["provider"] = "mock"

    model_cfg["temperature"] = hyperparams["temperature"]
    model_cfg["top_p"] = hyperparams["top_p"]
    model_cfg["repetition_penalty"] = hyperparams["repetition_penalty"]

    analyzer = BDRAnalyzer(
        model_config=model_cfg,
        custom_system_prompt=system_prompt,
        custom_user_template=user_template,
    )
    report = analyzer.analyze(bdr_content)
    md_content = analyzer.format_report_as_markdown(report)
    ReportWriter.save_model_report(session_dir, model_id, report, md_content)

    result = {
        "model_id": model_id,
        "model_name": model_cfg.get("name", model_id),
        "report": report,
        "md_content": md_content,
        "config": model_cfg,
    }
    metrics = {
        "model_id": model_id,
        "model_name": model_cfg.get("name", model_id),
        "provider": model_cfg.get("provider"),
        "duration_sec": report.analiz_suresi_saniye,
        "is_mock_fallback": report.is_mock_fallback,
        "fallback_reason": report.fallback_reason,
        "risk_count": len(report.tespit_edilen_riskler),
        "karar_egilimi": report.karar_egilimi.value,
        "denetci_gorusu": report.denetci_gorusu.value if report.denetci_gorusu else None,
    }
    return {"result": result, "metrics": metrics}


# Custom Executive UI CSS Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #475569;
        margin-bottom: 1.5rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        font-weight: 600;
        font-size: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Application Header
st.markdown('<div class="main-header">🏦 Finside AI — Kurumsal Kredi Tahsis Karar Destek</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">BDR Dipnot Analizi, Kalitatif Risk Çıkarımı ve Multi-LLM Performans Karşılaştırma Paneli</div>', unsafe_allow_html=True)

# LOAD INITIAL PROMPT TEMPLATE
PROMPT_FILE_NAME = "bdr_analyst_v1.md"
default_system_prompt, default_user_template = PromptLoader.load_prompt_md(PROMPT_FILE_NAME)

if "active_system_prompt" not in st.session_state:
    st.session_state.active_system_prompt = default_system_prompt

if "active_user_template" not in st.session_state:
    st.session_state.active_user_template = default_user_template

# SIDEBAR: Configuration & Model Selections
st.sidebar.image("https://img.icons8.com/color/96/000000/bank-building.png", width=70)
st.sidebar.title("⚙️ Kontrol Paneli")

# 1. Input BDR File Selector / Uploader
st.sidebar.subheader("📄 1. BDR Metin Dosyası Seçimi")
data_dir_files = list(Config.DATA_DIR.glob("*.txt"))
file_options = [f.name for f in data_dir_files]

selected_sample = st.sidebar.selectbox("Test BDR Dosyası Seçin", options=file_options, index=0)
uploaded_file = st.sidebar.file_uploader("Veya Kendi BDR (.txt) Dosyanızı Yükleyin", type=["txt"])

if uploaded_file is not None:
    bdr_content = uploaded_file.getvalue().decode("utf-8")
    bdr_name = uploaded_file.name
else:
    sample_path = Config.DATA_DIR / selected_sample
    loader = BDRLoader(sample_path)
    bdr_info = loader.get_processed_bdr()
    bdr_content = bdr_info["content"]
    bdr_name = bdr_info["file_name"]

# 2. Execution Mode (Mock vs Live API)
st.sidebar.subheader("🧪 2. Çalıştırma Modu")
exec_mode = st.sidebar.radio(
    "Mod Seçimi",
    options=["⚡ Gerçek Canlı API (Bulut / HF)", "🧪 Mock Test Modu (Simülasyon)"],
    index=0
)
is_mock_mode = "Mock" in exec_mode

# 3. Model Selections from config.json
st.sidebar.subheader("🤖 3. Değerlendirilecek Modeller")
config_data = Config.load_config()
all_models = config_data.get("models", [])

selected_model_ids = []
st.sidebar.caption(
    "Bu ayarlar (mod, model, parametreler) yalnızca **📊 Karşılaştırma Paneli** "
    "tek-model kıyaslaması içindir. 🔗 Multi-Agent Pipeline sekmesi bağımsız çalışır."
)

for m in all_models:
    model_id = m.get("id")
    model_name = m.get("name")
    default_checked = m.get("enabled", False)
    
    if st.sidebar.checkbox(f"{model_name}", value=default_checked, key=f"chk_{model_id}"):
        selected_model_ids.append(model_id)

if not selected_model_ids:
    st.sidebar.warning("⚠️ Lütfen en az bir model seçiniz!")

# 4. Advanced Hyperparameters (Expander)
with st.sidebar.expander("🎛️ Gelişmiş Çıkarım Parametreleri"):
    override_temp = st.slider("Temperature (Sıcaklık)", 0.0, 1.0, 0.1, 0.05)
    override_top_p = st.slider("Top-P (Nucleus Sampling)", 0.1, 1.0, 0.9, 0.05)
    override_rep_penalty = st.slider("Repetition Penalty (Tekrar Cezası)", 1.0, 1.5, 1.05, 0.05)

# Sidebar Action Button (Streamlit 1.62 Compatible)
try:
    run_analysis_btn = st.sidebar.button("🚀 ANALİZİ BAŞLAT", type="primary", width="stretch")
except TypeError:
    run_analysis_btn = st.sidebar.button("🚀 ANALİZİ BAŞLAT", type="primary", use_container_width=True)

# MAIN BODY TABS
tab_overview, tab_reports, tab_prompt, tab_input, tab_pipeline = st.tabs([
    "📊 Karşılaştırma Paneli",
    "🤖 Model Çıktı Raporları",
    "📝 Canlı Prompt Düzenleyici",
    "📄 BDR Metin Görünümü",
    "🔗 Multi-Agent Pipeline"
])

# SESSION STATE STORAGE FOR RESULTS
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

# RUN ANALYSIS LOGIC
if run_analysis_btn and selected_model_ids:
    with st.spinner("🔄 BDR Metni Analiz Ediliyor ve Model Çıktıları Üretiliyor..."):
        # Create session directory
        session_dir, input_stem = ReportWriter.create_session_directory(bdr_name)

        hyperparams = {
            "temperature": override_temp,
            "top_p": override_top_p,
            "repetition_penalty": override_rep_penalty,
        }
        active_system_prompt = st.session_state.active_system_prompt
        active_user_template = st.session_state.active_user_template

        outputs = {}
        with ThreadPoolExecutor(max_workers=min(len(selected_model_ids), MAX_PARALLEL_MODELS)) as executor:
            futures = {
                executor.submit(
                    run_model_analysis,
                    m_id,
                    all_models,
                    config_data,
                    is_mock_mode,
                    hyperparams,
                    active_system_prompt,
                    active_user_template,
                    bdr_content,
                    session_dir,
                ): m_id
                for m_id in selected_model_ids
            }
            for future in as_completed(futures):
                outputs[futures[future]] = future.result()

        results_list = [outputs[m_id]["result"] for m_id in selected_model_ids]
        metrics_summary_list = [outputs[m_id]["metrics"] for m_id in selected_model_ids]

        # Save summary metrics report
        ReportWriter.save_summary_metrics(session_dir, input_stem, metrics_summary_list)
        st.session_state.analysis_results = results_list
        st.session_state.metrics_summary = metrics_summary_list
        st.success(f"✅ Analiz Başarıyla Tamamlandı! Raporlar kaydedildi: `{session_dir}`")

# TAB 1: EXECUTIVE SUMMARY & METRICS COMPARISON
with tab_overview:
    st.subheader("📊 Model Karşılaştırma & Metrik Özet Tablosu")
    
    if st.session_state.analysis_results:
        metrics = st.session_state.metrics_summary

        # Top Metric Cards
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("İşlenen Dosya", bdr_name)
        col2.metric("Çalıştırılan Model Sayısı", len(metrics))
        avg_latency = sum(m["duration_sec"] for m in metrics) / len(metrics) if metrics else 0.0
        col3.metric("Ortalama Analiz Süresi", f"{avg_latency:.2f} sn")
        active_mode = "🧪 Mock Test Modu" if is_mock_mode else "⚡ Canlı API"
        col4.metric("Çalıştırma Modu", active_mode)

        st.markdown("---")

        # Summary Table View
        table_data = []
        for m in metrics:
            status_badge = "⚠️ Mock Fallback" if m["is_mock_fallback"] else "✅ Gerçek API"
            table_data.append({
                "Model ID": m["model_id"],
                "Model Adı": m["model_name"],
                "Sağlayıcı": m["provider"],
                "Analiz Süresi (sn)": f"{m['duration_sec']:.2f}s",
                "Durum": status_badge,
                "Risk Kalemi Sayısı": f"{m['risk_count']} Kalem",
                "Denetçi Görüşü": m["denetci_gorusu"] or "N/A",
                "Kredi Komitesi Kararı": m["karar_egilimi"]
            })

        try:
            st.dataframe(table_data, width="stretch")
        except TypeError:
            st.dataframe(table_data, use_container_width=True)
    else:
        st.info("👈 Analizi başlatmak için sol menüden modellerinizi seçip **🚀 ANALİZİ BAŞLAT** butonuna tıklayınız.")

# TAB 2: INDIVIDUAL MODEL REPORTS VIEW
with tab_reports:
    if st.session_state.analysis_results:
        st.subheader("🤖 Model Çıktı Raporları")
        
        results = st.session_state.analysis_results
        st.caption("Detaylı raporu görmek için ilgili modelin başlığına tıklayın.")

        for r in results:
            report = r["report"]
            gorus = report.denetci_gorusu.value if report.denetci_gorusu else "Belirtilmemiş"
            fallback_mark = " ⚠️ Mock" if report.is_mock_fallback else ""
            label = f"{r['model_name']} — {report.karar_egilimi.value}{fallback_mark}"

            with st.expander(label, expanded=False):
                if report.is_mock_fallback:
                    st.warning(f"⚠️ **Mock Fallback Uyarısı**: Gerçek API hatası nedeniyle simülasyon raporu gösterilmektedir. (Hata: {report.fallback_reason})")

                # Key Rapor Kartları
                c1, c2, c3 = st.columns(3)
                c1.info(f"**Firma:** {report.firma_adi}")
                c2.success(f"**Denetçi Görüşü:** {gorus}")
                c3.warning(f"**Karar Eğilimi:** {report.karar_egilimi.value}")

                st.markdown("---")
                st.markdown(r["md_content"])
    else:
        st.info("👈 Henüz bir analiz çalıştırılmadı. Sol menüden **🚀 ANALİZİ BAŞLAT** butonuna tıklayabilirsiniz.")

# TAB 3: DYNAMIC PROMPT EDITOR & INSPECTOR
with tab_prompt:
    st.subheader("📝 Canlı Prompt Düzenleme & İnceleme Paneli")
    st.caption("Aşağıdaki alanlardan System Prompt ve User Prompt metinlerini canlı olarak değiştirebilir ve analizde kullanabilirsiniz:")

    col_btn1, col_btn2, col_spacer = st.columns([1, 1, 2])
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
        st.markdown("#### 🟢 SYSTEM_PROMPT (Rol & Talimatlar)")
        edited_sys = st.text_area(
            "System Prompt Düzenle", 
            value=st.session_state.active_system_prompt, 
            height=500,
            key="sys_area"
        )
        st.session_state.active_system_prompt = edited_sys

    with col_usr:
        st.markdown("#### 🔵 USER_PROMPT (Girdi Şablonu)")
        edited_usr = st.text_area(
            "User Prompt Düzenle ({{bdr_text}} alanını koruyunuz)", 
            value=st.session_state.active_user_template, 
            height=500,
            key="usr_area"
        )
        st.session_state.active_user_template = edited_usr

# TAB 4: RAW BDR INPUT TEXT VIEWER
with tab_input:
    st.subheader(f"📄 İşlenen BDR Dosya İçeriği: `{bdr_name}`")
    st.caption(f"Karakter Sayısı: {len(bdr_content):,} | Kelime Sayısı: {len(bdr_content.split()):,}")

    st.download_button(
        "⬇️ Tam BDR Metnini İndir (.txt)",
        data=bdr_content,
        file_name=bdr_name,
        mime="text/plain",
    )

    if len(bdr_content) > BDR_PREVIEW_CHARS:
        st.info(
            f"Tarayıcı performansı için ilk {BDR_PREVIEW_CHARS:,} karakter gösteriliyor. "
            "Tamamı için indirme butonunu kullanın."
        )
        st.text(bdr_content[:BDR_PREVIEW_CHARS])
        with st.expander("Tam metni yine de göster (tarayıcıyı yavaşlatabilir)"):
            st.text(bdr_content)
    else:
        st.text(bdr_content)

# TAB 5: MULTI-AGENT PIPELINE (Faz 9.6)
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

if "pipeline_sonucu" not in st.session_state:
    st.session_state.pipeline_sonucu = None

with tab_pipeline:
    st.subheader("🔗 Multi-Agent BDR Analiz Pipeline")
    st.caption(
        "Segmentasyon → Triyaj → Ensemble Map → Grounding / Uzlaştırma / Critic → Sentez → QA. "
        "Tasarım: `docs/PIPELINE_DESIGN.md`"
    )
    st.warning(
        "Bu sekme **Karşılaştırma Paneli'nden tamamen bağımsızdır** — soldaki mod / model / "
        "parametre ayarları burada geçerli değildir. Pipeline BDR başına **20-45 LLM çağrısı** "
        "(~500K-900K token) yapar. Önce Karşılaştırma Paneli'nde modelleri kıyaslayıp en iyi "
        "2-3'ünü aşağıya ensemble olarak seçin, sonra çalıştırın."
    )

    pipeline_cfg = config_data.get("pipeline", {})
    model_secenekleri = [m.get("id") for m in all_models]
    varsayilan_ensemble = [m for m in pipeline_cfg.get("map_models", []) if m in model_secenekleri]
    secili_ensemble = st.multiselect(
        "Ensemble Map Modelleri (segment grubu başına paralel çalışır)",
        options=model_secenekleri,
        default=varsayilan_ensemble or model_secenekleri[:1],
    )
    maliyet_onay = st.checkbox("Yüksek token maliyetini anladım, pipeline'ı çalıştır")

    try:
        pipeline_btn = st.button(
            "🔗 PIPELINE BAŞLAT", type="primary", width="stretch", disabled=not maliyet_onay
        )
    except TypeError:
        pipeline_btn = st.button(
            "🔗 PIPELINE BAŞLAT", type="primary", use_container_width=True, disabled=not maliyet_onay
        )

    if pipeline_btn and not secili_ensemble:
        st.warning("⚠️ En az bir ensemble modeli seçiniz.")
    elif pipeline_btn:
        from langgraph.checkpoint.memory import MemorySaver
        from finside.pipeline.graph import build_graph

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
        st.success(f"✅ Pipeline tamamlandı. Çıktılar: `{pipe_session_dir}`")

    pipe_sonuc = st.session_state.pipeline_sonucu
    if pipe_sonuc and pipe_sonuc.get("nihai"):
        nr = pipe_sonuc["nihai"]
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.info(f"**Firma:** {nr.get('firma_adi')}")
        c2.success(f"**Denetçi Görüşü:** {nr.get('denetci_gorusu') or '—'}")
        c3.warning(f"**Karar Eğilimi:** {nr.get('karar_egilimi')}")

        for bayrak in nr.get("qa_bayraklari", []):
            st.error(f"⚠️ QA: {bayrak}")

        izi = nr.get("pipeline_izi") or {}
        if izi:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("LLM Çağrısı", izi.get("toplam_llm_cagrisi"))
            m2.metric("Girdi Token (~)", f"{izi.get('tahmini_girdi_token', 0):,}")
            m3.metric("Süre (sn)", izi.get("toplam_sure_sn"))
            m4.metric("Tahmini USD", izi.get("tahmini_usd"))

        st.markdown(f"### ⚠️ {len(nr.get('tespit_edilen_riskler', []))} Kalitatif Risk Kalemi")
        st.markdown(f"**Genel Kredi Risk Özeti:** {nr.get('genel_kredi_risk_ozeti')}")
        st.markdown(f"**Analist Gerekçesi:** {nr.get('analist_gerekce_metni')}")
        with st.expander("Nihai rapor (JSON)"):
            st.json(nr)
