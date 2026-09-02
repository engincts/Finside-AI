"""Faz 8 — Kural tabanlı tutarlılık kontrolü (LLM'siz son "akıl sağlığı" adımı)."""

from typing import List

from prompts.schemas import BDRRiskAnalysisReport, DenetciGorusTuru, KomiteKararEgilimi, RiskDerecesi

_DOGRULANMAMIS_ESIGI = 0.30
_BOS_RISK_SEGMENT_ESIGI = 20


def qa_bayraklari(report: BDRRiskAnalysisReport, segment_sayisi: int) -> List[str]:
    bayraklar: List[str] = []
    riskler = report.tespit_edilen_riskler

    if report.is_mock_fallback:
        bayraklar.append(
            "Sentez adımı API hatası/kota nedeniyle mock çıktıya düştü — genel özet, "
            f"karar eğilimi ve gerekçe güvenilir DEĞİL. ({report.fallback_reason})"
        )

    kritik_var = any(r.risk_derecesi == RiskDerecesi.KRITIK for r in riskler)
    if kritik_var and report.karar_egilimi == KomiteKararEgilimi.OLUMLU:
        bayraklar.append("KRİTİK dereceli risk varken karar eğilimi 'Olumlu' — gözden geçirilmeli.")

    olumsuz_gorusler = {DenetciGorusTuru.OLUMSUZ, DenetciGorusTuru.GORUS_BILDIRMEKTEN_KACINMA}
    if report.denetci_gorusu in olumsuz_gorusler and report.karar_egilimi == KomiteKararEgilimi.OLUMLU:
        bayraklar.append(
            f"Denetçi görüşü '{report.denetci_gorusu.value}' iken karar eğilimi 'Olumlu' — çelişkili."
        )

    if riskler:
        dogrulanmamis = sum(1 for r in riskler if r.dogrulanmadi)
        if dogrulanmamis / len(riskler) > _DOGRULANMAMIS_ESIGI:
            bayraklar.append(
                f"Risklerin %{round(100 * dogrulanmamis / len(riskler))}'i kaynak metinde doğrulanamadı."
            )

    if not riskler and segment_sayisi > _BOS_RISK_SEGMENT_ESIGI:
        bayraklar.append(
            f"{segment_sayisi} segment işlendi ama hiç risk bulunamadı — olası pipeline hatası."
        )

    return bayraklar
