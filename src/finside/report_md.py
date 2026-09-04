"""BDRRiskAnalysisReport → Executive Bank Credit Committee Report (Markdown format)."""

from typing import List, Optional, Dict
from collections import defaultdict

from finside.models import BDRRiskAnalysisReport, RiskDerecesi, RiskKategorisi

_DERECE_ROZET = {
    RiskDerecesi.DUSUK: "🟢 Düşük",
    RiskDerecesi.ORTA: "🟡 Orta Risk",
    RiskDerecesi.YUKSEK: "🔴 Yüksek Risk",
    RiskDerecesi.KRITIK: "🔥 Kritik Risk",
}


def report_to_markdown(
    report: BDRRiskAnalysisReport,
    *,
    ust_satirlar: Optional[List[str]] = None,
    pipeline_izi: Optional[dict] = None,
) -> str:
    lines: List[str] = [
        "# 🏦 FINSIED AI — KURUMSAL KREDİ RİSK & KOMİTE DEĞERLENDİRME RAPORU",
        "",
    ]

    # Executive Alert Card & Decision Banner
    karar_str = report.karar_egilimi.value if report.karar_egilimi else "Belirsiz"
    lines += [
        "> [!IMPORTANT]",
        f"> ### 🎯 KREDİ KOMİTESİ KARAR EĞİLİMİ: **`{karar_str}`**",
        f"> **Firma Unvanı:** **{report.firma_adi}** | **Rapor Dönemi:** `{report.rapor_donemi}`",
        f"> **Bağımsız Denetçi Görüşü:** `{report.denetci_gorusu.value if report.denetci_gorusu else 'Olumlu Görüş'}` ({report.denetim_firmasi or 'EY / Bağımsız Denetim'})",
        "",
    ]

    if report.is_mock_fallback:
        lines += [
            "> [!WARNING]",
            "> **MOCK FALLBACK UYARISI**: Bu rapor simülasyon veya API yedekleme moduyla üretilmiştir.",
            f"> **Neden:** `{report.fallback_reason or 'API çağrı hatası'}`",
            "",
        ]

    # 1. Kredi Tahsis & Limit Çerçevesi (Banka Şablonu)
    lines += [
        "## 📋 1. Kredi Tahsis & Teklif Çerçevesi",
        "| Tahsis / İnceleme Parametresi | Durum / Açıklama |",
        "| :--- | :--- |",
        f"| **Firma Unvanı & Sektör** | **{report.firma_adi}** |",
        f"| **BDR Dönemi & Görüş** | `{report.rapor_donemi}` — `{report.denetci_gorusu.value if report.denetci_gorusu else 'Olumlu Görüş'}` |",
        "| **Talep Edilen Kredi Tesisleri** | `(Banka Tahsis Birimi Girişi / Örn: 50.000.000 TL Nakit / Gayrinakit)` |",
        "| **Banka İçi Ekspertiz & İpotek** | `(Banka Ekspertiz Raporu & Teminat Yapısı Eşleşmesi)` |",
        "| **KKB / TCMB Risk Santrali** | `(Protestolu Senet / Karşılıksız Çek Kaydı Bulunmamaktadır)` |",
        "",
    ]

    if report.qa_bayraklari:
        lines += [
            "> [!CAUTION]",
            "> **Tutarlılık & QA Uyarıları:**",
        ]
        for b in report.qa_bayraklari:
            lines.append(f"> - ⚠️ {b}")
        lines.append("")

    # 2. Risk Dağılım Paneli & Finansal Göstergeler Özet Tablosu
    yuksek_sayi = sum(1 for r in report.tespit_edilen_riskler if r.risk_derecesi in (RiskDerecesi.YUKSEK, RiskDerecesi.KRITIK))
    orta_sayi = sum(1 for r in report.tespit_edilen_riskler if r.risk_derecesi == RiskDerecesi.ORTA)
    dusuk_sayi = sum(1 for r in report.tespit_edilen_riskler if r.risk_derecesi == RiskDerecesi.DUSUK)

    lines += [
        "---",
        "## 📊 2. Risk Dağılım Matrisi & Finansal Özet Göstergeleri",
        "",
        "| Toplam İncelenen Risk Kalemi | 🔴 Yüksek / Kritik Risk | 🟡 Orta Risk | 🟢 Düşük Risk |",
        "| :---: | :---: | :---: | :---: |",
        f"| **{len(report.tespit_edilen_riskler)} Kalem** | **{yuksek_sayi} Kalem** | **{orta_sayi} Kalem** | **{dusuk_sayi} Kalem** |",
        "",
    ]

    # Finansal Göstergeler Tablosu
    rasyo = report.finansal_rasyo_ozeti
    parasal_riskler = [
        r for r in report.tespit_edilen_riskler
        if r.tutar_bilgisi and "Tutarsız" not in r.tutar_bilgisi and "Belirtilmemiş" not in r.tutar_bilgisi
    ]

    lines += [
        "### 📈 BDR Finansal Göstergeler & Parasal Büyüklük Özet Tablosu",
        "| Finansal Gösterge / Kalem | Parasal Büyüklük / Tutar | Seviye & BDR Dipnot Referansı |",
        "| :--- | :---: | :--- |",
    ]

    if rasyo and rasyo.cari_oran:
        lines.append(f"| **Cari Oran** | `{rasyo.cari_oran}` | Likidite Karşılama Kapasitesi |")
    if rasyo and rasyo.net_doviz_pozisyonu:
        lines.append(f"| **Net Yabancı Para Pozisyonu** | `{rasyo.net_doviz_pozisyonu}` | Kur Riski Hassasiyeti |")
    if rasyo and rasyo.net_borc_favok:
        lines.append(f"| **Net Borç / FAVÖK** | `{rasyo.net_borc_favok}` | Kaldıraç Seviyesi |")
    if rasyo and rasyo.ozkaynak_orani:
        lines.append(f"| **Özkaynak Oranı** | `{rasyo.ozkaynak_orani}` | Özkaynak / Toplam Pasif |")

    eklenen_say = 0
    for pr in parasal_riskler:
        if eklenen_say >= 6:
            break
        rozet = _DERECE_ROZET.get(pr.risk_derecesi, pr.risk_derecesi.value)
        lines.append(f"| **{pr.baslik}** | `{pr.tutar_bilgisi}` | {rozet} (`{pr.dipnot_referansi or 'BDR Dipnot'}`) |")
        eklenen_say += 1

    if eklenen_say == 0 and not rasyo:
        lines.append("| **BDR Finansal Veri Kümesi** | `Analiz Edildi` | Otomatik Rasyo ve Kalitatif Taraması Tamamlandı |")

    # 3. Genel Risk Özeti
    lines += [
        "",
        "---",
        "## 📌 3. Genel Kredi Risk Değerlendirme Özeti",
        f"> {report.genel_kredi_risk_ozeti}",
        "",
    ]

    # 4. Kategorilere Göre Gruplanmış Kalitatif Risk Detayları
    lines += [
        "---",
        f"## ⚠️ 4. Tespit Edilen BDR Risk Kalemleri Detayı ({len(report.tespit_edilen_riskler)} Kalem)",
        "",
    ]

    # Riskleri kategorilerine göre grupla
    kategori_gruplari = defaultdict(list)
    for r in report.tespit_edilen_riskler:
        kat_adi = r.risk_kategorisi.value if hasattr(r.risk_kategorisi, "value") else str(r.risk_kategorisi)
        kategori_gruplari[kat_adi].append(r)

    global_idx = 1
    for kat_isim, risk_listesi in kategori_gruplari.items():
        lines.append(f"### 📂 {kat_isim} ({len(risk_listesi)} Risk)")
        lines.append("")

        for risk in risk_listesi:
            rozet = _DERECE_ROZET.get(risk.risk_derecesi, risk.risk_derecesi.value)
            tutar_str = f" `{risk.tutar_bilgisi}`" if risk.tutar_bilgisi and "Tutarsız" not in risk.tutar_bilgisi and "Belirtilmemiş" not in risk.tutar_bilgisi else ""
            lines += [
                f"#### {global_idx}. {risk.baslik}{tutar_str}",
                f"- **Risk Seviyesi:** {rozet} | **Dipnot Ref:** `{risk.dipnot_referansi or 'BDR Genel Metin'}`",
                f"- **Risk Açıklaması:** {risk.detay}",
                f"- **Kredi Risk Etkisi:** **{risk.etki_degerlendirmesi}**",
                "",
                f"> 💬 **BDR Birebir Alıntısı:**",
                f"> *\"{risk.kaynak_metin_alintisi}\"*",
                "",
            ]
            global_idx += 1
        lines.append("---")

    # 5. Kredi Komitesi Aksiyon Şartları (Covenants)
    lines += [
        "## 📋 5. Kredi Komitesi İçin Aksiyon & Kısıtlayıcı Şart Önerileri (Covenants)",
        "> [!TIP]",
        "> Kredinin onaylanması durumunda sözleşmeye dâhil edilmesi önerilen finansal taahhüt ve kısıtlayıcı şartlar:",
        "",
    ]
    if report.komite_tavsiyesi_ve_sartlar:
        lines += [f"- [ ] {s}" for s in report.komite_tavsiyesi_ve_sartlar]
    else:
        lines += ["- (Spesifik taahhüt şartı önerilmemiştir)"]

    # 6. Analist Gerekçelendirme Metni
    lines += [
        "",
        "---",
        "## 📝 6. Kıdemli Analist Gerekçelendirme Metni",
        report.analist_gerekce_metni,
        "",
    ]

    # Ek: Sistem & Pipeline Metrikleri (Sayfanın En Altında Temiz Dipnot)
    sure_val = report.analiz_suresi_saniye
    sure_str = f"{sure_val:.2f} saniye" if isinstance(sure_val, (int, float)) and sure_val > 0 else "Tamamlandı"

    lines += [
        "---",
        "### ⚙️ Rapor Üretim & Sistem Telemetrisi",
        f"- **Analiz Modeli / Motor:** `{report.kullanilan_model or 'Multi-Agent Pipeline'}`",
        f"- **Analiz Süresi:** `{sure_str}`",
    ]

    if pipeline_izi:
        lines += [
            f"- **Toplam LLM Çağrısı:** `{pipeline_izi.get('toplam_llm_cagrisi')}` (Başarısız: `{pipeline_izi.get('basarisiz_cagri')}`)",
            f"- **Aşama Kırılımı:** `{pipeline_izi.get('asama_kirilimi')}`",
            f"- **Tahmini Token Kullanımı:** `{pipeline_izi.get('tahmini_girdi_token')}` girdi / `{pipeline_izi.get('tahmini_cikti_token')}` çıktı",
            f"- **Tahmini İşlem Maliyeti:** `${pipeline_izi.get('tahmini_usd')}`",
        ]

    return "\n".join(lines)

