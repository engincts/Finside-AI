from typing import Dict, Any, List
from pathlib import Path
import streamlit as st

from config import Config
from finside.loaders import BDRLoader
from finside.models import SidebarState


def render_sidebar() -> SidebarState:
    """Kullanıcı dostu, adım adım yapılandırılmış yan kontrol panelini çizer."""
    st.sidebar.image("https://img.icons8.com/color/96/000000/bank-building.png", width=65)
    st.sidebar.title("⚙️ Kontrol Paneli")
    st.sidebar.caption("💡 Kolay Analiz: Sırasıyla 1, 2 ve 3. adımları seçip **🚀 ANALİZİ BAŞLAT** butonuna basın.")

    st.sidebar.markdown("---")

    # 1. Adım: BDR Dosyası Seçimi
    st.sidebar.markdown("### 1️⃣ BDR Raporu Seçimi")
    data_dir_files = list(Config.DATA_DIR.glob("*.txt"))
    file_options = [f.name for f in data_dir_files]

    selected_sample = st.sidebar.selectbox(
        "Hazır Örnek BDR Dosyası",
        options=file_options,
        index=0,
        help="Sistemde yüklü olan örnek Bağımsız Denetim Raporlarından birini seçin."
    )
    uploaded_file = st.sidebar.file_uploader(
        "Veya Kendi Metin (.txt) Dosyanızı Yükleyin",
        type=["txt"],
        help="Analiz etmek istediğiniz firmaya ait .txt formatındaki BDR metnini buraya yükleyin."
    )

    if uploaded_file is not None:
        bdr_content = uploaded_file.getvalue().decode("utf-8")
        bdr_name = uploaded_file.name
    else:
        sample_path = Config.DATA_DIR / selected_sample
        loader = BDRLoader(sample_path)
        bdr_info = loader.get_processed_bdr()
        bdr_content = bdr_info["content"]
        bdr_name = bdr_info["file_name"]

    st.sidebar.markdown("---")

    # 2. Adım: Çalıştırma Modu
    st.sidebar.markdown("### 2️⃣ Çalıştırma Modu")
    exec_mode = st.sidebar.radio(
        "Analiz Yöntemi",
        options=["⚡ Gerçek Canlı API (Bulut / HF)", "🧪 Mock Test Modu (Hızlı Simülasyon)"],
        index=0,
        help="API anahtarlarınız hazırsa Gerçek API, ücretsiz hızlı test için Mock Simülasyon seçin."
    )
    is_mock_mode = "Mock" in exec_mode

    st.sidebar.markdown("---")

    # 3. Adım: Modeller
    st.sidebar.markdown("### 3️⃣ AI Modelleri")
    config_data = Config.load_config()
    all_models = config_data.get("models", [])
    selected_model_ids = []

    st.sidebar.caption("Kıyaslamak istediğiniz AI modellerini işaretleyin:")

    for m in all_models:
        model_id = m.get("id")
        model_name = m.get("name")
        default_checked = m.get("enabled", False)
        if st.sidebar.checkbox(f"{model_name}", value=default_checked, key=f"chk_{model_id}"):
            selected_model_ids.append(model_id)

    if not selected_model_ids:
        st.sidebar.warning("⚠️ Lütfen analiz için en az bir model seçiniz!")

    st.sidebar.markdown("---")

    # 4. Gelişmiş Ayarlar (Opsiyonel)
    with st.sidebar.expander("🎛️ Gelişmiş Model Ayarları (Opsiyonel)"):
        st.caption("AI modellerinin yaratıcılık ve ceza parametrelerini ayarlayabilirsiniz:")
        override_temp = st.slider("Temperature (Sıcaklık)", 0.0, 1.0, 0.1, 0.05, help="Düşük değer daha tutarlı ve analitik sonuçlar üretir.")
        override_top_p = st.slider("Top-P (Sampling)", 0.1, 1.0, 0.9, 0.05)
        override_rep_penalty = st.slider("Repetition Penalty", 1.0, 1.5, 1.05, 0.05)

    hyperparams = {
        "temperature": override_temp,
        "top_p": override_top_p,
        "repetition_penalty": override_rep_penalty,
    }

    try:
        run_btn = st.sidebar.button("🚀 ANALİZİ BAŞLAT", type="primary", width="stretch")
    except TypeError:
        run_btn = st.sidebar.button("🚀 ANALİZİ BAŞLAT", type="primary", use_container_width=True)

    return SidebarState(
        bdr_content=bdr_content,
        bdr_name=bdr_name,
        is_mock_mode=is_mock_mode,
        selected_model_ids=selected_model_ids,
        hyperparams=hyperparams,
        run_btn=run_btn,
    )
