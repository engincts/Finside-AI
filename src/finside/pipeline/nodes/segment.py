from pathlib import Path

from config import Config
from finside.loaders.bdr_segmenter import segment_bdr
from finside.pipeline.state import PipelineState
from finside.writers import ReportWriter


def segmentle(state: PipelineState) -> dict:
    pc = Config.get_pipeline_config()
    sonuc = segment_bdr(
        state["ham_metin"],
        guven_esigi=pc["segmenter_guven_esigi"],
        fallback_model=pc["segmenter_fallback_model"],
    )

    session_dir = Path(state["session_dir"])
    ReportWriter.save_json(session_dir, "segments.json", {
        "yontem": sonuc.yontem,
        "guven": sonuc.guven,
        "segment_sayisi": len(sonuc.segmentler),
        "segmentler": [
            {k: v for k, v in s.items() if k != "ham_metin"} | {"onizleme": s["ham_metin"][:200]}
            for s in sonuc.segmentler
        ],
    })

    return {
        "segmentler": sonuc.segmentler,
        "segmentasyon_guven": sonuc.guven,
        "segmentasyon_yontemi": sonuc.yontem,
        "trace": list(sonuc.izler),
    }
