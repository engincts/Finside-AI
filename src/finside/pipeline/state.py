import operator
from typing import Annotated, List, Literal, Optional, TypedDict


class Segment(TypedDict):
    sira_no: int
    baslik: str
    ham_metin: str
    karakter_sayisi: int
    baslangic_offset: int
    bitis_offset: int


class TriajKarari(TypedDict):
    segment_sira_no: int
    dahil: bool
    yontem: Literal["kural", "boilerplate", "llm"]
    gerekce: str


class SegmentGrubu(TypedDict):
    grup_id: int
    segment_sira_nolari: List[int]
    birlesik_metin: str
    tahmini_token: int


class MapCiktisi(TypedDict):
    grup_id: int
    model_id: str
    riskler: List[dict]
    hata_durumu: Optional[str]
    sure_sn: float


class TraceKaydi(TypedDict):
    asama: str
    model_id: Optional[str]
    provider: Optional[str]
    girdi_karakter: int
    cikti_karakter: int
    sure_sn: float
    basari: bool
    hata: Optional[str]


class PipelineState(TypedDict, total=False):
    """Ana LangGraph state. Reducer'lı alanlara paralel node'lar birikimli yazar."""

    # --- girdi ---
    bdr_id: str
    bdr_adi: str
    ham_metin: str
    session_dir: str
    secili_map_modelleri: List[str]

    # --- Faz 1 ---
    segmentler: List[Segment]
    segmentasyon_guven: float
    segmentasyon_yontemi: Literal["regex", "llm_fallback"]

    # --- Faz 2 ---
    triaj_kararlari: List[TriajKarari]
    analiz_edilecek_sira_nolari: List[int]

    # --- Faz 3 ---
    segment_gruplari: List[SegmentGrubu]
    map_ciktilari: Annotated[List[MapCiktisi], operator.add]

    # --- Faz 4-6 (grup alt-grafı sonuçları) ---
    uzlastirilmis_riskler: Annotated[List[dict], operator.add]
    celiskiler: Annotated[List[dict], operator.add]
    critic_turlari: Annotated[List[dict], operator.add]

    # --- Faz 7-8 ---
    nihai_rapor: dict
    qa_bayraklari: List[str]

    # --- trace / Faz 10 ---
    trace: Annotated[List[TraceKaydi], operator.add]
    maliyet_ozeti: dict


class GrupState(TypedDict, total=False):
    """group_graph alt-grafının state'i (Faz 4-6). Ana state'ten Send ile beslenir.

    `uzlastirilmis_riskler` / `celiskiler` / `critic_turlari` / `trace` isimleri ve
    reducer'ları `PipelineState` ile aynıdır; alt-graf bitince ana state'e taşınır.
    """

    # Send ile gelen
    grup_id: int
    birlesik_metin: str
    ham_riskler: List[dict]
    # çalışma
    taslak_riskler: List[dict]
    critic_tur: int
    son_critic_eklenen: int
    # ana state'e taşınan (operator.add)
    uzlastirilmis_riskler: Annotated[List[dict], operator.add]
    celiskiler: Annotated[List[dict], operator.add]
    critic_turlari: Annotated[List[dict], operator.add]
    trace: Annotated[List[TraceKaydi], operator.add]
