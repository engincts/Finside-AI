from pathlib import Path
from typing import List

from config import Config
from finside.loaders.prompt_loader import PromptLoader
from finside.pipeline.keyword_map import boilerplate_mi, kategori_eslesmesi
from finside.pipeline.llm_call import ham_cagri
from finside.pipeline.state import PipelineState, Segment, SegmentGrubu, TriajKarari
from finside.writers import ReportWriter

_TRIYAJ_ORNEK_KARAKTER = 6000
_GRUP_KATIMI = "\n\n"


def _evet_mi(text: str) -> bool:
    t = text.strip().lower()
    if t.startswith(("hayır", "hayir", "no ", "no,", "hayır.")):
        return False
    return True  # recall-güvenli: belirsizse dahil et


def triyaj_yap(state: PipelineState) -> dict:
    pc = Config.get_pipeline_config()
    segmentler: List[Segment] = state["segmentler"]

    kararlar: List[TriajKarari] = []
    supheli: List[Segment] = []

    for s in segmentler:
        if boilerplate_mi(s["baslik"]):
            kararlar.append(TriajKarari(
                segment_sira_no=s["sira_no"], dahil=False,
                yontem="boilerplate", gerekce="standart açıklama / sunum bölümü",
            ))
            continue
        kategori = kategori_eslesmesi(f"{s['baslik']} {s['ham_metin'][:400]}")
        if kategori is not None:
            kararlar.append(TriajKarari(
                segment_sira_no=s["sira_no"], dahil=True,
                yontem="kural", gerekce=f"kategori: {kategori.value}",
            ))
        else:
            supheli.append(s)

    izler = []
    if supheli:
        sistem, sablon = PromptLoader.load_prompt_md("triage_v1.md")
        for s in supheli:
            sonuc = ham_cagri(
                pc["triage_model"],
                sablon.format(metin=s["ham_metin"][:_TRIYAJ_ORNEK_KARAKTER]),
                asama="faz2-triyaj",
                system_prompt=sistem,
            )
            izler.append(sonuc.trace)
            dahil = _evet_mi(sonuc.text) if sonuc.text else True
            kararlar.append(TriajKarari(
                segment_sira_no=s["sira_no"], dahil=dahil,
                yontem="llm", gerekce=(sonuc.text.strip()[:200] or sonuc.trace["hata"] or ""),
            ))

    kararlar.sort(key=lambda k: k["segment_sira_no"])
    dahil_nolar = [k["segment_sira_no"] for k in kararlar if k["dahil"]]

    ReportWriter.save_json(Path(state["session_dir"]), "triage_log.json", kararlar)

    return {
        "triaj_kararlari": kararlar,
        "analiz_edilecek_sira_nolari": dahil_nolar,
        "trace": izler,
    }


def _grup(grup_id: int, sira_nolari: List[int], metin: str) -> SegmentGrubu:
    return SegmentGrubu(
        grup_id=grup_id,
        segment_sira_nolari=list(sira_nolari),
        birlesik_metin=metin,
        tahmini_token=len(metin) // 4,
    )


def gruplari_olustur(state: PipelineState) -> dict:
    pc = Config.get_pipeline_config()
    butce = int(pc["segment_grup_karakter_butcesi"])
    by_no = {s["sira_no"]: s for s in state["segmentler"]}
    dahil = [by_no[n] for n in state["analiz_edilecek_sira_nolari"] if n in by_no]

    gruplar: List[SegmentGrubu] = []
    cur_metin, cur_nolar = "", []

    for s in dahil:
        parca = s["ham_metin"]
        if len(parca) > butce:
            if cur_nolar:
                gruplar.append(_grup(len(gruplar), cur_nolar, cur_metin))
                cur_metin, cur_nolar = "", []
            for i in range(0, len(parca), butce):
                gruplar.append(_grup(len(gruplar), [s["sira_no"]], parca[i:i + butce]))
            continue
        if cur_metin and len(cur_metin) + len(parca) > butce:
            gruplar.append(_grup(len(gruplar), cur_nolar, cur_metin))
            cur_metin, cur_nolar = "", []
        cur_metin = f"{cur_metin}{_GRUP_KATIMI}{parca}" if cur_metin else parca
        cur_nolar.append(s["sira_no"])

    if cur_nolar:
        gruplar.append(_grup(len(gruplar), cur_nolar, cur_metin))

    return {"segment_gruplari": gruplar}
