import math
import re
from typing import List, Optional

from rapidfuzz import fuzz

from config import Config
from finside.models import BDRRiskItem


def _norm(text: str) -> str:
    return text.strip().lower()


_SAYI_RE = re.compile(r"\d[\d.,]*\d")
_YIL_ARALIGI = range(1990, 2100)


def _onemli_sayilar(*metinler: str) -> set:
    """Metindeki 4+ haneli tutar benzeri sayılar (yıl olmayan). Binlik/ondalık
    ayıraçları temizlenir: '116.737' ve '116737' aynı sayılır."""
    bulunan: set = set()
    for metin in metinler:
        for eslesme in _SAYI_RE.findall(metin or ""):
            rakamlar = eslesme.replace(".", "").replace(",", "")
            if len(rakamlar) >= 4 and int(rakamlar) not in _YIL_ARALIGI:
                bulunan.add(rakamlar)
    return bulunan


def _kalem_sayilari(risk: dict) -> set:
    return _onemli_sayilar(
        risk.get("tutar_bilgisi") or "", risk.get("detay") or "", risk.get("baslik") or ""
    )


def rollup_ele(riskler: List[dict]) -> List[dict]:
    """"Roll-up/özet kalemi"ni eler: bir kalemin HER somut sayısı, aynı kategorideki
    başka ≥2 kalemde de geçiyorsa (yani kalem yeni/kendine özgü hiçbir tutar
    getirmiyor, var olan ≥2 kalemi bir araya topluyor) → çıkar.

    Deterministik (regex sayı eşleştirme, LLM yok). Prompt-seviyesi yasak bu deseni
    3 koşumda bastıramadığı için eklendi (bkz. CHANGELOG SORUN 2C).
    `alt <= aday` yerine sayı-bazlı kapsama: tekil kalemler ham tablo satırından
    fazladan sayı taşısa bile roll-up yakalanır.
    """
    if len(riskler) < 3:
        return list(riskler)

    sayilar = [_kalem_sayilari(r) for r in riskler]
    elenecek: set = set()
    for i, aday in enumerate(sayilar):
        if len(aday) < 2 or i in elenecek:
            continue
        kat = riskler[i].get("risk_kategorisi")
        kapsayan_kalemler: set = set()
        her_sayi_baskada_var = True
        for sayi in aday:
            baskalari = {
                j for j, alt in enumerate(sayilar)
                if j != i and j not in elenecek and sayi in alt
                and riskler[j].get("risk_kategorisi") == kat
            }
            if not baskalari:
                her_sayi_baskada_var = False
                break
            kapsayan_kalemler |= baskalari
        if her_sayi_baskada_var and len(kapsayan_kalemler) >= 2:
            elenecek.add(i)

    return [r for i, r in enumerate(riskler) if i not in elenecek]


def ayni_baslik_index(baslik: str, adaylar: List[str]) -> Optional[int]:
    """`baslik`'e `Config.BASLIK_BENZERLIK_ESIGI` üstünde benzeyen ilk adayın indeksi.

    `token_sort_ratio` kelime sırasından bağımsızdır; Türkçe çoğul eki (-lar/-ler) ve
    birim yazım farkı ("116.737 TL" vs "116.737 bin TL") gibi yüzeysel farkları aynı
    kaleme indirir, "alacaklar" vs "borçlar" gibi karşıt kalemleri ayrı tutar.
    """
    if not baslik:
        return None
    for i, aday in enumerate(adaylar):
        if aday and fuzz.token_sort_ratio(baslik, aday) >= Config.BASLIK_BENZERLIK_ESIGI:
            return i
    return None


def _risk_signature(risk: BDRRiskItem) -> str:
    return f"{risk.baslik}. {risk.detay} {risk.etki_degerlendirmesi}"


def _risk_signature_dict(risk: dict) -> str:
    return f"{risk.get('baslik', '')}. {risk.get('detay', '')} {risk.get('etki_degerlendirmesi', '')}"


