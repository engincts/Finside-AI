import time
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

from config import Config
from finside.loaders import PromptLoader
from finside.providers import ProviderFactory
from finside.pipeline.state import TraceKaydi
from finside.models import BDRRiskAnalysisReport, KomiteKararEgilimi

_T = TypeVar("_T")
# Geçici HF/API kesintileri (503, timeout, "yanıt alınamadı") için artan beklemeli retry.
_RETRY_BEKLEME_SN = (0.0, 4.0, 10.0)


def _deneme_ile(fn: Callable[[], _T]) -> _T:
    son_hata: Optional[Exception] = None
    for bekleme in _RETRY_BEKLEME_SN:
        if bekleme:
            time.sleep(bekleme)
        try:
            return fn()
        except Exception as err:  # noqa: BLE001 — son deneme de düşerse yeniden fırlatılır
            son_hata = err
    raise son_hata  # type: ignore[misc]


def _hata_raporu(reason: str) -> BDRRiskAnalysisReport:
    """LLM çağrısı başarısızsa: uydurma firma/risk verisi DEĞİL, boş + hatayı taşıyan rapor.
    Downstream `is_mock_fallback` bayrağıyla bu adımı güvenilmez sayar."""
    return BDRRiskAnalysisReport(
        is_mock_fallback=True,
        fallback_reason=reason,
        firma_adi=None,
        rapor_donemi=None,
        denetci_gorusu=None,
        karar_egilimi=KomiteKararEgilimi.BELIRSIZ,
        genel_kredi_risk_ozeti=f"LLM çağrısı başarısız: {reason}",
        analist_gerekce_metni=f"LLM çağrısı başarısız: {reason}",
    )


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

    if system_prompt is None:
        system_prompt, _ = PromptLoader.load_prompt_md(model_cfg["prompt_file"])

    def _uret(cfg: dict) -> BDRRiskAnalysisReport:
        provider = ProviderFactory.create_provider(
            provider_name=cfg.get("provider", "mock"),
            model_config=cfg,
            system_prompt=system_prompt,
            api_key=Config.get_api_key_for_model(cfg),
        )
        return _deneme_ile(lambda: provider.analyze(user_prompt))

    provider_name = model_cfg.get("provider", "mock")
    kullanilan_id = model_id
    start = time.perf_counter()
    try:
        report = _uret(model_cfg)
    except Exception as err:
        # Retry'lar tükendi — farklı sağlayıcıdaki yedek modele geç (config.pipeline.fallback_model).
        yedek_id = Config.get_pipeline_config().get("fallback_model")
        yedek_cfg = Config.get_model_config_by_id(yedek_id) if yedek_id and yedek_id != model_id else None
        if yedek_cfg:
            try:
                report = _uret(yedek_cfg)
                kullanilan_id = f"{yedek_id} (yedek; {model_id} başarısız)"
                provider_name = yedek_cfg.get("provider", "mock")
            except Exception as yedek_err:
                report = _hata_raporu(f"{err} | yedek {yedek_id}: {yedek_err}")
        else:
            report = _hata_raporu(str(err))
    elapsed = round(time.perf_counter() - start, 3)

    trace = _trace(
        asama=asama,
        model_id=kullanilan_id,
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
        text = _deneme_ile(lambda: provider.raw_generate(user_prompt, json_mode=json_mode))
        if not text.strip():
            basari, hata = False, "boş yanıt"
    except Exception as exc:  # noqa: BLE001 — trace'e yazılıp devam edilir
        basari, hata, text = False, f"{type(exc).__name__}: {exc}", ""
    elapsed = round(time.perf_counter() - start, 3)

    trace = _trace(asama, model_id, provider_name, user_prompt, text, elapsed, basari, hata)
    return HamCagriSonucu(text=text, trace=trace)
