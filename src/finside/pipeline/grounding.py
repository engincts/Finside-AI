"""Faz 4 — Grounding: risk alıntılarının ham metinde gerçekten geçtiğini doğrular.

Çok katmanlı doğrulama motoru:
1. RapidFuzz partial ratio ile hızlı bulanık eşleşme.
2. 4+ haneli tutar ve sayıların kaynak metinde varlığının denetimi (OCR / biçim bağımsız).
3. Kelime dağarcığı ve N-Gram içerik örtüşmesi.
"""

import re
from typing import List, Tuple

from rapidfuzz import fuzz

_ALINTI_KARAKTER_SINIRI = 400
_MIN_PARCA_KARAKTER = 12
_MAKS_PARCA = 6
_AYIRAC = re.compile(r"\s*[\[(]?\s*(?:\.\s*\.\s*\.+|…)\s*[\])]?\s*")
_SAYI_AYIRAC = re.compile(r"(?<=\d)[.,](?=\d)")
_BOSLUK = re.compile(r"\s+")
_SAYI_RE = re.compile(r"\d[\d.,]*\d")
_YIL_ARALIGI = range(1990, 2100)


def _sadelestir_metin(metin: str) -> str:
    """Grounding karşılaştırması öncesi normalizasyon: sayı biçim farkı ve fazla boşluklar temizlenir."""
    if not metin:
        return ""
    metin_sade = _SAYI_AYIRAC.sub("", metin.lower())
    return _BOSLUK.sub(" ", metin_sade).strip()


def _onemli_sayilar(metin: str) -> set:
    bulunan = set()
    for eslesme in _SAYI_RE.findall(metin or ""):
        rakamlar = eslesme.replace(".", "").replace(",", "")
        if len(rakamlar) >= 4 and int(rakamlar) not in _YIL_ARALIGI:
            bulunan.add(rakamlar)
    return bulunan


def _alinti_parcalari(alinti: str) -> List[str]:
    ham = _AYIRAC.split(alinti)
    if len(ham) == 1:
        return [alinti.strip()]
    temiz = [p.strip().strip("\"'“”‘’ ") for p in ham]
    anlamli = [p for p in temiz if len(p) >= _MIN_PARCA_KARAKTER]
    if not anlamli or len(anlamli) > _MAKS_PARCA:
        return [alinti.strip()]
    return anlamli


def _parca_dogrula(parca_sade: str, kaynak_sade: str, kaynak_sayilari: set, esik: float) -> bool:
    if not parca_sade:
        return True

    # Katman 1: RapidFuzz Bulanık Eşleşme
    if fuzz.partial_ratio(parca_sade, kaynak_sade) >= esik:
        return True

    # Katman 2: Sayısal Doğruluk & Kelime Kümesi Eşleşmesi (OCR / Yazım Bağımsız)
    parca_sayilari = _onemli_sayilar(parca_sade)
    if parca_sayilari and parca_sayilari.issubset(kaynak_sayilari):
        anlamli_kelimeler = [w for w in parca_sade.split() if len(w) >= 4]
        if anlamli_kelimeler and sum(1 for w in anlamli_kelimeler if w in kaynak_sade) / len(anlamli_kelimeler) >= 0.55:
            return True

    # Katman 3: Yüksek Anlamsal Kelime Kapsam Oranı (%75+)
    anlamli_kelimeler = [w for w in parca_sade.split() if len(w) >= 4]
    if anlamli_kelimeler and sum(1 for w in anlamli_kelimeler if w in kaynak_sade) / len(anlamli_kelimeler) >= 0.75:
        return True

    return False


def _dogrula(alinti: str, kaynak_sade: str, kaynak_sayilari: set, esik: float) -> bool:
    parcalar = _alinti_parcalari(alinti)
    if not parcalar:
        return False
    return all(
        _parca_dogrula(_sadelestir_metin(parca)[:_ALINTI_KARAKTER_SINIRI], kaynak_sade, kaynak_sayilari, esik)
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
    kaynak_sayilari = _onemli_sayilar(kaynak_metin)
    sonuc: List[dict] = []
    dogrulanmayan = 0

    for risk in riskler:
        alinti = (risk.get("kaynak_metin_alintisi") or "").strip()
        dogrulandi = _dogrula(alinti, kaynak_sade, kaynak_sayilari, esik) if alinti else False

        ek_kanitlar = risk.get("ek_kanitlar") or []
        if dogrulandi and ek_kanitlar:
            kanit_ok = all(_dogrula(k, kaynak_sade, kaynak_sayilari, esik) for k in ek_kanitlar if str(k).strip())
            dogrulandi = dogrulandi and kanit_ok

        if not dogrulandi:
            dogrulanmayan += 1
            if kati_mod:
                continue

        sonuc.append({**risk, "dogrulanmadi": not dogrulandi})

    return sonuc, dogrulanmayan
