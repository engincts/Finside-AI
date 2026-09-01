from typing import Dict, Any
from finside.providers.base import BaseProvider
from prompts.schemas import BDRRiskAnalysisReport


class MockProvider(BaseProvider):
    """Sıfır maliyetli offline test & simülasyon sağlayıcısı."""

    def analyze(self, user_prompt: str) -> BDRRiskAnalysisReport:
        return self.generate_mock_report(user_prompt, is_fallback=False)

    def raw_generate(self, user_prompt: str, *, json_mode: bool = False) -> str:
        low = user_prompt.lower()
        if "evet" in low and ("hayır" in low or "hayir" in low):
            return "EVET | mock varsayılan (recall-güvenli)"
        if json_mode:
            return "[]"
        return "MOCK: gerçek model çıktısı değil."
