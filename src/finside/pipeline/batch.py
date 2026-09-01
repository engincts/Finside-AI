"""Faz 9 — Toplu (batch) pipeline çalıştırma.

Her BDR ayrı bir `thread_id` ile çalışır; checkpointer (Postgres) sayesinde bir BDR
hata alırsa yalnızca o thread başarısız node'dan devam eder.
"""

import warnings
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from config import Config
from finside.loaders import BDRLoader
from finside.pipeline.graph import build_graph
from finside.writers import ReportWriter


def _checkpointer() -> Tuple[object, Optional[object]]:
    url = Config.get_pipeline_db_url()
    if url:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            if "connect_timeout" not in url:
                url += ("&" if "?" in url else "?") + "connect_timeout=5"
            ctx = PostgresSaver.from_conn_string(url)
            saver = ctx.__enter__()
            saver.setup()
            return saver, ctx
        except Exception as exc:  # noqa: BLE001 — Postgres yoksa geliştirme durmasın
            warnings.warn(
                f"Postgres checkpointer kurulamadı ({exc}); MemorySaver'a düşülüyor.",
                stacklevel=2,
            )
    else:
        warnings.warn(
            "PIPELINE_DB_URL tanımsız — MemorySaver kullanılıyor (batch resume kalıcı değil).",
            stacklevel=2,
        )

    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver(), None


def _bdr_calistir(dosya: Path, session_dir: Path, secili_modeller: List[str], graph) -> dict:
    bilgi = BDRLoader(dosya).get_processed_bdr()
    return graph.invoke(
        {
            "bdr_id": dosya.stem,
            "bdr_adi": bilgi["file_name"],
            "ham_metin": bilgi["content"],
            "session_dir": str(session_dir),
            "secili_map_modelleri": secili_modeller,
        },
        config={"configurable": {"thread_id": dosya.stem}},
    )


def calistir_batch(klasor: str, secili_modeller: Optional[List[str]] = None) -> List[dict]:
    dosyalar = sorted(Path(klasor).glob("*.txt"))
    if not dosyalar:
        raise FileNotFoundError(f"{klasor} içinde .txt BDR dosyası bulunamadı.")

    secili_modeller = secili_modeller or []
    varsayilan_modeller = Config.get_pipeline_config()["map_models"]
    now = datetime.now()
    kok = Config.OUTPUT_DIR / now.strftime("%Y-%m-%d") / now.strftime("%H-%M-%S")
    kok.mkdir(parents=True, exist_ok=True)

    saver, ctx = _checkpointer()
    ozet: List[dict] = []
    try:
        graph = build_graph(checkpointer=saver)
        for dosya in dosyalar:
            session_dir = kok / dosya.stem
            session_dir.mkdir(parents=True, exist_ok=True)
            state = _bdr_calistir(dosya, session_dir, secili_modeller, graph)

            nihai = state.get("nihai_rapor", {})
            maliyet = state.get("maliyet_ozeti") or {}
            ozet.append({
                "dosya": dosya.name,
                "firma": nihai.get("firma_adi"),
                "donem": nihai.get("rapor_donemi"),
                "karar": nihai.get("karar_egilimi"),
                "risk_sayisi": len(nihai.get("tespit_edilen_riskler", [])),
                "qa_bayrak": len(nihai.get("qa_bayraklari", [])),
                "sure_sn": maliyet.get("toplam_sure_sn"),
                "usd": maliyet.get("tahmini_usd"),
                "modeller": secili_modeller or varsayilan_modeller,
            })
    finally:
        if ctx is not None:
            ctx.__exit__(None, None, None)

    ReportWriter.save_portfolio_summary(kok, ozet)
    return ozet
