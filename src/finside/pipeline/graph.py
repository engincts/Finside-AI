"""Ana LangGraph pipeline. Faz 1-3 iskeleti; Faz 4+ ile genişletilir.

Mevcut akış:
  segmentle → triyaj_yap → gruplari_olustur ─(Send: grup×model)→ map_worker → map_topla → END
"""

from langgraph.graph import START, END, StateGraph

from finside.pipeline.nodes.map_extract import map_dagit, map_topla, map_worker
from finside.pipeline.nodes.segment import segmentle
from finside.pipeline.nodes.triage import gruplari_olustur, triyaj_yap
from finside.pipeline.state import PipelineState


def build_graph(checkpointer=None):
    graph = StateGraph(PipelineState)

    graph.add_node("segmentle", segmentle)
    graph.add_node("triyaj_yap", triyaj_yap)
    graph.add_node("gruplari_olustur", gruplari_olustur)
    graph.add_node("map_worker", map_worker)
    graph.add_node("map_topla", map_topla)

    graph.add_edge(START, "segmentle")
    graph.add_edge("segmentle", "triyaj_yap")
    graph.add_edge("triyaj_yap", "gruplari_olustur")
    graph.add_conditional_edges("gruplari_olustur", map_dagit, ["map_worker"])
    graph.add_edge("map_worker", "map_topla")
    graph.add_edge("map_topla", END)

    return graph.compile(checkpointer=checkpointer)
