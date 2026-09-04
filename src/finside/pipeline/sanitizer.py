"""Faz 6.5 — Sanitizer Ajanı: Küçük/hızlı LLM çağrısı ile sözde riskleri ve jenerik tekrarları süzer."""

import json
from typing import List, Tuple

from config import Config
from finside.loaders.prompt_loader import PromptLoader
from finside.pipeline.llm_call import rapor_cagrisi


def riskleri_temizle(riskler: List[dict], model_id: str) -> Tuple[List[dict], List[dict]]:
    """Ham/uzlaştırılmış risk listesinden jenerik ve sözde riskleri küçük/hızlı LLM filtresiyle temizler."""
    if len(riskler) < 2:
        return riskler, []

    sistem = (
        "Sen Kıdemli bir Kredi Risk Filtreleme ve Temizleme Ajanısın.\n"
        "Görevin: Verilen BDR kalitatif risk listesini inceleyip GERÇEK kredi riski taşıyan maddeleri korumak;\n"
        "1. Hiçbir kısıt veya finansal tehdit taşımayan salt bilanço bakiyelerini (örn: 'Nakit ve Nakit Benzerleri', 'Sunuma İlişkin Esaslar') ELEMEK,\n"
        "2. 'Borç ödeme kapasitesi üzerindeki olası etki' gibi jenerik/boş etki cümleli ve dipnotsuz jenerik tekrarları ELEMEK veya aynı kategorideki daha spesifik dipnot riskiyle BİRLEŞTİRMEKtir.\n"
        "Sadece temizlenmiş ve süzülmüş nihai `tespit_edilen_riskler` listesini üret."
    )

    user_prompt = f"Lütfen aşağıdaki risk listesini süzerek jenerik/sözde riskleri temizle:\n\n{json.dumps(riskler, ensure_ascii=False, indent=2)}"

    try:
        sonuc = rapor_cagrisi(
            model_id, user_prompt, asama="faz6.5-sanitizer", system_prompt=sistem
        )
        if sonuc.report and sonuc.report.tespit_edilen_riskler and not sonuc.report.is_mock_fallback:
            temiz = [r.model_dump() for r in sonuc.report.tespit_edilen_riskler]
            return temiz, sonuc.trace
    except Exception:
        pass

    return riskler, []
