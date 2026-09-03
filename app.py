import sys
import os
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import streamlit as st

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="Finside AI — Kurumsal Kredi Tahsis Karar Destek",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Path Resolution
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from config import Config
from finside.loaders import PromptLoader
from finside.models import BenchmarkRequest
from finside.services.benchmark_service import BenchmarkService
from finside.ui.sidebar import render_sidebar
from finside.ui.tabs import (
    render_overview_tab,
    render_reports_tab,
    render_prompt_tab,
    render_input_tab,
    render_pipeline_tab,
)

# Custom Executive UI CSS Styling
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 800; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1.1rem; color: #475569; margin-bottom: 1.5rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 12px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: 600; font-size: 1rem; }
</style>
""", unsafe_allow_html=True)

# Application Header
st.markdown('<div class="main-header">🏦 Finside AI — Kurumsal Kredi Tahsis Karar Destek</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">BDR Dipnot Analizi, Kalitatif Risk Çıkarımı ve Multi-LLM Performans Karşılaştırma Paneli</div>', unsafe_allow_html=True)

# Load Initial Prompts Into Session State
if "active_system_prompt" not in st.session_state or "active_user_template" not in st.session_state:
    sys_prompt, usr_template = PromptLoader.load_prompt_md("bdr_analyst_v1.md")
    st.session_state.active_system_prompt = sys_prompt
    st.session_state.active_user_template = usr_template

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

# Render Sidebar UI
ui_state = render_sidebar()

# Handle Benchmark Run Action
if ui_state.run_btn and ui_state.selected_model_ids:
    with st.spinner("🔄 BDR Metni Analiz Ediliyor ve Model Çıktıları Üretiliyor..."):
        request = BenchmarkRequest(
            selected_model_ids=ui_state.selected_model_ids,
            bdr_content=ui_state.bdr_content,
            bdr_name=ui_state.bdr_name,
            is_mock_mode=ui_state.is_mock_mode,
            hyperparams=ui_state.hyperparams,
            system_prompt=st.session_state.active_system_prompt,
            user_template=st.session_state.active_user_template,
        )
        results_list, metrics_summary_list, zaman_asimi, session_dir = BenchmarkService.run_benchmark_suite(request)

        if zaman_asimi:
            st.warning(f"⏱️ {len(zaman_asimi)} model zaman aşımına takıldı: {', '.join(zaman_asimi)}")
        if results_list:
            st.session_state.analysis_results = results_list
            st.session_state.metrics_summary = metrics_summary_list
            st.success(f"✅ Analiz Tamamlandı. Raporlar: `{session_dir}`")
        else:
            st.error("❌ Hiçbir model zamanında yanıt veremedi.")

# Render Main View Tabs
t1, t2, t3, t4, t5 = st.tabs([
    "📊 Karşılaştırma Paneli",
    "🤖 Model Çıktı Raporları",
    "📝 Canlı Prompt Düzenleyici",
    "📄 BDR Metin Görünümü",
    "🔗 Multi-Agent Pipeline"
])

with t1: render_overview_tab(ui_state.bdr_name, ui_state.is_mock_mode)
with t2: render_reports_tab()
with t3: render_prompt_tab()
with t4: render_input_tab(ui_state.bdr_name, ui_state.bdr_content)
with t5: render_pipeline_tab(ui_state.bdr_name, ui_state.bdr_content)

