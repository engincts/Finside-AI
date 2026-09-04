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


def is_rollup_of(aday: dict, digerleri: List[dict]) -> bool:
    """`aday`, `digerleri` içinden AYNI kategorideki ≥2 kalemin tutarlarını bir araya
    toplayan ve kendine özgü hiçbir sayı getirmeyen bir "özet/roll-up" kalemi mi?

    Deterministik: `tutar_bilgisi`/`detay`/`baslik`'teki 4+ haneli sayıları (yıl hariç,
    binlik/ondalık ayıraç temizli) karşılaştırır — LLM muhakemesi yok. Tekil kalemler
    ham tablo satırından fazladan sayı taşısa bile çalışır (aday ⊆ diğer değil,
    aday'ın HER sayısı ≥1 diğer kalemde aranır).
    """
    aday_sayilari = _kalem_sayilari(aday)
    if len(aday_sayilari) < 2:
        return False
    kat = aday.get("risk_kategorisi")
    ayni_kat = [
        (j, _kalem_sayilari(d)) for j, d in enumerate(digerleri)
        if d.get("risk_kategorisi") == kat
    ]
    kapsayan_idx: set = set()
    for sayi in aday_sayilari:
        eslesen = {j for j, sayilar in ayni_kat if sayi in sayilar}
        if not eslesen:
            return False
        kapsayan_idx |= eslesen
    return len(kapsayan_idx) >= 2


def rollup_ele(riskler: List[dict]) -> List[dict]:
    """`is_rollup_of` ile "özet/roll-up" kalemlerini listeden eler.

    Prompt-seviyesi yasak bu deseni 4 koşumdan 2'sinde bastıramadı (bkz. CHANGELOG
    SORUN 2C); bu deterministik kod-seviyesi garanti.
    """
    if len(riskler) < 3:
        return list(riskler)
    return [
        risk for i, risk in enumerate(riskler)
        if not is_rollup_of(risk, riskler[:i] + riskler[i + 1:])
    ]


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


def _local_text_similarity(t1: str, t2: str) -> float:
    """Yerel anlamsal kelime kümesi ve TF-IDF Kosinüs Benzerliği (Cosine Similarity) skoru."""
    s1 = set(_norm(t1).split())
    s2 = set(_norm(t2).split())
    if not s1 or not s2:
        return 0.0
    w1 = {w for w in s1 if len(w) >= 4}
    w2 = {w for w in s2 if len(w) >= 4}
    if not w1 or not w2:
        return 0.0
    jaccard = len(w1 & w2) / len(w1 | w2)

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        matrix = vec.fit_transform([t1, t2])
        arr = matrix.toarray()
        cos_sim = _cosine(arr[0].tolist(), arr[1].tolist())
        return max(jaccard, cos_sim)
    except Exception:
        return jaccard


_JENERIK_PATTERN = re.compile(
    r"(borç\s+ödeme|likidite|finansal\s+durum|kapasitesi?|faaliyet|performans|nakit\s+akışı|ödeme\s+dengesi|borçluluk\s+rasyoları)"
    r".*(olası|etki|yansı|sonuç|değerlendir|baskı|doğrudan\s+etki)",
    re.IGNORECASE | re.DOTALL
)


def _is_jenerik_etki(etki: str) -> bool:
    if not etki:
        return True
    etki_clean = etki.strip().lower()
    if len(etki_clean) < 20:
        return True
    if "nakit akışı, ödeme dengesi ve borçluluk rasyoları" in etki_clean:
        return True
    has_specifics = bool(re.search(r"\d|yüzde|%|ipotek|rehin|kefalet|dava|hedg|kambiyo|vergi|karşılık|bulaşma|türev", etki_clean))
    if _JENERIK_PATTERN.search(etki_clean) and not has_specifics:
        return True
    return False


_NARRATIVE_AUDIT_PATTERNS = re.compile(
    r"(denetç|denetim|kam\b|kilit\s+denetim|iç\s+kontrol|zafiyet|faaliyet\s+süreklili|going\s+concern|bilanço\s+sonrası|birleşme|satın\s+alma|yönetsel|uyum|ilişkili\s+taraf)",
    re.IGNORECASE
)


def _is_narrative_category(risk: dict) -> bool:
    kat = str(risk.get("risk_kategorisi") or "").lower()
    baslik = str(risk.get("baslik") or "").lower()
    return bool(_NARRATIVE_AUDIT_PATTERNS.search(f"{kat} {baslik}"))


