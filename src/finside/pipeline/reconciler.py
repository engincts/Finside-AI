"""Faz 5 — Uzlaştırma: birden çok modelin risk listelerini tek listeye indirger.

Önce mekanik ön-birleştirme (fuzzy başlık kümeleme + en ihtiyatlı derece), sonra bir
Reconciler LLM çağrısı. LLM'in düşürdüğü kalemler recall için geri eklenir.
"""

import json
from typing import List, Tuple

from finside.dedupe import ayni_baslik_index, dedup_risk_dicts, rollup_ele
from finside.loaders.prompt_loader import PromptLoader
from finside.pipeline.llm_call import rapor_cagrisi
from finside.pipeline.state import TraceKaydi

RISK_DERECE_SIRA = {"Düşük": 0, "Orta": 1, "Yüksek": 2, "Kritik": 3}


import re

_DIPNOT_PREFIX_RE = re.compile(r"^dipnot\s+\d+\s*[-–:]\s*", re.IGNORECASE)


def _baslik(risk: dict) -> str:
    raw = (risk.get("baslik") or "").strip().lower()
    return _DIPNOT_PREFIX_RE.sub("", raw).strip()


def mekanik_birlestir(riskler: List[dict]) -> Tuple[List[dict], List[dict]]:
    kumeler: List[dict] = []
    celiskiler: List[dict] = []

    # Ön-birleştirme öncesi deterministik deduplikasyon ve roll-up temizliği
    temiz_riskler = dedup_risk_dicts(riskler)

    for risk in temiz_riskler:
        baslik = _baslik(risk)
        if not baslik:
            continue

        idx = ayni_baslik_index(baslik, [_baslik(k) for k in kumeler])
        if idx is None:
            kumeler.append({**risk, "kaynak_modeller": list(risk.get("kaynak_modeller", []))})
            continue

        mevcut = kumeler[idx]
        mevcut["kaynak_modeller"] = sorted(
            set(mevcut["kaynak_modeller"]) | set(risk.get("kaynak_modeller", []))
        )
        eski, yeni = str(mevcut.get("risk_derecesi")), str(risk.get("risk_derecesi"))
        if eski != yeni:
            celiskiler.append({
                "baslik": risk.get("baslik"), "alan": "risk_derecesi",
                "degerler": sorted({eski, yeni}),
            })
            if RISK_DERECE_SIRA.get(yeni, 1) > RISK_DERECE_SIRA.get(eski, 1):
                mevcut["risk_derecesi"] = risk.get("risk_derecesi")
        if len(str(risk.get("detay") or "")) > len(str(mevcut.get("detay") or "")):
            mevcut["detay"] = risk["detay"]

    return kumeler, celiskiler


def uzlastir(
    ham_riskler: List[dict],
    taslak_riskler: List[dict],
    model_id: str,
) -> Tuple[List[dict], List[dict], List[TraceKaydi]]:
    on_birlesik, celiskiler = mekanik_birlestir(ham_riskler + taslak_riskler)
    if len(on_birlesik) <= 1:
        return on_birlesik, celiskiler, []

    sistem, sablon = PromptLoader.load_prompt_md("reconciler_v1.md")
    sonuc = rapor_cagrisi(
        model_id,
        sablon.format(riskler_json=json.dumps(on_birlesik, ensure_ascii=False, indent=2)),
        asama="faz5-uzlastirma",
        system_prompt=sistem,
    )
    if sonuc.report.is_mock_fallback or not sonuc.report.tespit_edilen_riskler:
        return on_birlesik, celiskiler, [sonuc.trace]

    # kaynak_modeller izlenebilirlik alanıdır — LLM'in üretebileceği bir değer değil,
    # her zaman mekanik eşleşmeden (fuzzy başlık) deterministik olarak atanır.
    on_birlesik_basliklar = [_baslik(r) for r in on_birlesik]
    llm_riskler = []
    for risk in sonuc.report.tespit_edilen_riskler:
        veri = risk.model_dump(mode="json")
        idx = ayni_baslik_index(_baslik(veri), on_birlesik_basliklar)
        veri["kaynak_modeller"] = on_birlesik[idx].get("kaynak_modeller", []) if idx is not None else []
        llm_riskler.append(veri)

    llm_basliklar = [_baslik(r) for r in llm_riskler]
    geri_eklenen = [r for r in on_birlesik if ayni_baslik_index(_baslik(r), llm_basliklar) is None]
    
    # Post-hoc deterministik guard: LLM'in uydurabileceği özet/roll-up kalemlerini reddet
    nihai_liste = rollup_ele(llm_riskler + geri_eklenen)
    return nihai_liste, celiskiler, [sonuc.trace]
