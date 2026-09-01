"""Faz 4-6 — Grup alt-grafı: ground → reconcile ⇄ critic (döngü) → grup_bitir.

Ana graf her segment grubu için `Send("grup_isle", …)` ile bu alt-grafı çalıştırır.
Alt-grafın `uzlastirilmis_riskler` / `celiskiler` / `critic_turlari` / `trace` çıktıları
ana `PipelineState`'e (aynı isim + `operator.add`) taşınır.
"""

from langgraph.graph import START, END, StateGraph

from config import Config
from finside.pipeline.critic import eksik_tara
from finside.pipeline.grounding import ground_riskler
from finside.pipeline.reconciler import uzlastir
from finside.pipeline.state import GrupState


def _ground(state: GrupState) -> dict:
    pc = Config.get_pipeline_config()
    grounded, _ = ground_riskler(
        state["ham_riskler"],
        state["birlesik_metin"],
        esik=float(pc["grounding_esigi"]),
        kati_mod=bool(pc["grounding_katimod"]),
    )
    return {"ham_riskler": grounded}


def _reconcile(state: GrupState) -> dict:
    pc = Config.get_pipeline_config()
    taslak, celiskiler, izler = uzlastir(
        state["ham_riskler"], state.get("taslak_riskler", []), pc["reconciler_model"],
    )
    ilk_gecis = state.get("critic_tur", 0) == 0
    return {
        "taslak_riskler": taslak,
        "celiskiler": celiskiler if ilk_gecis else [],
        "trace": izler,
    }


def _critic(state: GrupState) -> dict:
    pc = Config.get_pipeline_config()
    yeni, izler = eksik_tara(
        state["taslak_riskler"], state["ham_riskler"],
        state["birlesik_metin"], pc["critic_model"],
    )
    return {
        "taslak_riskler": state["taslak_riskler"] + yeni,
        "critic_tur": state.get("critic_tur", 0) + 1,
        "son_critic_eklenen": len(yeni),
        "trace": izler,
    }


def _route_critic(state: GrupState) -> str:
    pc = Config.get_pipeline_config()
    if state.get("son_critic_eklenen", 0) > 0 and state.get("critic_tur", 0) < int(pc["max_critic_turu"]):
        return "reconcile"
    return "grup_bitir"


def _grup_bitir(state: GrupState) -> dict:
    return {
        "uzlastirilmis_riskler": state.get("taslak_riskler", []),
        "critic_turlari": [{
            "grup_id": state["grup_id"],
            "tur": state.get("critic_tur", 0),
            "son_eklenen": state.get("son_critic_eklenen", 0),
        }],
    }


def build_group_graph():
    graph = StateGraph(GrupState)
    graph.add_node("ground", _ground)
    graph.add_node("reconcile", _reconcile)
    graph.add_node("critic", _critic)
    graph.add_node("grup_bitir", _grup_bitir)

    graph.add_edge(START, "ground")
    graph.add_edge("ground", "reconcile")
    graph.add_edge("reconcile", "critic")
    graph.add_conditional_edges("critic", _route_critic, ["reconcile", "grup_bitir"])
    graph.add_edge("grup_bitir", END)

    return graph.compile()
