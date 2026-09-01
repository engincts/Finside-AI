from typing import Dict, Any
from finside.providers.base import BaseProvider
from prompts.schemas import BDRRiskAnalysisReport


class MockProvider(BaseProvider):
    """Sıfır maliyetli offline test & simülasyon sağlayıcısı."""

    def analyze(self, user_prompt: str) -> BDRRiskAnalysisReport:
        return self.generate_mock_report(user_prompt, is_fallback=False)
