"""Faz 4 — Grounding: risk alıntılarının ham metinde gerçekten geçtiğini doğrular.

LLM kullanmaz; `rapidfuzz` ile fuzzy alt-dize eşleşmesi. Halüsinasyon yakalamada
en yüksek getirili adımlardan biri.
"""

from typing import List, Tuple

from rapidfuzz import fuzz

_ALINTI_KARAKTER_SINIRI = 400


def ground_riskler(
    riskler: List[dict],
    kaynak_metin: str,
    esik: float,
    kati_mod: bool,
) -> Tuple[List[dict], int]:
    """Her riske `dogrulanmadi` bayrağı ekler. Kati modda doğrulanmayanları eler.

    Dönüş: (işlenmiş riskler, doğrulanmayan sayısı).
    """
    sonuc: List[dict] = []
    dogrulanmayan = 0

    for risk in riskler:
        alinti = (risk.get("kaynak_metin_alintisi") or "").strip()
        skor = fuzz.partial_ratio(alinti[:_ALINTI_KARAKTER_SINIRI], kaynak_metin) if alinti else 0.0
        dogrulandi = skor >= esik

        if not dogrulandi:
            dogrulanmayan += 1
            if kati_mod:
                continue

        sonuc.append({**risk, "dogrulanmadi": not dogrulandi})

    return sonuc, dogrulanmayan
