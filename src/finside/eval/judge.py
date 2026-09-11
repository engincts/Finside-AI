"""Katman 2 — LLM hakem değerlendirmesi (canlı API çağrısı yapar).

Frontier bir veya birkaç model, ham BDR + üretilen raporu katı bir rubrik ile
puanlar ve kaçırılan / hatalı riskleri listeler. Birden çok hakem verilirse
puanlar ortalanır, kaçırılan/hatalı listeleri birleştirilir.
"""

import json
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import Config
from finside.loaders import PromptLoader
from finside.pipeline.llm_call import ham_cagri

VARSAYILAN_HAKEMLER = ["gemini-3.6-flash"]
_PUAN_ALANLARI = ("recall_puani", "precision_puani", "derinlik_puani", "karar_isabeti")
_RAPOR_ALANLARI = (
    "risk_kategorisi", "baslik", "dipnot_referansi",
    "tutar_bilgisi", "etki_degerlendirmesi", "risk_derecesi",
)


def _json_ayikla(text: str) -> str:
    parca = (text or "").strip()
    if "```json" in parca:
        parca = parca.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in parca:
        parca = parca.split("```", 2)[1]
    bas, son = parca.find("{"), parca.rfind("}")
    return parca[bas:son + 1] if bas != -1 and son != -1 else parca


def _bdr_hazirla(bdr_metni: str, model_id: str) -> Tuple[str, bool]:
    cfg = Config.get_model_config_by_id(model_id) or {}
    sinir = Config.model_girdi_siniri(cfg)
    if len(bdr_metni) <= sinir:
        return bdr_metni, False
    return bdr_metni[:sinir], True


def _tek_hakem(
    model_id: str,
    bdr_metni: str,
    rapor_json: str,
    sistem: str,
    sablon: str,
    yaz: Optional[Callable[[str], None]],
) -> Dict[str, Any]:
    metin, kirpildi = _bdr_hazirla(bdr_metni, model_id)
    prompt = sablon.format(bdr_metni=metin, rapor_json=rapor_json)
    sonuc = ham_cagri(model_id, prompt, asama="eval-hakem", system_prompt=sistem, json_mode=True)
    if yaz:
        ek = " · BDR kırpıldı" if kirpildi else ""
        yaz(f"  hakem {model_id} · {sonuc.trace['sure_sn']:.1f}s{ek}")
    try:
        veri = json.loads(_json_ayikla(sonuc.text))
    except Exception as exc:  # noqa: BLE001 — hakem çıktısı bozuksa diğerleri sürsün
        return {"model_id": model_id, "hata": f"JSON ayrıştırılamadı: {exc}", "ham": (sonuc.text or "")[:500]}
    veri["model_id"] = model_id
    veri["bdr_kirpildi"] = kirpildi
    return veri


def _tekille(items: List[Any]) -> List[str]:
    gorulen: set = set()
    sonuc: List[str] = []
    for item in items:
        metin = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        if metin.lower() not in gorulen:
            gorulen.add(metin.lower())
            sonuc.append(metin)
    return sonuc


def hakem_degerlendir(
    bdr_metni: str,
    rapor: dict,
    hakem_modelleri: Optional[List[str]] = None,
    yaz: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    hakemler = hakem_modelleri or VARSAYILAN_HAKEMLER
    sistem, sablon = PromptLoader.load_prompt_md("judge_v1.md")

    ozet_rapor = {
        "firma_adi": rapor.get("firma_adi"),
        "denetci_gorusu": rapor.get("denetci_gorusu"),
        "karar_egilimi": rapor.get("karar_egilimi"),
        "analist_gerekce_metni": rapor.get("analist_gerekce_metni"),
        "tespit_edilen_riskler": [
            {alan: r.get(alan) for alan in _RAPOR_ALANLARI}
            for r in (rapor.get("tespit_edilen_riskler") or [])
        ],
    }
    rapor_json = json.dumps(ozet_rapor, ensure_ascii=False, indent=2)

    sonuclar = [
        _tek_hakem(model_id, bdr_metni, rapor_json, sistem, sablon, yaz)
        for model_id in hakemler
    ]
    gecerli = [s for s in sonuclar if "hata" not in s]

    ortalama: Dict[str, Optional[float]] = {}
    for alan in _PUAN_ALANLARI:
        puanlar = [float(s[alan]) for s in gecerli if isinstance(s.get(alan), (int, float))]
        ortalama[alan] = round(sum(puanlar) / len(puanlar), 2) if puanlar else None

    kacirilan: List[Any] = []
    hatali: List[Any] = []
    for s in gecerli:
        kacirilan += s.get("kacirilan_riskler") or []
        hatali += s.get("hatali_riskler") or []

    return {
        "hakemler": sonuclar,
        "ortalama_puan": ortalama,
        "kacirilan_riskler": _tekille(kacirilan),
        "hatali_riskler": _tekille(hatali),
    }
