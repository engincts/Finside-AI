"""Eval orkestrasyonu: bir raporu 3 katmanda değerlendirir, sonucu diske yazar.

Katman 1 her zaman çalışır (offline). Katman 2 yalnızca `hakem_modelleri` verilince,
Katman 3 yalnızca `gold/<stem>.json` mevcutsa çalışır.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config import Config
from finside.eval import gold as gold_mod
from finside.eval.judge import hakem_degerlendir
from finside.eval.metrics import katman1_metrikleri

EVAL_DIR = Config.BASE_DIR / "eval"


@dataclass
class EvalSonucu:
    bdr_stem: str
    config_adi: str
    tarih: str
    katman1: Dict[str, Any]
    katman2: Optional[Dict[str, Any]] = None
    katman3: Optional[Dict[str, Any]] = None

    @property
    def taban_puan(self) -> float:
        return self.katman1.get("taban_puan", 0.0)


def _segment_sayisi(rapor_yolu: Path) -> int:
    seg = rapor_yolu.parent / "segments.json"
    if not seg.exists():
        return 0
    try:
        return len(json.loads(seg.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        return 0


def _yaz_sonuc(sonuc: EvalSonucu) -> None:
    hedef = EVAL_DIR / sonuc.config_adi
    hedef.mkdir(parents=True, exist_ok=True)
    (hedef / f"{sonuc.bdr_stem}.json").write_text(
        json.dumps(asdict(sonuc), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def degerlendir(
    rapor_yolu: Path,
    bdr_yolu: Path,
    *,
    config_adi: str,
    hakem_modelleri: Optional[List[str]] = None,
    gold_kullan: bool = True,
    yaz: Optional[Callable[[str], None]] = None,
) -> EvalSonucu:
    rapor = json.loads(rapor_yolu.read_text(encoding="utf-8"))
    bdr_metni = bdr_yolu.read_text(encoding="utf-8")
    stem = bdr_yolu.stem

    if yaz:
        yaz(f"• {stem}  ({config_adi})")

    katman1 = katman1_metrikleri(rapor, bdr_metni, _segment_sayisi(rapor_yolu))
    if yaz:
        yaz(
            f"  katman1 → taban {katman1['taban_puan']} · "
            f"grounding {katman1['grounding']['grounding_orani']} · "
            f"jenerik etki {katman1['kapsam']['jenerik_etki_orani']} · "
            f"QA {katman1['sema']['qa_bayrak_sayisi']}"
        )

    katman2 = None
    if hakem_modelleri:
        katman2 = hakem_degerlendir(bdr_metni, rapor, hakem_modelleri, yaz)
        if yaz:
            yaz(
                f"  katman2 → ortalama {katman2['ortalama_puan']} · "
                f"kaçırılan {len(katman2['kacirilan_riskler'])} · "
                f"hatalı {len(katman2['hatali_riskler'])}"
            )

    katman3 = None
    if gold_kullan:
        gold = gold_mod.yukle(stem)
        if gold:
            katman3 = gold_mod.skorla(rapor, gold)
            if yaz:
                yaz(
                    f"  katman3 → recall {katman3['recall']} · "
                    f"kaçırılan {len(katman3['kacirilan_riskler'])} · "
                    f"karar isabeti {katman3['karar_isabeti']}"
                )
        elif yaz:
            yaz("  katman3 → gold dosyası yok, atlandı")

    sonuc = EvalSonucu(
        bdr_stem=stem,
        config_adi=config_adi,
        tarih=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        katman1=katman1,
        katman2=katman2,
        katman3=katman3,
    )
    _yaz_sonuc(sonuc)
    return sonuc


def _bdr_bul(stem: str) -> Optional[Path]:
    aday = Config.DATA_DIR / f"{stem}.txt"
    return aday if aday.exists() else None


def degerlendir_klasor(
    cikti_kok: Path,
    *,
    config_adi: str,
    hakem_modelleri: Optional[List[str]] = None,
    gold_kullan: bool = True,
    yaz: Optional[Callable[[str], None]] = None,
) -> List[EvalSonucu]:
    raporlar = sorted(cikti_kok.rglob("final_report.json"))
    if not raporlar:
        raporlar = sorted(cikti_kok.rglob("nihai_rapor.json"))

    sonuclar: List[EvalSonucu] = []
    for rapor_yolu in raporlar:
        stem = rapor_yolu.parent.name
        bdr = _bdr_bul(stem)
        if not bdr:
            if yaz:
                yaz(f"⚠ {stem}: kaynak BDR bulunamadı ({Config.DATA_DIR}/), atlandı")
            continue
        sonuclar.append(degerlendir(
            rapor_yolu, bdr,
            config_adi=config_adi,
            hakem_modelleri=hakem_modelleri,
            gold_kullan=gold_kullan,
            yaz=yaz,
        ))

    if sonuclar:
        from finside.eval.karsilastir import ozet_yaz

        ozet_yaz(sonuclar, EVAL_DIR / config_adi / "ozet.md")
    return sonuclar
