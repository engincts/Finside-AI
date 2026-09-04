"""Faz 4 — Grounding: risk alıntılarının ham metinde gerçekten geçtiğini doğrular.

LLM kullanmaz; `rapidfuzz` ile fuzzy alt-dize eşleşmesi. Halüsinasyon yakalamada
en yüksek getirili adımlardan biri.
"""

import re
from typing import List, Tuple

from rapidfuzz import fuzz

_ALINTI_KARAKTER_SINIRI = 400
_MIN_PARCA_KARAKTER = 12
_MAKS_PARCA = 6
# "...", ". . .", "…" ve köşeli/parantezli varyantları — modelin birbirinden uzak
# metin parçalarını tek "alıntı" gibi birleştirdiği ayraç.
_AYIRAC = re.compile(r"\s*[\[(]?\s*(?:\.\s*\.\s*\.+|…)\s*[\])]?\s*")
# Rakam-arası binlik/ondalık ayıracı: "155.737" / "155,737" -> "155737".
_SAYI_AYIRAC = re.compile(r"(?<=\d)[.,](?=\d)")
_BOSLUK = re.compile(r"\s+")


def _sadelestir_metin(metin: str) -> str:
    """Grounding karşılaştırması öncesi normalizasyon: sayı biçim farkı (nokta/virgül
    binlik ayracı) ve çok satırlı tablo hizalaması (fazla boşluk/tab/satır sonu)
    eşleşmeyi bozmasın diye hem alıntı hem kaynak metin bundan geçirilir."""
    return _BOSLUK.sub(" ", _SAYI_AYIRAC.sub("", metin)).strip()


def _alinti_parcalari(alinti: str) -> List[str]:
    """Alıntıyı "..." ayracına göre parçalara böler.

    Ayraç yoksa tek elemanlı liste döner (eski davranış). Ayraç varsa yalnızca
    anlamlı uzunluktaki parçalar tutulur; hepsi çok kısaysa veya aşırı çok parça
    varsa alıntı bütün olarak kontrol edilir (birleştirme deseni bu durumda zaten
    doğrulanamaz).
    """
    ham = _AYIRAC.split(alinti)
    if len(ham) == 1:
        return [alinti.strip()]
    temiz = [p.strip().strip("\"'“”‘’ ") for p in ham]
    anlamli = [p for p in temiz if len(p) >= _MIN_PARCA_KARAKTER]
    if not anlamli or len(anlamli) > _MAKS_PARCA:
        return [alinti.strip()]
    return anlamli


def _dogrula(alinti: str, kaynak_sade: str, esik: float) -> bool:
    parcalar = _alinti_parcalari(alinti)
    return bool(parcalar) and all(
        fuzz.partial_ratio(_sadelestir_metin(parca)[:_ALINTI_KARAKTER_SINIRI], kaynak_sade) >= esik
        for parca in parcalar
    )


def ground_riskler(
    riskler: List[dict],
    kaynak_metin: str,
    esik: float,
    kati_mod: bool,
) -> Tuple[List[dict], int]:
    """Her riske `dogrulanmadi` bayrağı ekler. Kati modda doğrulanmayanları eler.

    Dönüş: (işlenmiş riskler, doğrulanmayan sayısı).
    """
    kaynak_sade = _sadelestir_metin(kaynak_metin)
    sonuc: List[dict] = []
    dogrulanmayan = 0

    for risk in riskler:
        alinti = (risk.get("kaynak_metin_alintisi") or "").strip()
        dogrulandi = _dogrula(alinti, kaynak_sade, esik) if alinti else False

        if not dogrulandi:
            dogrulanmayan += 1
            if kati_mod:
                continue

        sonuc.append({**risk, "dogrulanmadi": not dogrulandi})

    return sonuc, dogrulanmayan
