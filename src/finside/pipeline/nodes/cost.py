"""Faz 10 — Maliyet/süre şeffaflığı. `state.trace`'ten toplar; amaç görünürlük."""

from collections import Counter
from pathlib import Path

from config import Config
from finside.pipeline.state import PipelineState
from finside.report_md import report_to_markdown
from finside.writers import ReportWriter
from prompts.schemas import BDRRiskAnalysisReport

_KARAKTER_PER_TOKEN = 4


def _model_fiyati(model_id: str):
    cfg = Config.get_model_config_by_id(model_id) or {}
    return float(cfg.get("usd_1k_in", 0.0)), float(cfg.get("usd_1k_out", 0.0))


def maliyet_ozetle(state: PipelineState) -> dict:
    trace = list(state.get("trace", []))
    toplam_girdi = sum(t["girdi_karakter"] for t in trace)
    toplam_cikti = sum(t["cikti_karakter"] for t in trace)

    usd = 0.0
    for kayit in trace:
        giris_fiyat, cikis_fiyat = _model_fiyati(kayit.get("model_id") or "")
        usd += (kayit["girdi_karakter"] / _KARAKTER_PER_TOKEN / 1000) * giris_fiyat
        usd += (kayit["cikti_karakter"] / _KARAKTER_PER_TOKEN / 1000) * cikis_fiyat

    izi = {
        "toplam_llm_cagrisi": len(trace),
        "basarisiz_cagri": sum(1 for t in trace if not t["basari"]),
        "asama_kirilimi": dict(Counter(t["asama"] for t in trace)),
        "tahmini_girdi_token": toplam_girdi // _KARAKTER_PER_TOKEN,
        "tahmini_cikti_token": toplam_cikti // _KARAKTER_PER_TOKEN,
        "toplam_sure_sn": round(sum(t["sure_sn"] for t in trace), 2),
        "tahmini_usd": round(usd, 4),
    }

    session_dir = Path(state["session_dir"])
    nihai = dict(state.get("nihai_rapor", {}))
    nihai["pipeline_izi"] = izi
    ReportWriter.save_json(session_dir, "nihai_rapor.json", nihai)
    ReportWriter.save_json(session_dir, "pipeline_izi.json", izi)

    rapor = BDRRiskAnalysisReport.model_validate(nihai)
    ust = [
        f"**Kaynak:** Multi-Agent Pipeline · `{rapor.kullanilan_model}`",
        f"**Firma Adı:** {rapor.firma_adi}",
        f"**Rapor Dönemi:** {rapor.rapor_donemi}",
        f"**Bağımsız Denetim Firması:** {rapor.denetim_firmasi or 'Belirtilmemiş'}",
        f"**Denetçi Görüşü:** `{rapor.denetci_gorusu.value if rapor.denetci_gorusu else 'Belirtilmemiş'}`",
        f"**Genel Karar Eğilimi:** `{rapor.karar_egilimi.value}`",
    ]
    (session_dir / "nihai_rapor.md").write_text(
        report_to_markdown(rapor, ust_satirlar=ust, pipeline_izi=izi), encoding="utf-8"
    )

    return {"nihai_rapor": nihai, "maliyet_ozeti": izi}
