from typing import Dict, Any, List
from pathlib import Path
import streamlit as st

from config import Config
from finside.loaders import BDRLoader
from finside.models import SidebarState


def render_sidebar() -> SidebarState:
    """Kullanıcı dostu, adım adım yapılandırılmış yan kontrol panelini çizer."""
    # Sidebar genişliğini ve okunabilirliğini artırmak için özel CSS enjeksiyonu
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] {
                min-width: 420px !important;
                max-width: 450px !important;
            }
            [data-testid="stSidebar"] .stCaption {
                font-size: 0.88rem !important;
                line-height: 1.4 !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.image("https://img.icons8.com/color/96/000000/bank-building.png", width=65)
    st.sidebar.title("⚙️ Kontrol Paneli")
    st.sidebar.caption("💡 Kolay Analiz: Sırasıyla 1. ve 2. adımları seçip **🚀 ANALİZİ BAŞLAT** butonuna basın.")

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

    # 2. Adım: Modeller
    st.sidebar.markdown("### 2️⃣ AI Model Seçimi & Teknik Metrikler")
    config_data = Config.load_config()
    all_models = config_data.get("models", [])
    selected_model_ids = []

    bdr_karakter = len(bdr_content)
    bdr_kelime = len(bdr_content.split())
    bdr_token = round(bdr_karakter / 3.8)
    st.sidebar.caption(
        f"📄 **Dosya:** `{bdr_name}`  \n"
        f"📊 **BDR Hacmi:** {bdr_karakter:,} Karakter · {bdr_kelime:,} Kelime (`~{bdr_token:,} Token`)"
    )

    # Modelleri Kategorilere Ayırma
    embedder_models = [m for m in all_models if "embedding" in m.get("id", "") or "embed" in m.get("id", "")]
    kloudeks_models = [m for m in all_models if ("qwen3" in m.get("id", "") or m.get("id") == "gpt-oss-120b") and m not in embedder_models]
    cloud_models = [m for m in all_models if m.get("provider") in ("gemini", "openai", "anthropic") and m not in kloudeks_models and m not in embedder_models]
    hf_models = [m for m in all_models if m.get("provider") == "huggingface" and m not in kloudeks_models and m not in embedder_models]
    mock_models = [m for m in all_models if m.get("provider") == "mock"]

    tab_cloud, tab_hf, tab_embed, tab_mock = st.sidebar.tabs([
        "🌐 Bulut Servisleri",
        "🤗 Açık Kaynak",
        "🧬 Vektör & Embedder",
        "🧪 Test & Simülasyon"
    ])

    def _render_model_cards(model_list: List[dict]):
        for m in model_list:
            model_id = m.get("id")
            model_name = m.get("name")
            provider = m.get("provider", "")
            deg = Config.model_bdr_degerlendirmesi(m, bdr_karakter)

            secildi = st.checkbox(
                f"{deg['rozet']} {model_name}",
                value=m.get("enabled", False),
                key=f"chk_{model_id}",
            )

            # Detaylı Teknik Özellikler Metin Kutusu (Standart Yapay Zeka Terimleri)
            st.caption(
                f"📥 **Context Window:** {deg['context_window_str']}  \n"
                f"📤 **Max Output Tokens:** {deg['max_tokens_str']}  \n"
                f"🎯 **BDR Suitability:** {deg['bdr_etiketi']}  \n"
                f"🔑 **API Key Status:** {deg['api_key_status']}"
            )

            if deg["uyarilar"]:
                with st.expander("ℹ️ Detay & Uyarılar"):
                    for u in deg["uyarilar"]:
                        st.write(f"- {u}")

            st.markdown("---")

            if secildi:
                selected_model_ids.append(model_id)

    with tab_cloud:
        _render_model_cards(cloud_models)

    with tab_hf:
        st.markdown("#### 🏛️ Kloudeks Mia (KKB Kurumsal Altyapı)")
        st.caption("KKB bünyesinde sunulan Kloudeks Mia açık kaynak modelleri:")
        _render_model_cards(kloudeks_models)
        st.markdown("#### 🚀 Diğer Açık Kaynak Modeller (HuggingFace)")
        _render_model_cards(hf_models)

    with tab_embed:
        st.sidebar.info("📐 **Vektör & Embedding Motoru:**\n\nBu modeller metin üretimi için değil; BDR dipnot risklerinin vektörleştirilmesi ve Kosinüs Benzerliği (Cosine Similarity) ile mükerrer risklerin tekleştirilmesi (Dedupe) için kullanılır.")
        _render_model_cards(embedder_models)

    with tab_mock:
        _render_model_cards(mock_models)

    mock_model_ids = {m.get("id") for m in mock_models if m.get("id")}
    is_mock_mode = bool(selected_model_ids) and all(m_id in mock_model_ids for m_id in selected_model_ids)

    if not selected_model_ids:
        st.sidebar.warning("⚠️ Lütfen analiz için en az bir AI modeli seçiniz!")

    st.sidebar.markdown("---")

    # 3. Gelişmiş Ayarlar (Opsiyonel)
    with st.sidebar.expander("🎛️ 3️⃣ Gelişmiş Model Ayarları (Opsiyonel)"):
        st.caption("AI modellerinin analitik hassasiyet ve ceza parametrelerini özelleştirebilirsiniz:")
        
        override_temp = st.slider(
            "Temperature (Sıcaklık)",
            0.0, 1.0, 0.1, 0.05,
            help=(
                "🎯 **Temperature (0.0 - 1.0):** Modelin yanıt üretirken gösterdiği rastgelelik/yaratıcılık seviyesi.\n\n"
                "• **0.0 - 0.1 (Tavsiye Edilen):** Deterministik ve matematiksel hassasiyet. Modele verilen Prompt'a ve BDR metnine %100 sadık kalır, uydurma/hallüsinasyon riskini engeller.\n\n"
                "• **0.7 - 1.0:** Serbest metin yazımı (Finansal analiz ve Kredi Komite raporları için tavsiye EDİLMEZ)."
            )
        )
        st.caption("ℹ️ **Önerilen (0.10):** Prompta ve BDR metnine %100 sadık deterministik analiz.")

        override_top_p = st.slider(
            "Top-P (Nucleus Sampling)",
            0.1, 1.0, 0.9, 0.05,
            help=(
                "🔍 **Top-P (0.1 - 1.0):** Modelin kelime seçimi yaparken dikkate aldığı olasılık havuzunun genişliği.\n\n"
                "• **0.90 (Tavsiye Edilen):** En yüksek olasılıklı finansal terim havuzunu kullanarak anlamsız kelime sapmalarını filtreler ve dil akıcılığını korur."
            )
        )
        st.caption("ℹ️ **Önerilen (0.90):** Finansal literatüre ve terimlere uygun kelime seçimi.")

        override_rep_penalty = st.slider(
            "Repetition Penalty (Tekrar Cezası)",
            1.0, 1.5, 1.05, 0.05,
            help=(
                "🚫 **Repetition Penalty (1.0 - 1.5):** Modelin aynı kelimeleri veya cümle kalıplarını üst üste tekrarlamasını engelleyen ceza katsayısı.\n\n"
                "• **1.00:** Ceza yok (Bazı açık kaynak modellerde aynı cümleyi döngüye sokabilir).\n\n"
                "• **1.05 (Tavsiye Edilen):** Kelime döngülerini önler, akıcı ve özgün cümle yapısı sağlar."
            )
        )
        st.caption("ℹ️ **Önerilen (1.05):** Gereksiz kelime ve cümle tekrarlarını önler.")

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
