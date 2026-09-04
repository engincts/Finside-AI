"""BDRRiskAnalysisReport → Markdown. Hem tek-model (analyzer) hem pipeline kullanır."""

from typing import List, Optional, Dict
from collections import Counter

from finside.models import BDRRiskAnalysisReport, RiskDerecesi

_DERECE_ROZET = {
    RiskDerecesi.DUSUK: "🟢 Düşük",
    RiskDerecesi.ORTA: "🟡 Orta",
    RiskDerecesi.YUKSEK: "🔴 Yüksek",
    RiskDerecesi.KRITIK: "🔥 Kritik",
}


def _varsayilan_ust_satirlar(report: BDRRiskAnalysisReport) -> List[str]:
    return [
        f"- **Analiz Modeli / Motor:** `{report.kullanilan_model or 'Belirtilmemiş'}`",
        f"- **Analiz Süresi:** `{report.analiz_suresi_saniye} saniye`",
        f"- **Firma Adı:** **{report.firma_adi}**",
        f"- **Rapor Dönemi:** `{report.rapor_donemi}`",
        f"- **Bağımsız Denetim Firması:** `{report.denetim_firmasi or 'Belirtilmemiş'}`",
        f"- **Denetçi Görüş Türü:** `{report.denetci_gorusu.value if report.denetci_gorusu else 'Belirtilmemiş'}`",
        f"- **Kredi Komite Karar Eğilimi:** **`{report.karar_egilimi.value}`**",
    ]


def report_to_markdown(
    report: BDRRiskAnalysisReport,
    *,
    ust_satirlar: Optional[List[str]] = None,
    pipeline_izi: Optional[dict] = None,
) -> str:
    lines: List[str] = ["# 🏦 BDR Kurumsal Kredi Risk & Komite Değerlendirme Raporu"]

    if report.is_mock_fallback:
        lines += [
            "",
            "> [!WARNING]",
            "> **MOCK FALLBACK UYARISI**: Bu raporun bir kısmı API hatası veya simülasyon "
            "nedeniyle mock fallback olarak üretilmiştir.",
            f"> **Neden:** `{report.fallback_reason or 'API çağrı hatası'}`",
        ]

    lines += [
        "",
        "## 📋 Rapor Künyesi ve Genel Bilgiler",
        *(ust_satirlar or _varsayilan_ust_satirlar(report))
    ]

    if report.qa_bayraklari:
        lines += ["", "---", "## 🚩 Tutarlılık ve Kalite Kontrol (QA) Uayrıları"]
        lines += [f"- ⚠️ {b}" for b in report.qa_bayraklari]

    # Risk Dağılım Metrikleri Özeti
    yuksek_sayi = sum(1 for r in report.tespit_edilen_riskler if r.risk_derecesi in (RiskDerecesi.YUKSEK, RiskDerecesi.KRITIK))
    orta_sayi = sum(1 for r in report.tespit_edilen_riskler if r.risk_derecesi == RiskDerecesi.ORTA)
    dusuk_sayi = sum(1 for r in report.tespit_edilen_riskler if r.risk_derecesi == RiskDerecesi.DUSUK)

    lines += [
        "",
        "---",
        "## 📊 Risk Dağılım Paneli",
        f"| Toplam Risk Kalemi | 🔴 Yüksek/Kritik Risk | 🟡 Orta Risk | 🟢 Düşük Risk |",
        f"| :---: | :---: | :---: | :---: |",
        f"| **{len(report.tespit_edilen_riskler)} Kalem** | **{yuksek_sayi} Kalem** | **{orta_sayi} Kalem** | **{dusuk_sayi} Kalem** |",
    ]

    lines += [
        "",
        "---",
        "## 📌 1. Genel Kredi Risk Özeti",
        f"> {report.genel_kredi_risk_ozeti}",
        "",
        "---",
        f"## ⚠️ 2. Tespit Edilen Kalitatif Risk Kalemleri Detayı ({len(report.tespit_edilen_riskler)})",
        "",
    ]

    for idx, risk in enumerate(report.tespit_edilen_riskler, 1):
        rozet = _DERECE_ROZET.get(risk.risk_derecesi, risk.risk_derecesi.value)
        satirlar = [
            f"### {idx}. {risk.baslik}",
            f"- **Kategori:** `{risk.risk_kategorisi.value}`",
            f"- **Dipnot Referansı:** `{risk.dipnot_referansi or 'BDR Genel Metin'}`",
            f"- **Risk Derecesi:** {rozet}",
            f"- **Finansal Tutar / Büyüklük:** `{risk.tutar_bilgisi or 'Metinde Tutarsız/Belirtilmemiş'}`",
            f"- **Risk Detayı:** {risk.detay}",
            f"- **Kredi Risk Etkisi:** **{risk.etki_degerlendirmesi}**",
            "",
            "> 💬 **BDR Birebir Alıntısı:**",
            f"> *\"{risk.kaynak_metin_alintisi}\"*",
        ]
        if risk.dogrulanmadi:
            satirlar.append("- ⚠️ **Kaynak alıntısı ham metinde doğrulanamadı.**")
        if risk.kaynak_modeller:
            satirlar.append(f"- 🤖 **Tespit Eden Modeller:** `{', '.join(risk.kaynak_modeller)}`")
        lines += [*satirlar, "", "---"]

    lines += [
        "## 📋 3. Kredi Komitesi İçin Aksiyon & Kısıtlayıcı Şart Önerileri (Covenants)",
    ]
    if report.komite_tavsiyesi_ve_sartlar:
        lines += [f"- [ ] {s}" for s in report.komite_tavsiyesi_ve_sartlar]
    else:
        lines += ["- (Spesifik taahhüt şartı önerilmemiştir)"]

    lines += [
        "",
        "---",
        "## 📝 4. Kıdemli Analist Gerekçelendirme Metni",
        report.analist_gerekce_metni
    ]

    if pipeline_izi:
        lines += [
            "",
            "---",
            "## ⏱️ Multi-Agent Pipeline İşlem Metrikleri",
            f"- **Toplam LLM Çağrısı:** `{pipeline_izi.get('toplam_llm_cagrisi')}` (Başarısız: `{pipeline_izi.get('basarisiz_cagri')}`)",
            f"- **Aşama Kırılımı:** `{pipeline_izi.get('asama_kirilimi')}`",
            f"- **Tahmini Token Kullanımı:** `{pipeline_izi.get('tahmini_girdi_token')}` girdi / `{pipeline_izi.get('tahmini_cikti_token')}` çıktı",
            f"- **Toplam Analiz Süresi:** `{pipeline_izi.get('toplam_sure_sn')}` saniye",
            f"- **Tahmini İşlem Maliyeti:** `${pipeline_izi.get('tahmini_usd')}`",
        ]

    return "\n".join(lines)
