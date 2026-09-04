import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

CONFIG_JSON_PATH = BASE_DIR / "config.json"

PIPELINE_DEFAULTS: Dict[str, Any] = {
    "map_models": ["qwen3-coder-30b", "gpt-oss-120b"],
    "triage_model": "qwen3-omni-30b",
    "reconciler_model": "gpt-oss-120b",
    "critic_model": "gpt-oss-120b",
    "sanitizer_model": "qwen3-omni-30b",
    "synthesis_model": "gpt-oss-120b",
    "segmenter_fallback_model": "qwen3-omni-30b",
    "segmenter_guven_esigi": 0.6,
    "segment_grup_karakter_butcesi": 88000,
    "grounding_esigi": 85,
    "grounding_katimod": False,
    "max_critic_turu": 2,
}


class Config:
    """Tek Noktadan Yönetim (Centralized Configuration & Single Source of Truth).
    Projedeki tüm sabitler, eşik değerleri, limitler ve dizin tanımları bu sınıfta toplanmıştır.
    """
    # 1. Dizin ve Dosya Yolları (Paths)
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data" / "bdr_samples"
    OUTPUT_DIR: Path = BASE_DIR / "outputs"
    PROMPTS_DIR: Path = BASE_DIR / "prompts"

    # 2. Çalıştırma & UI Benchmark Ayarları
    MAX_PARALLEL_MODELS: int = 8
    BENCHMARK_MAX_WAIT_SEC: int = 600
    BDR_PREVIEW_CHARS: int = 20_000

    # 3. Analizör & Parçalama (Chunking) Ayarları
    DEFAULT_MAX_INPUT_CHARS: int = 150_000
    TRUNCATE_MAX_CHARS: int = 60_000
    CHUNK_UTILIZATION: float = 0.9
    MAX_CHUNK_WORKERS: int = 4

    PROVIDER_INPUT_LIMITS: Dict[str, int] = {
        "huggingface": 250_000,
        "openai": 480_000,
        "anthropic": 760_000,
        "gemini": 3_800_000,
        "mock": 10_000_000,
    }

    # 4. Tekleştirme & Embedding Ayarları (Deduplication)
    EMBED_MODEL: str = "text-embedding-3-small"
    COVERAGE_THRESHOLD: float = 0.80
    JACCARD_THRESHOLD: float = 0.60
    NEAR_DUP_THRESHOLD: float = 0.88
    # Başlık kümeleme eşiği (rapidfuzz token_sort_ratio, 0-100). Türkçe çoğul eki
    # (-lar/-ler) ve birim yazım farkı ("116.737 TL" vs "116.737 bin TL") gibi
    # yüzeysel farkları aynı kaleme indirir (~92-96), ama "alacaklar" vs "borçlar"
    # gibi karşıt kalemleri ayrı tutar (~86). 90 bu ikisini ayıran eşik.
    BASLIK_BENZERLIK_ESIGI: int = 90
    EMBED_API_KEY_ENV: str = "OPENAI_API_KEY"

    # 5. Segmentasyon Ayarları (BDR Segmentation)
    BEKLENEN_MIN_SEGMENT: int = 12
    BEKLENEN_MAX_SEGMENT: int = 90
    MIN_SEGMENT_KARAKTER: int = 300
    YETERLI_SEGMENT: int = 10
    LLM_GIRDI_KARAKTER_SINIRI: int = 200_000

    # 6. LLM Token & Reasoning Haritası
    EFFORT_TOKEN_MAP: Dict[str, int] = {
        "low": 2048,
        "medium": 4096,
        "high": 8192,
        "auto": 8192,
    }

    _config_data: Optional[Dict[str, Any]] = None

    @classmethod
    def load_config(cls, force_reload: bool = False) -> Dict[str, Any]:
        if cls._config_data is None or force_reload:
            with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                cls._config_data = json.load(f)
        return cls._config_data

    @classmethod
    def update_pipeline_config(
        cls,
        triage: Optional[str] = None,
        reconciler: Optional[str] = None,
        critic: Optional[str] = None,
        sanitizer: Optional[str] = None,
        synthesis: Optional[str] = None,
    ) -> None:
        cfg = cls.load_config()
        if "pipeline" not in cfg:
            cfg["pipeline"] = {}
        if triage:
            cfg["pipeline"]["triage_model"] = triage
        if reconciler:
            cfg["pipeline"]["reconciler_model"] = reconciler
        if critic:
            cfg["pipeline"]["critic_model"] = critic
        if sanitizer:
            cfg["pipeline"]["sanitizer_model"] = sanitizer
        if synthesis:
            cfg["pipeline"]["synthesis_model"] = synthesis


    @classmethod
    def get_enabled_models(cls) -> List[Dict[str, Any]]:
        config = cls.load_config()
        defaults = {
            "temperature": config.get("default_temperature", 0.1),
            "max_tokens": config.get("default_max_tokens", 4096),
            "top_p": config.get("default_top_p", 0.9),
            "repetition_penalty": config.get("default_repetition_penalty", 1.0),
            "reasoning_effort": config.get("default_reasoning_effort", "medium"),
            "strict_schema": config.get("default_strict_schema", True),
            "prompt_file": config.get("default_prompt_file", "bdr_analyst_v1.md")
        }
        
        merged_models = []
        for m in config.get("models", []):
            if m.get("enabled", False):
                merged = {**defaults, **m}
                merged_models.append(merged)
        return merged_models

    @classmethod
    def get_model_by_id(cls, model_id: str) -> Optional[Dict[str, Any]]:
        for m in cls.get_enabled_models():
            if m.get("id") == model_id:
                return m
        return None

    @classmethod
    def get_api_key_for_model(cls, model_config: Dict[str, Any]) -> str:
        env_var_name = model_config.get("api_key_env", "")
        return os.getenv(env_var_name, "") if env_var_name else ""

    @classmethod
    def get_model_config_by_id(cls, model_id: str) -> Optional[Dict[str, Any]]:
        """enabled bakmadan, tüm modeller arasından varsayılanlarla birleştirilmiş config döndürür."""
        config = cls.load_config()
        defaults = {
            "temperature": config.get("default_temperature", 0.1),
            "max_tokens": config.get("default_max_tokens", 8192),
            "top_p": config.get("default_top_p", 0.9),
            "repetition_penalty": config.get("default_repetition_penalty", 1.0),
            "reasoning_effort": config.get("default_reasoning_effort", "high"),
            "prompt_file": config.get("default_prompt_file", "bdr_analyst_v1.md"),
        }
        for m in config.get("models", []):
            if m.get("id") == model_id:
                return {**defaults, **m}
        return None

    @classmethod
    def model_girdi_siniri(cls, model_config: Dict[str, Any]) -> int:
        """Bir modelin BDR metni için efektif karakter sınırı (analyzer ile aynı mantık):
        modelin kendi `max_input_chars`'ı → sağlayıcı limiti → genel varsayılan."""
        return int(
            model_config.get("max_input_chars")
            or cls.PROVIDER_INPUT_LIMITS.get(model_config.get("provider", ""), cls.DEFAULT_MAX_INPUT_CHARS)
        )

    @classmethod
    def model_bdr_degerlendirmesi(cls, model_config: Dict[str, Any], bdr_karakter: int) -> Dict[str, Any]:
        """Model seçim ekranı için token bazlı detaylı teknik metrikler ve BDR uyumluluk analizi.

        Dönüş: rozet, ozet, context_window_str, max_tokens_str, api_key_status, bdr_etiketi, uyarilar, secilebilir, bdr_token.
        """
        durum = str(model_config.get("durum") or "ok")
        sinir_krk = cls.model_girdi_siniri(model_config)
        etkin_sinir_krk = max(int(sinir_krk * cls.CHUNK_UTILIZATION), 1)
        parca = 1 if bdr_karakter <= sinir_krk else (bdr_karakter + etkin_sinir_krk - 1) // etkin_sinir_krk
        cikti_tavani = int(model_config.get("max_tokens") or 0)
        provider = model_config.get("provider", "")
        api_key_env = model_config.get("api_key_env", "")
        api_key = os.getenv(api_key_env, "") if api_key_env else ""

        # Token bazlı hesaplamalar (Türkçe BDR metinlerinde ortalama 1 Token ≈ 3.8 Karakter)
        bdr_token = round(bdr_karakter / 3.8)
        sinir_token = round(sinir_krk / 3.8)

        # Context Window & Output Stringler (Standart Yapay Zeka Terimleri)
        context_str = model_config.get("context_window") or f"~{sinir_token:,} Token"
        output_str = f"{cikti_tavani:,} Token" if cikti_tavani else "Unspecified"

        # API Key Durumu
        if provider == "mock":
            api_key_status = "✅ Mock Mode (No Key Required)"
            has_key = True
        elif api_key:
            api_key_status = f"✅ Key Active (`{api_key_env}`)"
            has_key = True
        else:
            api_key_status = f"❌ Missing Key (`.env: {api_key_env}`)"
            has_key = False

        uyarilar: List[str] = []
        if model_config.get("durum_notu"):
            uyarilar.append(str(model_config["durum_notu"]))

        cok_dusuk_cikti = 0 < cikti_tavani < 8000

        if parca > 1:
            uyarilar.append(
                f"Seçili BDR (~{bdr_token:,} Token), modelin Context Window sınırını (~{sinir_token:,} Token) "
                f"aşıyor → ~{parca} parçada Map-Reduce yöntemiyle işlenir."
            )
        if cok_dusuk_cikti:
            uyarilar.append(f"Düşük Max Output Tokens ({cikti_tavani:,} Token) — Analiz yanıtı kesilebilir.")
        if provider == "huggingface":
            uyarilar.append("HuggingFace Router: Sunucu yoğunluğuna göre işlem süresi değişkenlik gösterebilir.")
        if not has_key and provider != "mock":
            uyarilar.append(f"Çalıştırmak için .env dosyasında {api_key_env} tanımlanmalıdır.")

        if not has_key and provider != "mock":
            rozet = "⚠️"
            bdr_etiketi = "🔑 API Key Eksik"
        elif parca == 1 and not cok_dusuk_cikti:
            rozet = "🟢"
            bdr_etiketi = "⚡ Single Pass (İdeal & Hızlı)"
        elif parca <= 4:
            rozet = "🟡"
            bdr_etiketi = f"🧩 Map-Reduce (~{parca} Parça)"
        else:
            rozet = "🔴"
            bdr_etiketi = f"🐢 Yüksek Parçalama (~{parca} Parça - Yavaş)"

        ozet = f"Context Window: {context_str} · Max Output: {output_str} · {bdr_etiketi}"

        return {
            "rozet": rozet,
            "ozet": ozet,
            "context_window_str": context_str,
            "max_tokens_str": output_str,
            "api_key_status": api_key_status,
            "has_key": has_key,
            "bdr_etiketi": bdr_etiketi,
            "bdr_token": bdr_token,
            "parca": parca,
            "uyarilar": uyarilar,
            "secilebilir": durum != "kullanilamaz",
        }

    @classmethod
    def get_pipeline_config(cls) -> Dict[str, Any]:
        block = cls.load_config().get("pipeline", {})
        return {**PIPELINE_DEFAULTS, **block}

    @classmethod
    def get_pipeline_db_url(cls) -> str:
        return os.getenv("PIPELINE_DB_URL", "")

    @classmethod
    def ensure_directories(cls):
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


Config.ensure_directories()
Config.load_config()
