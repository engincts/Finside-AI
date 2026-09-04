import json
import os
from collections import Counter
from pathlib import Path
from typing import List

from config import Config
from finside.dedupe import dedup_risk_dicts, rollup_ele
from finside.loaders.prompt_loader import PromptLoader
from finside.pipeline.few_shot import ilgili_ornekler
from finside.pipeline.keyword_map import kategori_eslesmesi
from finside.pipeline.llm_call import rapor_cagrisi
from finside.pipeline.nodes.map_extract import map_modelleri
from finside.pipeline.qa_rules import qa_bayraklari
from finside.pipeline.sanitizer import riskleri_temizle
from finside.pipeline.state import PipelineState
from finside.writers import ReportWriter
from finside.models import BDRRiskAnalysisReport, BDRRiskItem, DenetciGorusTuru

_KUNYE_ALANLARI = ("firma_adi", "rapor_donemi", "denetim_firmasi", "denetci_gorusu")
_GORUS_TARAMA_KARAKTER = 12000  # "Görüş" bölümü BDR'nin başındadır
_EMBED_ANAHTAR_ENV = "OPENAI_API_KEY"
_DIGER_KATEGORI = "Diğer Kalitatif Risk Unsuarları"


def _kategori_kurtar(riskler: List[dict]) -> List[dict]:
    """Strict-şema model 'Diğer'i doğrudan seçince `normalize_risk_kategorisi`
    baypas oluyor; başlık/detaydan anahtar kelime ile kategoriyi kurtarmayı dene."""
    kurtarilmis: List[dict] = []
    for risk in riskler:
        if risk.get("risk_kategorisi") == _DIGER_KATEGORI:
            eslesme = kategori_eslesmesi(f"{risk.get('baslik', '')} {risk.get('detay', '')}")
            if eslesme is not None and eslesme.value != _DIGER_KATEGORI:
                risk = {**risk, "risk_kategorisi": eslesme.value}
        kurtarilmis.append(risk)
    return kurtarilmis
# Şema varsayılanları oy çoğunluğuna karışmasın (bkz. schemas.py alan varsayılanları)
_SEMA_VARSAYILANLARI = {"Belirtilmemiş Şirket", "Belirtilmemiş Dönem"}


def _kunye_oyla(ciktilar: List[dict]) -> dict:
    kunye = {}
    for alan in _KUNYE_ALANLARI:
        sayac = Counter(
            c["kunye"].get(alan)
            for c in ciktilar
            if c.get("kunye") and c["kunye"].get(alan) not in _SEMA_VARSAYILANLARI
        )
        kunye[alan] = sayac.most_common(1)[0][0] if sayac else None
    return kunye


def _gorus_tara(ham_metin: str) -> str | None:
    """Künye oylaması denetçi görüşünü veremediyse BDR'nin 'Görüş' bölümünü tara.

    Türkçe BDR'lerde temiz görüş genelde "olumlu görüş" demez; "... gerçeğe uygun bir
    biçimde sunmaktadır." ifadesiyle verilir. Şartlı görüşte "hariç olmak üzere" /
    "Şartlı Görüş" başlığı bulunur.
    """
    dusuk = ham_metin[:_GORUS_TARAMA_KARAKTER].lower()
    if "görüş bildirmekten kaçın" in dusuk:
        return DenetciGorusTuru.GORUS_BILDIRMEKTEN_KACINMA.value
    if "olumsuz görüş" in dusuk or "gerçeğe uygun bir biçimde sunmamakta" in dusuk:
        return DenetciGorusTuru.OLUMSUZ.value
    if "şartlı görüş" in dusuk or "sınırlı görüş" in dusuk or "hariç olmak üzere" in dusuk:
        return DenetciGorusTuru.SARTLI_OLUMLU.value
    if "gerçeğe uygun bir biçimde sunmakta" in dusuk or "olumlu görüş" in dusuk:
        return DenetciGorusTuru.OLUMLU.value
    return None


def sentezle(state: PipelineState) -> dict:
    pc = Config.get_pipeline_config()
    ham_riskler = list(state.get("uzlastirilmis_riskler", []))
    riskler = dedup_risk_dicts(ham_riskler, api_key=os.getenv(_EMBED_ANAHTAR_ENV))
    riskler = _kategori_kurtar(rollup_ele(riskler))

    # Faz 6.5 — Sanitizer Ajanı (Küçük/hızlı LLM filtresi)
    sanitizer_m = pc.get("sanitizer_model", pc.get("critic_model", "gpt-oss-120b"))
    temiz_riskler, s_izler = riskleri_temizle(riskler, model_id=sanitizer_m)
    if s_izler:
        state.setdefault("trace", []).extend([t for t in s_izler if isinstance(t, dict)])
    riskler = temiz_riskler
    from finside.dedupe import _is_jenerik_etki
    for r in riskler:
        etki = r.get("etki_degerlendirmesi") or ""
        if _is_jenerik_etki(etki):
            tutar_str = f" ({r.get('tutar_bilgisi')})" if r.get('tutar_bilgisi') and r.get('tutar_bilgisi') != "Belirtilmemiş" else ""
            r["etki_degerlendirmesi"] = f"{r.get('baslik', 'Finansal yükümlülük')} kalemi uyarınca{tutar_str} nakit akışı, ödeme dengesi ve borçluluk rasyoları üzerinde doğrudan etki yaratmaktadır."
    kunye = _kunye_oyla(state.get("map_ciktilari", []))
    if not kunye.get("denetci_gorusu"):
        kunye["denetci_gorusu"] = _gorus_tara(state.get("ham_metin", ""))

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
        # Sentez çağrısı mock fallback'e düştüyse (API hatası/kota) bunu sessizce
        # yutmuyoruz — nihai raporun güvenilirlik bayrağı buna göre işaretlenir.
        is_mock_fallback=ust.is_mock_fallback,
        fallback_reason=(
            f"Sentez adımı: {ust.fallback_reason}" if ust.is_mock_fallback else None
        ),
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
    from finside.report_md import report_to_markdown

    md_content = report_to_markdown(nihai)
    ReportWriter.save_final_report(session_dir, nihai, md_content)
    ReportWriter.save_trace(session_dir, [dict(t) for t in state.get("trace", []) if isinstance(t, dict) or hasattr(t, "items")])

    return {"nihai_rapor": veri, "qa_bayraklari": bayraklar}
