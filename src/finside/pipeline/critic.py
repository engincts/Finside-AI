"""Faz 6 — Critic: uzlaştırılmış taslakta gözden kaçmış riskleri arar (recall ikinci geçiş).

Ön-filtre: ham risklerden taslakta olmayan başlıklar critic'e "özellikle bunlara bak"
ipucu olarak verilir. Kör aramadan daha isabetli.
"""

import json
from typing import List, Tuple

from finside.dedupe import ayni_baslik_index
from finside.loaders.prompt_loader import PromptLoader
from finside.pipeline.llm_call import rapor_cagrisi
from finside.pipeline.state import TraceKaydi


def _baslik(risk: dict) -> str:
    return (risk.get("baslik") or "").strip().lower()


def _kapsanmayan(ham_riskler: List[dict], taslak_riskler: List[dict]) -> List[dict]:
    taslak_basliklar = [_baslik(r) for r in taslak_riskler]
    return [r for r in ham_riskler if ayni_baslik_index(_baslik(r), taslak_basliklar) is None]


def eksik_tara(
    taslak_riskler: List[dict],
    ham_riskler: List[dict],
    birlesik_metin: str,
    model_id: str,
) -> Tuple[List[dict], List[TraceKaydi]]:
    ipuclari = [r.get("baslik") for r in _kapsanmayan(ham_riskler, taslak_riskler)]
    sistem, sablon = PromptLoader.load_prompt_md("critic_v1.md")
    sonuc = rapor_cagrisi(
        model_id,
        sablon.format(
            taslak_json=json.dumps(taslak_riskler, ensure_ascii=False, indent=2),
            ipucu_json=json.dumps(ipuclari, ensure_ascii=False),
            metin=birlesik_metin,
        ),
        asama="faz6-critic",
        system_prompt=sistem,
    )
    if sonuc.report.is_mock_fallback:
        return [], [sonuc.trace]

    mevcut = [_baslik(r) for r in taslak_riskler]
    yeni = []
    for r in sonuc.report.tespit_edilen_riskler:
        veri = r.model_dump(mode="json")
        if ayni_baslik_index(_baslik(veri), mevcut) is not None:
            continue
        veri["kaynak_modeller"] = ["critic"]  # LLM'in ürettiği değeri değil, deterministik işareti kullan
        yeni.append(veri)
    return yeni, [sonuc.trace]
