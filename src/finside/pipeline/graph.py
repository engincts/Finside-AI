"""Ana LangGraph pipeline. Faz 1-2 iskeleti; Faz 3+ ile genişletilir.

Mevcut akış: segmentle → triyaj_yap → gruplari_olustur → END
"""

from langgraph.graph import START, END, StateGraph

from finside.pipeline.nodes.segment import segmentle
from finside.pipeline.nodes.triage import gruplari_olustur, triyaj_yap
from finside.pipeline.state import PipelineState


def build_graph(checkpointer=None):
    graph = StateGraph(PipelineState)

    graph.add_node("segmentle", segmentle)
    graph.add_node("triyaj_yap", triyaj_yap)
    graph.add_node("gruplari_olustur", gruplari_olustur)

    graph.add_edge(START, "segmentle")
    graph.add_edge("segmentle", "triyaj_yap")
    graph.add_edge("triyaj_yap", "gruplari_olustur")
    graph.add_edge("gruplari_olustur", END)

    return graph.compile(checkpointer=checkpointer)