def dedup_risk_dicts(riskler: List[dict], api_key: Optional[str] = None) -> List[dict]:
    """Faz 7 global dedup: önce başlık, sonra (varsa) embedding yakın-tekrar birleştirme.

    Birleştirilen kalemlerin `kaynak_modeller` listeleri birleşir; hiçbir kalem içerik
    kaybı yaşamaz (en zengin detay tutulur).
    """
    kalanlar: List[dict] = []
    for risk in riskler:
        anahtar = _norm(risk.get("baslik") or "")
        if not anahtar:
            continue
        idx = ayni_baslik_index(anahtar, [_norm(k.get("baslik") or "") for k in kalanlar])
        if idx is None:
            kalanlar.append({**risk, "kaynak_modeller": list(risk.get("kaynak_modeller", []))})
        else:
            mevcut = kalanlar[idx]
            mevcut["kaynak_modeller"] = sorted(
                set(mevcut["kaynak_modeller"]) | set(risk.get("kaynak_modeller", []))
            )
            if len(str(risk.get("detay") or "")) > len(str(mevcut.get("detay") or "")):
                mevcut["detay"] = risk["detay"]
    if len(kalanlar) < 2 or not api_key:
        return kalanlar

    vektorler = _embed([_risk_signature_dict(r) for r in kalanlar], api_key)
    if not vektorler:
        return kalanlar

    tutulan: List[dict] = []
    tutulan_vek: List[List[float]] = []
    for risk, vek in zip(kalanlar, vektorler):
        eslesme = next(
            (
                i for i, tv in enumerate(tutulan_vek)
                if _cosine(vek, tv) >= Config.NEAR_DUP_THRESHOLD
                and tutulan[i].get("risk_kategorisi") == risk.get("risk_kategorisi")
            ),
            None,
        )
        if eslesme is None:
            tutulan.append(risk)
            tutulan_vek.append(vek)
        else:
            tutulan[eslesme]["kaynak_modeller"] = sorted(
                set(tutulan[eslesme].get("kaynak_modeller", [])) | set(risk.get("kaynak_modeller", []))
            )
    return tutulan


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def _embed(texts: List[str], api_key: str) -> Optional[List[List[float]]]:
    try:
        from openai import OpenAI

        response = OpenAI(api_key=api_key).embeddings.create(model=Config.EMBED_MODEL, input=texts)
        return [item.embedding for item in response.data]
    except Exception:
        return None


def _covered_by_tokens(candidate: BDRRiskItem, reference: List[BDRRiskItem]) -> bool:
    cand_tokens = set(_norm(candidate.baslik).split())
    if not cand_tokens:
        return True
    for ref in reference:
        ref_tokens = set(_norm(ref.baslik).split())
        union = cand_tokens | ref_tokens
        if union and len(cand_tokens & ref_tokens) / len(union) >= Config.JACCARD_THRESHOLD:
            return True
    return False


def uncovered_risks(
    candidate: List[BDRRiskItem],
    reference: List[BDRRiskItem],
    api_key: Optional[str] = None,
    threshold: Optional[float] = None,
) -> List[BDRRiskItem]:
    effective_threshold = threshold if threshold is not None else Config.COVERAGE_THRESHOLD
    """`reference` (sentez LLM listesi) tarafından kapsanmayan `candidate` risklerini döndürür.

    Sadece 'düşürülmüş' riskleri geri ekler; hiçbir riski birleştirmez veya silmez.
    Farklı dipnot referansına sahip kalemler asla kapsanmış sayılmaz.
    """
    if not candidate:
        return []
    if not reference:
        return list(candidate)

    ref_titles = {_norm(r.baslik) for r in reference}

    cand_vecs = ref_vecs = None
    if api_key:
        vectors = _embed(
            [_risk_signature(r) for r in candidate] + [_risk_signature(r) for r in reference],
            api_key,
        )
        if vectors:
            cand_vecs = vectors[: len(candidate)]
            ref_vecs = vectors[len(candidate):]

    missing: List[BDRRiskItem] = []
    for index, item in enumerate(candidate):
        if _norm(item.baslik) in ref_titles:
            continue

        same_note_refs = [
            (ref_index, ref)
            for ref_index, ref in enumerate(reference)
            if not item.dipnot_referansi
            or not ref.dipnot_referansi
            or _norm(ref.dipnot_referansi) == _norm(item.dipnot_referansi)
        ]
        if not same_note_refs:
            missing.append(item)
            continue

        if cand_vecs and ref_vecs:
            best = max(_cosine(cand_vecs[index], ref_vecs[ref_index]) for ref_index, _ in same_note_refs)
            if best >= effective_threshold:
                continue
        elif _covered_by_tokens(item, [ref for _, ref in same_note_refs]):
            continue

        missing.append(item)

    return missing
