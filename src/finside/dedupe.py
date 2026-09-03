import math
from typing import List, Optional

from config import Config
from finside.models import BDRRiskItem


def _norm(text: str) -> str:
    return text.strip().lower()


def _risk_signature(risk: BDRRiskItem) -> str:
    return f"{risk.baslik}. {risk.detay} {risk.etki_degerlendirmesi}"


def _risk_signature_dict(risk: dict) -> str:
    return f"{risk.get('baslik', '')}. {risk.get('detay', '')} {risk.get('etki_degerlendirmesi', '')}"


def dedup_risk_dicts(riskler: List[dict], api_key: Optional[str] = None) -> List[dict]:
    """Faz 7 global dedup: önce başlık, sonra (varsa) embedding yakın-tekrar birleştirme.

    Birleştirilen kalemlerin `kaynak_modeller` listeleri birleşir; hiçbir kalem içerik
    kaybı yaşamaz (en zengin detay tutulur).
    """
    basliga_gore: dict = {}
    for risk in riskler:
        anahtar = _norm(risk.get("baslik") or "")
        if not anahtar:
            continue
        if anahtar not in basliga_gore:
            basliga_gore[anahtar] = {**risk, "kaynak_modeller": list(risk.get("kaynak_modeller", []))}
        else:
            mevcut = basliga_gore[anahtar]
            mevcut["kaynak_modeller"] = sorted(
                set(mevcut["kaynak_modeller"]) | set(risk.get("kaynak_modeller", []))
            )
            if len(str(risk.get("detay") or "")) > len(str(mevcut.get("detay") or "")):
                mevcut["detay"] = risk["detay"]

    kalanlar = list(basliga_gore.values())
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
