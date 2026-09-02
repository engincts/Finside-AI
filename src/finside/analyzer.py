import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional

from config import Config
from finside.chunking import build_chunks
from finside.dedupe import uncovered_risks
from finside.loaders import PromptLoader
from finside.providers import ProviderFactory
from finside.report_md import report_to_markdown
from prompts.schemas import BDRRiskAnalysisReport, BDRRiskItem

EMBED_API_KEY_ENV = "OPENAI_API_KEY"

DEFAULT_MAX_INPUT_CHARS = 150_000
PROVIDER_INPUT_LIMITS = {
    "huggingface": 90_000,
    "openai": 200_000,
    "anthropic": 200_000,
    "gemini": 200_000,
    "mock": 5_000_000,
}
CHUNK_UTILIZATION = 0.9
MAX_CHUNK_WORKERS = 4
TRUNCATE_MAX_CHARS = 60_000  # kıyas modunda: bir modeli değerlendirmek için yeterli dilim

CHUNK_INSTRUCTION = (
    "[BDR PARÇA {idx}/{total}] Aşağıdaki metin, daha büyük bir Bağımsız Denetim Raporunun "
    "yalnızca bir bölümüdür. SADECE bu bölümde açıkça yer alan kalitatif kredi risklerini çıkar. "
    "Bu bölümde risk yoksa 'tespit_edilen_riskler' listesini boş bırak. Firma, dönem ve denetçi "
    "bilgisini metnin künye kısmından doldur.\n\n{body}"
)

SYNTHESIS_INSTRUCTION = (
    "[SENTEZ GÖREVİ] Aşağıda AYNI Bağımsız Denetim Raporunun farklı bölümlerinden çıkarılmış "
    "kısmi risk analizleri (JSON) yer alıyor. Bunları tek, tutarlı ve tekrarsız bir kredi "
    "komitesi raporunda birleştir. Genel kredi risk özetini, karar eğilimini ve analist gerekçe "
    "metnini tüm riskleri birlikte değerlendirerek yeniden yaz; borç ödeme kapasitesi, likidite "
    "ve teminat yapısı açısından derin bir analist yorumu üret.\n\n{body}"
)

_SYNTH_EXCLUDE = {"analiz_suresi_saniye", "kullanilan_model", "is_mock_fallback", "fallback_reason"}


