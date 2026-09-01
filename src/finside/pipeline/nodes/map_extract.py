from pathlib import Path
from typing import List

from langgraph.types import Send

from config import Config
from finside.pipeline.llm_call import rapor_cagrisi
from finside.pipeline.state import MapCiktisi, PipelineState, TraceKaydi
from finside.writers import ReportWriter

MAP_INSTRUCTION = (
    "[BDR PARÇA {idx}/{toplam}] Aşağıdaki metin, daha büyük bir Bağımsız Denetim "
    "Raporunun yalnızca bir bölümüdür. SADECE bu bölümde açıkça yer alan kalitatif "
    "kredi risklerini çıkar. Bu bölümde risk yoksa 'tespit_edilen_riskler' listesini "
    "boş bırak. Firma, dönem ve denetçi bilgisini metnin künyesinden doldur.\n\n{metin}"
)


def map_modelleri(state: PipelineState) -> List[str]:
    return state.get("secili_map_modelleri") or list(Config.get_pipeline_config()["map_models"])


def map_dagit(state: PipelineState) -> List[Send]:
    """gruplari_olustur sonrası fan-out: her (grup, model) çifti bir map_worker."""
    gruplar = state["segment_gruplari"]
    modeller = map_modelleri(state)
    toplam = len(gruplar)
    return [
        Send("map_worker", {"grup": g, "model_id": m, "toplam_grup": toplam})
        for g in gruplar
        for m in modeller
    ]


def map_worker(payload: dict) -> dict:
    grup = payload["grup"]
    model_id = payload["model_id"]
    user_prompt = MAP_INSTRUCTION.format(
        idx=grup["grup_id"] + 1,
        toplam=payload["toplam_grup"],
        metin=grup["birlesik_metin"],
    )

    try:
        sonuc = rapor_cagrisi(model_id, user_prompt, asama="faz3-map")
    except Exception as exc:  # noqa: BLE001 — bir modelin çökmesi diğerlerini durdurmaz
        hata = f"{type(exc).__name__}: {exc}"
        cikti = MapCiktisi(grup_id=grup["grup_id"], model_id=model_id, riskler=[],
                           hata_durumu=hata, sure_sn=0.0)
        iz = TraceKaydi(asama="faz3-map", model_id=model_id, provider=None,
                        girdi_karakter=len(user_prompt), cikti_karakter=0,
                        sure_sn=0.0, basari=False, hata=hata)
        return {"map_ciktilari": [cikti], "trace": [iz]}

    rapor = sonuc.report
    riskler: List[dict] = []
    if not rapor.is_mock_fallback:
        for risk in rapor.tespit_edilen_riskler:
            veri = risk.model_dump(mode="json")  # enum -> string: checkpoint-güvenli
            veri["kaynak_modeller"] = [model_id]
            riskler.append(veri)

    cikti = MapCiktisi(
        grup_id=grup["grup_id"],
        model_id=model_id,
        riskler=riskler,
        hata_durumu=rapor.fallback_reason if rapor.is_mock_fallback else None,
        sure_sn=sonuc.trace["sure_sn"],
    )
    return {"map_ciktilari": [cikti], "trace": [sonuc.trace]}


def map_topla(state: PipelineState) -> dict:
    ciktilar = state["map_ciktilari"]
    session_dir = Path(state["session_dir"])
    ReportWriter.save_json(session_dir, "map_raw.json", [
        {
            "grup_id": c["grup_id"],
            "model_id": c["model_id"],
            "risk_sayisi": len(c["riskler"]),
            "hata_durumu": c["hata_durumu"],
            "sure_sn": c["sure_sn"],
        }
        for c in ciktilar
    ])
    ReportWriter.save_trace(session_dir, [dict(t) for t in state.get("trace", [])])
    return {}
