from typing import List

from langgraph.types import Send

from finside.pipeline.state import PipelineState


def grup_dagit(state: PipelineState) -> List[Send]:
    """map_topla sonrası fan-out: her segment grubu için grup alt-grafı (grup_isle)."""
    ciktilar = state["map_ciktilari"]
    gonderiler: List[Send] = []
    for grup in state["segment_gruplari"]:
        ham_riskler = [
            risk
            for cikti in ciktilar
            if cikti["grup_id"] == grup["grup_id"]
            for risk in cikti["riskler"]
        ]
        gonderiler.append(Send("grup_isle", {
            "grup_id": grup["grup_id"],
            "birlesik_metin": grup["birlesik_metin"],
            "ham_riskler": ham_riskler,
            "critic_tur": 0,
        }))
    return gonderiler
