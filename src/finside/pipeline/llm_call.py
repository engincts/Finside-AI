import time
from dataclasses import dataclass
from typing import Optional

from config import Config
from finside.loaders import PromptLoader
from finside.providers import ProviderFactory
from finside.pipeline.state import TraceKaydi
from prompts.schemas import BDRRiskAnalysisReport


@dataclass
class RaporCagriSonucu:
    report: BDRRiskAnalysisReport
    trace: TraceKaydi


@dataclass
class HamCagriSonucu:
    text: str
    trace: TraceKaydi


def _trace(
    asama: str,
    model_id: Optional[str],
    provider: Optional[str],
    girdi: str,
    cikti: str,
    sure_sn: float,
    basari: bool,
    hata: Optional[str],
) -> TraceKaydi:
    return TraceKaydi(
        asama=asama,
        model_id=model_id,
        provider=provider,
        girdi_karakter=len(girdi),
        cikti_karakter=len(cikti),
        sure_sn=sure_sn,
        basari=basari,
        hata=hata,
    )


def rapor_cagrisi(
    model_id: str,
    user_prompt: str,
    *,
    asama: str,
    system_prompt: Optional[str] = None,
) -> RaporCagriSonucu:
    """Tek bir modele BDRRiskAnalysisReport üreten çağrı yapar; trace kaydını da döndürür.

    Provider katmanı hata durumunda exception atmaz, mock fallback raporu döndürür;
    trace `basari`/`hata` alanları `report.is_mock_fallback`/`fallback_reason`'dan gelir.
    """
    model_cfg = Config.get_model_config_by_id(model_id)
    if model_cfg is None:
        raise ValueError(f"Bilinmeyen model id: {model_id}")

    provider_name = model_cfg.get("provider", "mock")
    if system_prompt is None:
        system_prompt, _ = PromptLoader.load_prompt_md(model_cfg["prompt_file"])

    provider = ProviderFactory.create_provider(
        provider_name=provider_name,
        model_config=model_cfg,
        system_prompt=system_prompt,
        api_key=Config.get_api_key_for_model(model_cfg),
    )

    start = time.perf_counter()
    report = provider.analyze(user_prompt)
    elapsed = round(time.perf_counter() - start, 3)

    trace = _trace(
        asama=asama,
        model_id=model_id,
        provider=provider_name,
        girdi=user_prompt,
        cikti=report.model_dump_json(),
        sure_sn=elapsed,
        basari=not report.is_mock_fallback,
        hata=report.fallback_reason,
    )
    return RaporCagriSonucu(report=report, trace=trace)


def ham_cagri(
    model_id: str,
    user_prompt: str,
    *,
    asama: str,
    system_prompt: str,
    json_mode: bool = False,
) -> HamCagriSonucu:
    """Şemasız ham metin üreten çağrı (triyaj, segmenter). Hata → trace.basari=False, text=''."""
    model_cfg = Config.get_model_config_by_id(model_id)
    if model_cfg is None:
        raise ValueError(f"Bilinmeyen model id: {model_id}")

    provider_name = model_cfg.get("provider", "mock")
    provider = ProviderFactory.create_provider(
        provider_name=provider_name,
        model_config=model_cfg,
        system_prompt=system_prompt,
        api_key=Config.get_api_key_for_model(model_cfg),
    )

    start = time.perf_counter()
    text, basari, hata = "", True, None
    try:
        text = provider.raw_generate(user_prompt, json_mode=json_mode)
        if not text.strip():
            basari, hata = False, "boş yanıt"
    except Exception as exc:  # noqa: BLE001 — trace'e yazılıp devam edilir
        basari, hata, text = False, f"{type(exc).__name__}: {exc}", ""
    elapsed = round(time.perf_counter() - start, 3)

    trace = _trace(asama, model_id, provider_name, user_prompt, text, elapsed, basari, hata)
    return HamCagriSonucu(text=text, trace=trace)
