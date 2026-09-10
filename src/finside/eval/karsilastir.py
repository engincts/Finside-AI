"""Eval sonuçlarını tek markdown kıyas tablosuna indirger."""

from pathlib import Path
from typing import Dict, List

from finside.eval.runner import EvalSonucu


def _hucre(deger) -> str:
    return "-" if deger is None else str(deger)


def _satir(sonuc: EvalSonucu) -> str:
    k1 = sonuc.katman1
    k2 = (sonuc.katman2 or {}).get("ortalama_puan") or {}
    k3 = sonuc.katman3 or {}
    return (
        f"| {sonuc.bdr_stem[:14]} | {sonuc.config_adi} | {k1['taban_puan']} | "
        f"{k1['grounding']['grounding_orani']} | {k1['sayisal']['sayisal_tutarlilik_orani']} | "
        f"{k1['kapsam']['kategori_kapsam_orani']} | {k1['kapsam']['jenerik_etki_orani']} | "
        f"{k1['sema']['qa_bayrak_sayisi']} | "
        f"{_hucre(k2.get('recall_puani'))} | {_hucre(k2.get('derinlik_puani'))} | "
        f"{_hucre(k3.get('recall'))} | {_hucre(k3.get('karar_isabeti'))} |"
    )


def _ortalama(sonuclar: List[EvalSonucu], config_adi: str) -> str:
    alt = [s for s in sonuclar if s.config_adi == config_adi]
    taban = round(sum(s.taban_puan for s in alt) / len(alt), 1)
    recaller = [s.katman3["recall"] for s in alt if s.katman3]
    recall_str = f" · gold recall ort. {round(sum(recaller) / len(recaller), 3)}" if recaller else ""
    return f"- **{config_adi}** ({len(alt)} BDR): taban puan ort. **{taban}**{recall_str}"


def ozet_tablo(sonuclar: List[EvalSonucu]) -> str:
    baslik = (
        "| BDR | Config | Taban | Ground | Sayısal | Kat.Kapsam | Jenerik | QA | "
        "Hakem Recall | Hakem Derinlik | Gold Recall | Karar |\n"
        "| :-- | :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: | :-: |"
    )
    satirlar = [baslik] + [_satir(s) for s in sonuclar]

    config_adlari: Dict[str, None] = {s.config_adi: None for s in sonuclar}
    ozet = ["", "## Config Ortalamaları", ""]
    ozet += [_ortalama(sonuclar, ad) for ad in config_adlari]
    return "\n".join(satirlar + ozet)


def ozet_yaz(sonuclar: List[EvalSonucu], hedef: Path) -> None:
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text("# Eval Özeti\n\n" + ozet_tablo(sonuclar) + "\n", encoding="utf-8")
