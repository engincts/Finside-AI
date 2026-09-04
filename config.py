import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

CONFIG_JSON_PATH = BASE_DIR / "config.json"

PIPELINE_DEFAULTS: Dict[str, Any] = {
    "map_models": [],
    "triage_model": "gpt-4o-mini",
    "reconciler_model": "claude-sonnet-4-5",
    "critic_model": "gemini-3.6-flash",
    "synthesis_model": "claude-sonnet-4-5",
    "segmenter_fallback_model": "gemini-3.6-flash",
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
        "huggingface": 90_000,
        "openai": 200_000,
        "anthropic": 200_000,
        "gemini": 200_000,
        "mock": 5_000_000,
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

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

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
