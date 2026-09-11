"""Katman 3 — Altın (gold) set ile deterministik skorlama.

`gold/<bdr_stem>.json` insan-doğrulamalı beklenen riskleri tutar; bir rapor bu
listeye karşı ağırlıklı recall, karar ve denetçi görüşü isabeti açısından puanlanır.
LLM muhakemesi yok — eşleşme tutar/başlık/dipnot ipucu üzerinden yapılır.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz

from config import Config
from finside.dedupe import _onemli_sayilar

GOLD_DIR = Config.BASE_DIR / "gold"

_BASLIK_ESIGI = 62
_ONEM_AGIRLIK = {"kritik": 2.0, "yuksek": 1.5, "orta": 1.0, "dusuk": 0.5}


def yukle(bdr_stem: str) -> Optional[dict]:
    yol = GOLD_DIR / f"{bdr_stem}.json"
    if not yol.exists():
        return None
    return json.loads(yol.read_text(encoding="utf-8"))


def _agirlik(onem: Optional[str]) -> float:
    return _ONEM_AGIRLIK.get((onem or "orta").strip().lower(), 1.0)


def _eslesir(beklenen: dict, rapor_riski: dict) -> bool:
    beklenen_baslik = (beklenen.get("kisa_baslik") or "").strip()
    rapor_baslik = (rapor_riski.get("baslik") or "").strip()
    if beklenen_baslik and rapor_baslik:
        if fuzz.token_set_ratio(beklenen_baslik, rapor_baslik) >= _BASLIK_ESIGI:
            return True

    ipucu = (beklenen.get("kaynak_ipucu") or "").strip().lower()
    if ipucu:
        ref = (rapor_riski.get("dipnot_referansi") or "").lower()
        detay = (rapor_riski.get("detay") or "").lower()
        if ipucu in ref or ipucu in detay:
            return True

    beklenen_sayi = _onemli_sayilar(beklenen.get("anahtar_tutar") or "")
    if beklenen_sayi:
        rapor_sayi = _onemli_sayilar(
            rapor_riski.get("tutar_bilgisi") or "",
            rapor_riski.get("baslik") or "",
            rapor_riski.get("detay") or "",
        )
        if beklenen_sayi & rapor_sayi:
            return True
    return False


def skorla(rapor: dict, gold: dict) -> Dict[str, Any]:
    rapor_riskleri = rapor.get("tespit_edilen_riskler") or []
    beklenenler = gold.get("beklenen_riskler") or []

    bulunan_agirlik = 0.0
    toplam_agirlik = 0.0
    kacirilanlar: List[str] = []
    eslesen_rapor_idx: set = set()

    for beklenen in beklenenler:
        agirlik = _agirlik(beklenen.get("onem"))
        toplam_agirlik += agirlik
        eslesme = next(
            (i for i, r in enumerate(rapor_riskleri) if _eslesir(beklenen, r)), None
        )
        if eslesme is not None:
            bulunan_agirlik += agirlik
            eslesen_rapor_idx.add(eslesme)
        else:
            kacirilanlar.append(beklenen.get("kisa_baslik") or "?")

    fazla_kalemler = [
        r.get("baslik") or "?"
        for i, r in enumerate(rapor_riskleri)
        if i not in eslesen_rapor_idx
    ]

    karar_beklenen = gold.get("beklenen_karar_araligi") or []
    gorus_beklenen = gold.get("beklenen_denetci_gorusu")

    return {
        "recall": round(bulunan_agirlik / toplam_agirlik, 3) if toplam_agirlik else 0.0,
        "eslesen_rapor_kalemi": len(eslesen_rapor_idx),
        "precision_sinyali": (
            round(len(eslesen_rapor_idx) / len(rapor_riskleri), 3) if rapor_riskleri else 0.0
        ),
        "kacirilan_riskler": kacirilanlar,
        "fazla_kalemler": fazla_kalemler[:15],
        "karar_isabeti": (rapor.get("karar_egilimi") in karar_beklenen) if karar_beklenen else None,
        "gorus_isabeti": (rapor.get("denetci_gorusu") == gorus_beklenen) if gorus_beklenen else None,
        "beklenen_risk_sayisi": len(beklenenler),
        "rapor_risk_sayisi": len(rapor_riskleri),
    }
