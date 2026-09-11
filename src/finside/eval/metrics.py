"""Katman 1 — Etiketsiz otomatik kalite metrikleri (API gerektirmez).

Bir nihai raporu (final_report.json şeması) ham BDR metniyle karşılaştırıp
grounding, sayısal tutarlılık, kapsam ve şema sağlığını ölçer.
"""

from typing import Any, Dict, List

from finside.dedupe import _is_jenerik_etki, _onemli_sayilar
from finside.models import BDRRiskAnalysisReport, RiskKategorisi
from finside.pipeline.grounding import ground_riskler
from finside.pipeline.qa_rules import _buyuklukce_yakin, _DIPNOT_ONEK_RE, _olcekli_degerler, qa_bayraklari

_GROUNDING_ESIGI = 85.0
_TOPLAM_KATEGORI = len(RiskKategorisi)
_DIGER_KATEGORI = RiskKategorisi.DIGER_KALITATIF_RISK.value


def _oran(pay: int, payda: int) -> float:
    return round(pay / payda, 3) if payda else 0.0


def grounding_metrigi(riskler: List[dict], bdr_metni: str) -> Dict[str, Any]:
    _, dogrulanmayan = ground_riskler(riskler, bdr_metni, esik=_GROUNDING_ESIGI, kati_mod=False)
    toplam = len(riskler)
    return {
        "toplam_risk": toplam,
        "dogrulanmayan": dogrulanmayan,
        "grounding_orani": _oran(toplam - dogrulanmayan, toplam),
    }


def sayisal_tutarlilik_metrigi(riskler: List[dict], bdr_metni: str) -> Dict[str, Any]:
    kaynak_sayilar = _onemli_sayilar(bdr_metni)
    kaynak_tam = {int(s) for s in kaynak_sayilar}
    dogrulanan = 0
    sayili_kalem = 0
    tutarsiz_kalemler: List[str] = []
    for r in riskler:
        baslik_temiz = _DIPNOT_ONEK_RE.sub("", r.get("baslik") or "")
        kalem_sayilar = _onemli_sayilar(r.get("tutar_bilgisi") or "", baslik_temiz)
        if not kalem_sayilar:
            continue
        sayili_kalem += 1
        eslesmeyen = kalem_sayilar - kaynak_sayilar
        if eslesmeyen:
            olcekli = _olcekli_degerler(f"{r.get('tutar_bilgisi') or ''} {baslik_temiz}")
            eslesmeyen = {
                s for s in eslesmeyen
                if not any(_buyuklukce_yakin(o, kaynak_tam) for o in olcekli)
            }
        if not eslesmeyen:
            dogrulanan += 1
        else:
            tutarsiz_kalemler.append(r.get("baslik") or "?")
    return {
        "sayili_kalem": sayili_kalem,
        "kaynakta_dogrulanan": dogrulanan,
        "sayisal_tutarlilik_orani": _oran(dogrulanan, sayili_kalem),
        "tutarsiz_kalemler": tutarsiz_kalemler[:10],
    }


def kapsam_metrigi(riskler: List[dict]) -> Dict[str, Any]:
    toplam = len(riskler)
    kategoriler = {r.get("risk_kategorisi") for r in riskler if r.get("risk_kategorisi")}
    diger = sum(1 for r in riskler if r.get("risk_kategorisi") == _DIGER_KATEGORI)
    jenerik_etki = sum(1 for r in riskler if _is_jenerik_etki(r.get("etki_degerlendirmesi") or ""))
    jenerik_baslik = sum(
        1 for r in riskler
        if len((r.get("baslik") or "").split()) <= 3
        and not any(ch.isdigit() for ch in (r.get("baslik") or ""))
    )
    return {
        "farkli_kategori": len(kategoriler),
        "kategori_kapsam_orani": _oran(len(kategoriler), _TOPLAM_KATEGORI),
        "diger_kategori_orani": _oran(diger, toplam),
        "jenerik_etki_orani": _oran(jenerik_etki, toplam),
        "jenerik_baslik_orani": _oran(jenerik_baslik, toplam),
    }


def derece_dagilimi(riskler: List[dict]) -> Dict[str, int]:
    dagilim: Dict[str, int] = {}
    for r in riskler:
        derece = r.get("risk_derecesi") or "?"
        dagilim[derece] = dagilim.get(derece, 0) + 1
    return dagilim


def sema_metrigi(rapor: dict, segment_sayisi: int = 0) -> Dict[str, Any]:
    try:
        model = BDRRiskAnalysisReport.model_validate(rapor)
        bayraklar = qa_bayraklari(model, segment_sayisi)
    except Exception as exc:  # noqa: BLE001 — bozuk rapor da bir eval sinyalidir
        return {"qa_bayrak_sayisi": -1, "qa_bayraklari": [f"rapor doğrulanamadı: {exc}"]}
    return {"qa_bayrak_sayisi": len(bayraklar), "qa_bayraklari": bayraklar}


def taban_puan(katman1: Dict[str, Any]) -> float:
    """Gold set yoksa kaba kalite göstergesi. Kapsam (kategori) yüksek ağırlıklı:
    grounding/sayısal, az risk üretilince kolayca 1.0 çıkar — bu tek başına
    'iyi rapor' demek değildir, o yüzden düşük kapsam sert cezalandırılır.
    """
    grounding = katman1["grounding"]["grounding_orani"]
    sayisal = katman1["sayisal"]["sayisal_tutarlilik_orani"]
    somut_etki = 1.0 - katman1["kapsam"]["jenerik_etki_orani"]
    kategori = katman1["kapsam"]["kategori_kapsam_orani"]
    qa = katman1["sema"]["qa_bayrak_sayisi"]
    qa_puan = max(0.0, 1.0 - 0.15 * qa) if qa >= 0 else 0.0
    puan = 100 * (
        0.30 * grounding
        + 0.15 * sayisal
        + 0.20 * somut_etki
        + 0.25 * kategori
        + 0.10 * qa_puan
    )
    return round(puan, 1)


def katman1_metrikleri(rapor: dict, bdr_metni: str, segment_sayisi: int = 0) -> Dict[str, Any]:
    riskler = rapor.get("tespit_edilen_riskler") or []
    katman1 = {
        "grounding": grounding_metrigi(riskler, bdr_metni),
        "sayisal": sayisal_tutarlilik_metrigi(riskler, bdr_metni),
        "kapsam": kapsam_metrigi(riskler),
        "derece_dagilimi": derece_dagilimi(riskler),
        "sema": sema_metrigi(rapor, segment_sayisi),
    }
    katman1["taban_puan"] = taban_puan(katman1)
    return katman1
