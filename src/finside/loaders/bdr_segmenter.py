"""Faz 1 — BDR metnini yapı-farkında segmentlere ayırır.

Birincil yol: `chunking._is_heading` regex tespiti + offset hesaplama.
Güven skoru düşükse LLM segmenter fallback (`prompts/segmenter_v1.md`).
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Tuple

from rapidfuzz import fuzz

from finside.chunking import _is_heading
from finside.loaders.prompt_loader import PromptLoader
from finside.pipeline.state import Segment, TraceKaydi

BEKLENEN_MIN_SEGMENT = 12
BEKLENEN_MAX_SEGMENT = 90
MIN_SEGMENT_KARAKTER = 300
CAPA_IBARELERI = (
    "BAĞIMSIZ DENETÇİ", "KİLİT DENETİM KONULARI", "GÖRÜŞÜN DAYANAĞI",
    "FİNANSAL TABLOLARA İLİŞKİN", "DİPNOT",
)
_LLM_GIRDI_KARAKTER_SINIRI = 200_000


@dataclass
class SegmentSonucu:
    segmentler: List[Segment]
    guven: float
    yontem: str  # "regex" | "llm_fallback"
    izler: List[TraceKaydi] = field(default_factory=list)


def _segment_olustur(sira_no: int, metin: str, baslangic: int) -> Segment:
    ilk_satir = ""
    for satir in metin.splitlines():
        if satir.strip():
            ilk_satir = satir.strip()
            break
    return Segment(
        sira_no=sira_no,
        baslik=(ilk_satir[:160] or f"Bölüm {sira_no}"),
        ham_metin=metin,
        karakter_sayisi=len(metin),
        baslangic_offset=baslangic,
        bitis_offset=baslangic + len(metin),
    )


def regex_segmentle(ham_metin: str) -> List[Segment]:
    segmentler: List[Segment] = []
    buffer: List[str] = []
    buffer_bas = 0
    offset = 0
    for satir in ham_metin.splitlines(keepends=True):
        if buffer and _is_heading(satir):
            metin = "".join(buffer)
            if metin.strip():
                segmentler.append(_segment_olustur(len(segmentler) + 1, metin, buffer_bas))
            buffer, buffer_bas = [satir], offset
        else:
            if not buffer:
                buffer_bas = offset
            buffer.append(satir)
        offset += len(satir)
    if buffer and "".join(buffer).strip():
        segmentler.append(_segment_olustur(len(segmentler) + 1, "".join(buffer), buffer_bas))
    return _kucuk_segmentleri_birlestir(segmentler)


def _kucuk_segmentleri_birlestir(segmentler: List[Segment]) -> List[Segment]:
    """MIN_SEGMENT_KARAKTER altındaki parçaları (tablo kırıntıları) bir öncekine ekler."""
    if not segmentler:
        return segmentler
    birlesik: List[Segment] = [dict(segmentler[0])]  # type: ignore[list-item]
    for seg in segmentler[1:]:
        onceki = birlesik[-1]
        if seg["karakter_sayisi"] < MIN_SEGMENT_KARAKTER or onceki["karakter_sayisi"] < MIN_SEGMENT_KARAKTER:
            onceki["ham_metin"] += seg["ham_metin"]
            onceki["karakter_sayisi"] = len(onceki["ham_metin"])
            onceki["bitis_offset"] = seg["bitis_offset"]
        else:
            birlesik.append(dict(seg))  # type: ignore[arg-type]
    for i, seg in enumerate(birlesik, 1):
        seg["sira_no"] = i
    return birlesik  # type: ignore[return-value]


def segmentation_confidence(segmentler: List[Segment], ham_metin: str) -> float:
    if not segmentler:
        return 0.0
    n = len(segmentler)
    puanlar: List[float] = []

    if BEKLENEN_MIN_SEGMENT <= n <= BEKLENEN_MAX_SEGMENT:
        puanlar.append(1.0)
    elif 4 <= n < BEKLENEN_MIN_SEGMENT:
        puanlar.append(0.4)
    else:
        puanlar.append(0.15)

    numarali = sum(
        1 for s in segmentler
        if re.match(r"^\s*(?:NOT|D[İI]PNOT)?\s*\d", s["baslik"], re.IGNORECASE)
    )
    puanlar.append(min(numarali / max(n * 0.3, 1.0), 1.0))

    ort = sum(s["karakter_sayisi"] for s in segmentler) / n
    puanlar.append(1.0 if 200 <= ort <= 40_000 else 0.5)

    en_buyuk = max(s["karakter_sayisi"] for s in segmentler)
    puanlar.append(1.0 if en_buyuk <= 60_000 else (0.4 if en_buyuk <= 120_000 else 0.1))

    ust = ham_metin.upper()
    puanlar.append(1.0 if any(ibare in ust for ibare in CAPA_IBARELERI) else 0.3)

    skor = round(sum(puanlar) / len(puanlar), 3)
    if en_buyuk > 150_000:  # açıkça kaçmış sınır → LLM fallback'i zorla
        skor = min(skor, 0.5)
    return skor


def _ipucu_konumu(ham_metin: str, ipucu: str) -> int:
    ipucu = ipucu.strip()
    if not ipucu:
        return -1
    dogrudan = ham_metin.find(ipucu[:60])
    if dogrudan != -1:
        return dogrudan
    pencere = max(len(ipucu), 40)
    en_iyi_skor, en_iyi_konum = 0.0, -1
    for i in range(0, len(ham_metin) - pencere, 200):
        skor = fuzz.ratio(ipucu[:pencere], ham_metin[i:i + pencere])
        if skor > en_iyi_skor:
            en_iyi_skor, en_iyi_konum = skor, i
    return en_iyi_konum if en_iyi_skor >= 70 else -1


def _llm_ciktisini_uygula(llm_text: str, ham_metin: str) -> List[Segment]:
    try:
        veri = json.loads(llm_text[llm_text.find("["): llm_text.rfind("]") + 1])
    except (ValueError, json.JSONDecodeError):
        return []
    if not isinstance(veri, list):
        return []

    konumlar: List[Tuple[int, str]] = []
    for oge in veri:
        if not isinstance(oge, dict):
            continue
        ipucu = str(oge.get("baslangic_ipucu") or oge.get("baslik") or "")
        konum = _ipucu_konumu(ham_metin, ipucu)
        if konum != -1:
            konumlar.append((konum, str(oge.get("baslik") or ipucu)[:160]))

    konumlar.sort()
    if not konumlar:
        return []

    segmentler: List[Segment] = []
    for i, (bas, baslik) in enumerate(konumlar):
        bit = konumlar[i + 1][0] if i + 1 < len(konumlar) else len(ham_metin)
        metin = ham_metin[bas:bit]
        seg = _segment_olustur(len(segmentler) + 1, metin, bas)
        seg["baslik"] = baslik or seg["baslik"]
        segmentler.append(seg)
    return segmentler


def segment_bdr(
    ham_metin: str,
    *,
    guven_esigi: float,
    fallback_model: str,
    asama: str = "faz1-segmentasyon",
) -> SegmentSonucu:
    segmentler = regex_segmentle(ham_metin)
    guven = segmentation_confidence(segmentler, ham_metin)
    if guven >= guven_esigi or not fallback_model:
        return SegmentSonucu(segmentler, guven, "regex")

    from finside.pipeline.llm_call import ham_cagri

    sistem, sablon = PromptLoader.load_prompt_md("segmenter_v1.md")
    sonuc = ham_cagri(
        fallback_model,
        sablon.format(bdr_text=ham_metin[:_LLM_GIRDI_KARAKTER_SINIRI]),
        asama=asama,
        system_prompt=sistem,
        json_mode=True,
    )
    llm_segmentler = _llm_ciktisini_uygula(sonuc.text, ham_metin) if sonuc.text else []
    if llm_segmentler:
        return SegmentSonucu(llm_segmentler, guven, "llm_fallback", izler=[sonuc.trace])
    return SegmentSonucu(segmentler, guven, "regex", izler=[sonuc.trace])
