import time
from typing import Dict, Any, Optional

from config import Config
from finside.loaders import PromptLoader
from finside.providers import ProviderFactory
from prompts.schemas import BDRRiskAnalysisReport, RiskDerecesi


class BDRAnalyzer:
    """SOLID Orchestrator: BDR risk analizi ve LLM provider orkestrasyon sınıfı."""

    def __init__(
        self, 
        model_config: Optional[Dict[str, Any]] = None,
        custom_system_prompt: Optional[str] = None,
        custom_user_template: Optional[str] = None
    ):
        if model_config is None:
            enabled = Config.get_enabled_models()
            self.model_config = enabled[0] if enabled else {
                "id": "mock",
                "name": "Mock Modeli",
                "provider": "mock",
                "model_name": "mock-v1"
            }
        else:
            self.model_config = model_config

        self.provider_name = self.model_config.get("provider", "mock")
        self.model_name = self.model_config.get("model_name", "mock")
        self.prompt_file = self.model_config.get("prompt_file", "bdr_analyst_v1.md")
        self.api_key = Config.get_api_key_for_model(self.model_config)

        # Markdown Prompt Yükleyici (PromptLoader) veya Dinamik Prompt Overrides
        default_sys, default_usr = PromptLoader.load_prompt_md(self.prompt_file)
        self.system_prompt = custom_system_prompt if custom_system_prompt is not None else default_sys
        self.user_template = custom_user_template if custom_user_template is not None else default_usr

        # Provider Factory üzerinden ilgili LLM sağlayıcısının (Strategy) oluşturulması
        self.provider = ProviderFactory.create_provider(
            provider_name=self.provider_name,
            model_config=self.model_config,
            system_prompt=self.system_prompt,
            api_key=self.api_key
        )

    def analyze(self, bdr_text: str) -> BDRRiskAnalysisReport:
        user_prompt = self.user_template.format(bdr_text=bdr_text)
        start_time = time.perf_counter()

        # Strategy Pattern: Sağlayıcıya dinamik prompt ile delegasyon
        report = self.provider.analyze(user_prompt)

        elapsed = round(time.perf_counter() - start_time, 3)
        report.analiz_suresi_saniye = elapsed
        report.kullanilan_model = self.model_config.get("name", self.model_name)
        return report

    def format_report_as_markdown(self, report: BDRRiskAnalysisReport) -> str:
        lines = [
            "# 📊 BDR Kredi Komitesi Risk Değerlendirme Raporu"
        ]

        if report.is_mock_fallback:
            lines.extend([
                "> [!WARNING]",
                "> **MOCK FALLBACK UYARISI**: Bu rapor gerçek model API çağrısı sırasında hata alındığı için otomatik mock simülasyona düşmüştür.",
                f"> **Hata Nedeni:** `{report.fallback_reason or 'API Çağrı Hatası'}`",
                ""
            ])

        lines.extend([
            f"**Model:** `{report.kullanilan_model}` (Prompt: `{self.prompt_file}`, Reasoning: `{self.model_config.get('reasoning_effort', 'medium')}`, Temp: `{self.model_config.get('temperature', 0.1)}`, Top-p: `{self.model_config.get('top_p', 0.9)}`)",
            f"**Analiz Süresi:** `{report.analiz_suresi_saniye} saniye`",
            f"**Firma Adı:** {report.firma_adi}",
            f"**Rapor Dönemi:** {report.rapor_donemi}",
            f"**Bağımsız Denetim Firması:** {report.denetim_firmasi or 'Belirtilmemiş'}",
            f"**Denetçi Görüşü:** `{report.denetci_gorusu.value if report.denetci_gorusu else 'Belirtilmemiş'}`",
            f"**Genel Karar Eğilimi:** `{report.karar_egilimi.value}`",
            "",
            "---",
            "## 📌 1. Genel Kredi Risk Özeti",
            report.genel_kredi_risk_ozeti,
            "",
            "---",
            "## ⚠️ 2. Tespit Edilen Kalitatif Risk Kalemleri",
            ""
        ])

        for idx, risk in enumerate(report.tespit_edilen_riskler, 1):
            severity = {
                RiskDerecesi.DUSUK: "🟢 Düşük",
                RiskDerecesi.ORTA: "🟡 Orta",
                RiskDerecesi.YUKSEK: "🔴 Yüksek",
                RiskDerecesi.KRITIK: "🔥 Kritik"
            }.get(risk.risk_derecesi, risk.risk_derecesi.value)

            lines.extend([
                f"### {idx}. {risk.baslik}",
                f"- **Kategori:** `{risk.risk_kategorisi.value}`",
                f"- **Dipnot Referansı:** `{risk.dipnot_referansi or 'BDR Genel'}`",
                f"- **Risk Derecesi:** {severity}",
                f"- **Tutar:** {risk.tutar_bilgisi or 'Belirtilmemiş'}",
                f"- **Detay:** {risk.detay}",
                f"- **Kredi Etkisi:** {risk.etki_degerlendirmesi}",
                f"- **BDR Alıntısı:** *\"{risk.kaynak_metin_alintisi}\"*",
                ""
            ])

        lines.extend([
            "---",
            "## 📋 3. Kredi Komitesi Tavsiyeleri & Şartlar",
        ])
        for sart in report.komite_tavsiyesi_ve_sartlar:
            lines.append(f"- [ ] {sart}")

        lines.extend([
            "",
            "---",
            "## 📝 4. Analist Gerekçelendirme Metni",
            report.analist_gerekce_metni
        ])

        return "\n".join(lines)