class BDRAnalyzer:
    """SOLID Orchestrator: BDR risk analizi ve LLM provider orkestrasyon sınıfı."""

    def __init__(
        self,
        model_config: Optional[Dict[str, Any]] = None,
        custom_system_prompt: Optional[str] = None,
        custom_user_template: Optional[str] = None,
        buyuk_girdi_stratejisi: str = "map_reduce",
    ):
        # "map_reduce": yapı-farkında chunking + sentez (tam analiz, yavaş)
        # "truncate": limit kadar kes, tek çağrı (model kıyaslama / hızlı)
        self.buyuk_girdi_stratejisi = buyuk_girdi_stratejisi
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
        self.max_input_chars = int(
            self.model_config.get("max_input_chars")
            or PROVIDER_INPUT_LIMITS.get(self.provider_name, DEFAULT_MAX_INPUT_CHARS)
        )

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
        start_time = time.perf_counter()
        ad = self.model_config.get("name", self.model_name)

        if self.buyuk_girdi_stratejisi == "truncate":
            kes = min(self.max_input_chars, TRUNCATE_MAX_CHARS)
            if len(bdr_text) <= kes:
                report = self._run_provider(bdr_text)
                report.kullanilan_model = ad
            else:
                report = self._run_provider(bdr_text[:kes])
                report.kullanilan_model = f"{ad} (ilk {kes:,} karakter — kıyas modu)"
        elif len(bdr_text) <= self.max_input_chars:
            report = self._run_provider(bdr_text)
            report.kullanilan_model = ad
        else:
            report = self._analyze_chunked(bdr_text)

        report.analiz_suresi_saniye = round(time.perf_counter() - start_time, 3)
        return report

    def _run_provider(self, bdr_text: str) -> BDRRiskAnalysisReport:
        # Strategy Pattern: Sağlayıcıya dinamik prompt ile delegasyon
        return self.provider.analyze(self.user_template.format(bdr_text=bdr_text))

    def _analyze_chunked(self, bdr_text: str) -> BDRRiskAnalysisReport:
        chunks = build_chunks(bdr_text, int(self.max_input_chars * CHUNK_UTILIZATION))
        total = len(chunks)
        tasks = [
            CHUNK_INSTRUCTION.format(idx=i + 1, total=total, body=chunk)
            for i, chunk in enumerate(chunks)
        ]
        with ThreadPoolExecutor(max_workers=min(total, MAX_CHUNK_WORKERS)) as executor:
            partials = list(executor.map(self._run_provider, tasks))

        valid = [p for p in partials if not p.is_mock_fallback]
        if not valid:
            return partials[0]

        merged_risks = self._dedupe_risks(
            [risk for p in valid for risk in p.tespit_edilen_riskler]
        )
        merged_terms = list(dict.fromkeys(
            term for p in valid for term in p.komite_tavsiyesi_ve_sartlar
        ))

        report = self._synthesize(valid, merged_risks, merged_terms)
        report.is_mock_fallback = False
        report.fallback_reason = None
        report.kullanilan_model = f"{self.model_config.get('name', self.model_name)} (Yapısal Chunk: {total} bölüm)"
        return report

    def _synthesize(
        self,
        partials: List[BDRRiskAnalysisReport],
        merged_risks: List[BDRRiskItem],
        merged_terms: List[str],
    ) -> BDRRiskAnalysisReport:
        combined = "\n\n".join(
            p.model_dump_json(exclude=_SYNTH_EXCLUDE, exclude_none=True) for p in partials
        )
        try:
            synth = self._run_provider(SYNTHESIS_INSTRUCTION.format(body=combined))
            if not synth.is_mock_fallback:
                consolidated = synth.tespit_edilen_riskler
                recovered = uncovered_risks(
                    merged_risks, consolidated, api_key=os.getenv(EMBED_API_KEY_ENV)
                )
                synth.tespit_edilen_riskler = consolidated + recovered
                synth.komite_tavsiyesi_ve_sartlar = synth.komite_tavsiyesi_ve_sartlar or merged_terms
                return synth
        except Exception:
            pass

        base = partials[0]
        base.tespit_edilen_riskler = merged_risks
        base.komite_tavsiyesi_ve_sartlar = merged_terms or base.komite_tavsiyesi_ve_sartlar
        return base

    @staticmethod
    def _dedupe_risks(risks: List[BDRRiskItem]) -> List[BDRRiskItem]:
        seen: Dict[str, BDRRiskItem] = {}
        for risk in risks:
            key = risk.baslik.strip().lower()
            seen.setdefault(key, risk)
        return list(seen.values())

    def format_report_as_markdown(self, report: BDRRiskAnalysisReport) -> str:
        ust = [
            f"**Model:** `{report.kullanilan_model}` (Prompt: `{self.prompt_file}`, "
            f"Reasoning: `{self.model_config.get('reasoning_effort', 'medium')}`, "
            f"Temp: `{self.model_config.get('temperature', 0.1)}`, "
            f"Top-p: `{self.model_config.get('top_p', 0.9)}`)",
            f"**Analiz Süresi:** `{report.analiz_suresi_saniye} saniye`",
            f"**Firma Adı:** {report.firma_adi}",
            f"**Rapor Dönemi:** {report.rapor_donemi}",
            f"**Bağımsız Denetim Firması:** {report.denetim_firmasi or 'Belirtilmemiş'}",
            f"**Denetçi Görüşü:** `{report.denetci_gorusu.value if report.denetci_gorusu else 'Belirtilmemiş'}`",
            f"**Genel Karar Eğilimi:** `{report.karar_egilimi.value}`",
        ]
        return report_to_markdown(report, ust_satirlar=ust)
