"""BDRRiskAnalysisReport → Markdown. Hem tek-model (analyzer) hem pipeline kullanır."""

from typing import List, Optional

from finside.models import BDRRiskAnalysisReport, RiskDerecesi

_DERECE_ROZET = {
    RiskDerecesi.DUSUK: "🟢 Düşük",
    RiskDerecesi.ORTA: "🟡 Orta",
    RiskDerecesi.YUKSEK: "🔴 Yüksek",
    RiskDerecesi.KRITIK: "🔥 Kritik",
}


def _varsayilan_ust_satirlar(report: BDRRiskAnalysisReport) -> List[str]:
    return [
        f"**Model:** `{report.kullanilan_model or 'Belirtilmemiş'}`",
        f"**Analiz Süresi:** `{report.analiz_suresi_saniye} saniye`",
        f"**Firma Adı:** {report.firma_adi}",
        f"**Rapor Dönemi:** {report.rapor_donemi}",
        f"**Bağımsız Denetim Firması:** {report.denetim_firmasi or 'Belirtilmemiş'}",
        f"**Denetçi Görüşü:** `{report.denetci_gorusu.value if report.denetci_gorusu else 'Belirtilmemiş'}`",
        f"**Genel Karar Eğilimi:** `{report.karar_egilimi.value}`",
    ]


def report_to_markdown(
    report: BDRRiskAnalysisReport,
    *,
    ust_satirlar: Optional[List[str]] = None,
    pipeline_izi: Optional[dict] = None,
) -> str:
    lines: List[str] = ["# 📊 BDR Kredi Komitesi Risk Değerlendirme Raporu"]

    if report.is_mock_fallback:
        lines += [
            "",
            "> [!WARNING]",
            "> **MOCK FALLBACK UYARISI**: Bu raporun bir kısmı API hatası nedeniyle mock "
            "simülasyona düşmüştür — genel özet, karar ve gerekçe güvenilir olmayabilir.",
            f"> **Neden:** `{report.fallback_reason or 'API çağrı hatası'}`",
        ]

    lines += ["", *(ust_satirlar or _varsayilan_ust_satirlar(report))]

    if report.qa_bayraklari:
        lines += ["", "---", "## 🚩 Tutarlılık Uyarıları (QA)"]
        lines += [f"- ⚠️ {b}" for b in report.qa_bayraklari]

    lines += [
        "",
        "---",
        "## 📌 1. Genel Kredi Risk Özeti",
        report.genel_kredi_risk_ozeti,
        "",
        "---",
        f"## ⚠️ 2. Tespit Edilen Kalitatif Risk Kalemleri ({len(report.tespit_edilen_riskler)})",
        "",
    ]

    for idx, risk in enumerate(report.tespit_edilen_riskler, 1):
        rozet = _DERECE_ROZET.get(risk.risk_derecesi, risk.risk_derecesi.value)
        satirlar = [
            f"### {idx}. {risk.baslik}",
            f"- **Kategori:** `{risk.risk_kategorisi.value}`",
            f"- **Dipnot Referansı:** `{risk.dipnot_referansi or 'BDR Genel'}`",
            f"- **Risk Derecesi:** {rozet}",
            f"- **Tutar:** {risk.tutar_bilgisi or 'Belirtilmemiş'}",
            f"- **Detay:** {risk.detay}",
            f"- **Kredi Etkisi:** {risk.etki_degerlendirmesi}",
            f"- **BDR Alıntısı:** *\"{risk.kaynak_metin_alintisi}\"*",
        ]
        if risk.dogrulanmadi:
            satirlar.append("- ⚠️ **Kaynak alıntısı ham metinde doğrulanamadı.**")
        if risk.kaynak_modeller:
            satirlar.append(f"- **Bulan:** `{', '.join(risk.kaynak_modeller)}`")
        lines += [*satirlar, ""]

    lines += ["---", "## 📋 3. Kredi Komitesi Tavsiyeleri & Şartlar"]
    lines += [f"- [ ] {s}" for s in report.komite_tavsiyesi_ve_sartlar] or ["- (öneri yok)"]

    lines += ["", "---", "## 📝 4. Analist Gerekçelendirme Metni", report.analist_gerekce_metni]

    if pipeline_izi:
        lines += [
            "",
            "---",
            "## ⏱️ Pipeline İzi",
            f"- Toplam LLM çağrısı: `{pipeline_izi.get('toplam_llm_cagrisi')}` "
            f"(başarısız: `{pipeline_izi.get('basarisiz_cagri')}`)",
            f"- Aşama kırılımı: `{pipeline_izi.get('asama_kirilimi')}`",
            f"- Tahmini token: `{pipeline_izi.get('tahmini_girdi_token')}` girdi / "
            f"`{pipeline_izi.get('tahmini_cikti_token')}` çıktı",
            f"- Toplam süre: `{pipeline_izi.get('toplam_sure_sn')}` sn · "
            f"Tahmini maliyet: `${pipeline_izi.get('tahmini_usd')}`",
        ]

    return "\n".join(lines)
