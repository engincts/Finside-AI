"""Ana LangGraph pipeline. Faz 1-8.

Akış:
  segmentle → triyaj_yap → gruplari_olustur ─(Send: grup×model)→ map_worker → map_topla
  ─(Send: grup)→ grup_isle (alt-graf: ground → reconcile ⇄ critic) → sentezle → qa_kontrol → END
"""

from langgraph.graph import START, END, StateGraph

from finside.pipeline.group_graph import build_group_graph
from finside.pipeline.nodes.group import grup_dagit
from finside.pipeline.nodes.map_extract import map_dagit, map_topla, map_worker
from finside.pipeline.nodes.segment import segmentle
from finside.pipeline.nodes.synthesis import qa_kontrol, sentezle
from finside.pipeline.nodes.triage import gruplari_olustur, triyaj_yap
from finside.pipeline.state import PipelineState


def build_graph(checkpointer=None):
    graph = StateGraph(PipelineState)

    graph.add_node("segmentle", segmentle)
    graph.add_node("triyaj_yap", triyaj_yap)
    graph.add_node("gruplari_olustur", gruplari_olustur)
    graph.add_node("map_worker", map_worker)
    graph.add_node("map_topla", map_topla)
    graph.add_node("grup_isle", build_group_graph())
    graph.add_node("sentezle", sentezle)
    graph.add_node("qa_kontrol", qa_kontrol)

    graph.add_edge(START, "segmentle")
    graph.add_edge("segmentle", "triyaj_yap")
    graph.add_edge("triyaj_yap", "gruplari_olustur")
    graph.add_conditional_edges("gruplari_olustur", map_dagit, ["map_worker"])
    graph.add_edge("map_worker", "map_topla")
    graph.add_conditional_edges("map_topla", grup_dagit, ["grup_isle"])
    graph.add_edge("grup_isle", "sentezle")
    graph.add_edge("sentezle", "qa_kontrol")
    graph.add_edge("qa_kontrol", END)

    return graph.compile(checkpointer=checkpointer)
