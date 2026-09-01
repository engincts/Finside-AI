import json
import os
from collections import Counter
from pathlib import Path
from typing import List

from config import Config
from finside.dedupe import dedup_risk_dicts
from finside.loaders.prompt_loader import PromptLoader
from finside.pipeline.few_shot import ilgili_ornekler
from finside.pipeline.llm_call import rapor_cagrisi
from finside.pipeline.nodes.map_extract import map_modelleri
from finside.pipeline.qa_rules import qa_bayraklari
from finside.pipeline.state import PipelineState
from finside.writers import ReportWriter
from prompts.schemas import BDRRiskAnalysisReport, BDRRiskItem

_KUNYE_ALANLARI = ("firma_adi", "rapor_donemi", "denetim_firmasi", "denetci_gorusu")
_EMBED_ANAHTAR_ENV = "OPENAI_API_KEY"


def _kunye_oyla(ciktilar: List[dict]) -> dict:
    kunye = {}
    for alan in _KUNYE_ALANLARI:
        sayac = Counter(
            c["kunye"].get(alan)
            for c in ciktilar
            if c.get("kunye") and c["kunye"].get(alan)
        )
        kunye[alan] = sayac.most_common(1)[0][0] if sayac else None
    return kunye


def sentezle(state: PipelineState) -> dict:
    pc = Config.get_pipeline_config()
    ham_riskler = list(state.get("uzlastirilmis_riskler", []))
    riskler = dedup_risk_dicts(ham_riskler, api_key=os.getenv(_EMBED_ANAHTAR_ENV))
    kunye = _kunye_oyla(state.get("map_ciktilari", []))

    sistem, sablon = PromptLoader.load_prompt_md("synthesis_v1.md")
    user_prompt = sablon.format(
        kunye_json=json.dumps(kunye, ensure_ascii=False),
        riskler_json=json.dumps(riskler, ensure_ascii=False, indent=2),
    )
    ornekler = ilgili_ornekler(riskler)
    if ornekler:
        user_prompt = ornekler + user_prompt

    sonuc = rapor_cagrisi(
        pc["synthesis_model"], user_prompt, asama="faz7-sentez", system_prompt=sistem,
    )
    ust = sonuc.report

    nihai = BDRRiskAnalysisReport(
        kullanilan_model=f"pipeline ({', '.join(map_modelleri(state))})",
        firma_adi=kunye.get("firma_adi") or ust.firma_adi,
        rapor_donemi=kunye.get("rapor_donemi") or ust.rapor_donemi,
        denetim_firmasi=kunye.get("denetim_firmasi") or ust.denetim_firmasi,
        denetci_gorusu=kunye.get("denetci_gorusu") or (ust.denetci_gorusu.value if ust.denetci_gorusu else None),
        tespit_edilen_riskler=[BDRRiskItem.model_validate(r) for r in riskler],
        genel_kredi_risk_ozeti=ust.genel_kredi_risk_ozeti,
        komite_tavsiyesi_ve_sartlar=ust.komite_tavsiyesi_ve_sartlar,
        karar_egilimi=ust.karar_egilimi,
        analist_gerekce_metni=ust.analist_gerekce_metni,
    )
    return {"nihai_rapor": nihai.model_dump(mode="json"), "trace": [sonuc.trace]}


def qa_kontrol(state: PipelineState) -> dict:
    nihai = BDRRiskAnalysisReport.model_validate(state["nihai_rapor"])
    bayraklar = qa_bayraklari(nihai, len(state.get("segmentler", [])))
    nihai.qa_bayraklari = bayraklar
    veri = nihai.model_dump(mode="json")

    session_dir = Path(state["session_dir"])
    ReportWriter.save_json(session_dir, "nihai_rapor.json", veri)
    ReportWriter.save_trace(session_dir, [dict(t) for t in state.get("trace", [])])

    return {"nihai_rapor": veri, "qa_bayraklari": bayraklar}