def jenerik_ve_tekrarlayan_ele(riskler: List[dict]) -> List[dict]:
    """Tüm gruplardan gelen kalemler arasında jenerik/sözde (örn: 'Kur Riski', 'Likidite Riski') ve
    şablon etki cümleli tekrarlayan kalemleri eler ve kaynak modellerini spesifik kaleme aktarır.
    Anlatı-tabanlı denetim ve birleşme kategorileri (İç Kontrol, KAM, Faaliyet Sürekliliği)
    rakamsız olsa dahi korunur.
    """
    if len(riskler) < 2:
        return list(riskler)

    elenen_indeksler = set()
    for i, risk in enumerate(riskler):
        if i in elenen_indeksler:
            continue
        baslik = _norm(risk.get("baslik") or "")
        etki = risk.get("etki_degerlendirmesi") or ""

        # Anlatı tabanlı denetim/birleşme kalemleri rakamsız olsa dahi jenerik sayılmaz
        is_narrative = _is_narrative_category(risk)
        if is_narrative:
            is_jenerik = False
        else:
            is_jenerik = _is_jenerik_etki(etki) or not risk.get("tutar_bilgisi") or "Tutarsız" in str(risk.get("tutar_bilgisi")) or "Belirtilmemiş" in str(risk.get("tutar_bilgisi"))

        for j, diger in enumerate(riskler):
            if i == j or j in elenen_indeksler:
                continue
            diger_baslik = _norm(diger.get("baslik") or "")
            diger_etki = diger.get("etki_degerlendirmesi") or ""
            diger_jenerik = _is_jenerik_etki(diger_etki)
            diger_spesifik = not diger_jenerik or bool(diger.get("dipnot_referansi"))

            is_overlap = (baslik in diger_baslik or diger_baslik in baslik)
            is_generic_vs_specific = is_jenerik and diger_spesifik and (is_overlap or not risk.get("dipnot_referansi"))

            if is_generic_vs_specific:
                diger["kaynak_modeller"] = sorted(
                    set(diger.get("kaynak_modeller", [])) | set(risk.get("kaynak_modeller", []))
                )
                elenen_indeksler.add(i)
                break

    return [r for i, r in enumerate(riskler) if i not in elenen_indeksler]


def dedup_risk_dicts(riskler: List[dict], api_key: Optional[str] = None) -> List[dict]:
    """Faz 7 global cross-group dedup: deterministik roll-up, jenerik tekrar elenmesi,
    küresel (kategoriler arası) sayısal eşleşme ve anlamsal yakın-tekrar birleştirme.

    Farklı gruplardan (chunk) gelen aynı finansal rakamı veya alıntıyı taşıyan kalemler
    farklı kategorilere atanmış olsa bile küresel olarak birleştirilir.
    """
    # 1. Deterministik Özet/Roll-Up ve Jenerik/Şablon Tekrar Elenmesi
    riskler = rollup_ele(riskler)
    riskler = jenerik_ve_tekrarlayan_ele(riskler)

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

    if len(kalanlar) < 2:
        return kalanlar

    if api_key:
        vektorler = _embed([_risk_signature_dict(r) for r in kalanlar], api_key)
        if vektorler:
            tutulan: List[dict] = []
            tutulan_vek: List[List[float]] = []
            for risk, vek in zip(kalanlar, vektorler):
                sayilar = _kalem_sayilari(risk)
                eslesme = None
                for i, tv in enumerate(tutulan_vek):
                    mev = tutulan[i]
                    mev_sayilar = _kalem_sayilari(mev)
                    sayi_eslesmesi = bool(sayilar and mev_sayilar and sayilar.intersection(mev_sayilar))
                    sim = _cosine(vek, tv)
                    kat_eslesmesi = (mev.get("risk_kategorisi") == risk.get("risk_kategorisi"))
                    if sayi_eslesmesi or (sim >= Config.NEAR_DUP_THRESHOLD and kat_eslesmesi) or sim >= 0.90:
                        eslesme = i
                        break
                if eslesme is None:
                    tutulan.append(risk)
                    tutulan_vek.append(vek)
                else:
                    tutulan[eslesme]["kaynak_modeller"] = sorted(
                        set(tutulan[eslesme].get("kaynak_modeller", [])) | set(risk.get("kaynak_modeller", []))
                    )
                    if len(str(risk.get("detay") or "")) > len(str(tutulan[eslesme].get("detay") or "")):
                        tutulan[eslesme]["detay"] = risk["detay"]
            return tutulan

    # API Key Yoksa veya Embedding Fallback Durumunda: Yerel Küresel Anlamsal Birleştirme
    tutulan_yerel: List[dict] = []
    for risk in kalanlar:
        sig = _risk_signature_dict(risk)
        kat = risk.get("risk_kategorisi")
        sayilar = _kalem_sayilari(risk)
        alinti = _norm(risk.get("kaynak_alinti") or "")

        eslesme_idx = None
        for i, mev in enumerate(tutulan_yerel):
            mev_kat = mev.get("risk_kategorisi")
            mev_sayilar = _kalem_sayilari(mev)
            mev_alinti = _norm(mev.get("kaynak_alinti") or "")

            sayi_eslesmesi = bool(sayilar and mev_sayilar and sayilar.intersection(mev_sayilar))
            alinti_eslesmesi = bool(alinti and mev_alinti and (alinti in mev_alinti or mev_alinti in alinti or _local_text_similarity(alinti, mev_alinti) >= 0.70))
            sim = _local_text_similarity(sig, _risk_signature_dict(mev))

            kat_eslesmesi = (kat and mev_kat == kat)
            # Sayı veya alıntı eşleşmesi varsa kategori fark etmeksizin dedup yap
            if sayi_eslesmesi or alinti_eslesmesi or (kat_eslesmesi and sim >= 0.65) or sim >= 0.85:
                eslesme_idx = i
                break

        if eslesme_idx is None:
            tutulan_yerel.append(risk)
        else:
            tutulan_yerel[eslesme_idx]["kaynak_modeller"] = sorted(
                set(tutulan_yerel[eslesme_idx].get("kaynak_modeller", [])) | set(risk.get("kaynak_modeller", []))
            )
            if len(str(risk.get("detay") or "")) > len(str(tutulan_yerel[eslesme_idx].get("detay") or "")):
                tutulan_yerel[eslesme_idx]["detay"] = risk["detay"]

    return tutulan_yerel


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
