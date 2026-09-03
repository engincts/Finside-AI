import time
from typing import Dict, Any
from finside.providers.base import BaseProvider
from finside.models import BDRRiskAnalysisReport

try:
    from google import genai
    from google.genai import types as genai_types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

_RATE_LIMIT_DENEME = 2
_RATE_LIMIT_BEKLEME_SN = 8


class GeminiProvider(BaseProvider):
    """Google Gemini API entegrasyon sağlayıcısı (Google GenAI Chat SDK Uyumlu)."""

    @staticmethod
    def _rate_limited(err: Exception) -> bool:
        s = str(err)
        return "429" in s or "RESOURCE_EXHAUSTED" in s

    def analyze(self, user_prompt: str) -> BDRRiskAnalysisReport:
        if not self.api_key:
            raise RuntimeError(f"❌ GEMINI_API_KEY eksik ({self.model_name}). Lütfen .env dosyanızı veya API anahtarınızı kontrol edin.")
        if not HAS_GENAI:
            raise RuntimeError("❌ google-genai paketi yüklü değil. Lütfen `pip install google-genai` çalıştırın.")

        client = genai.Client(api_key=self.api_key)
        config_kwargs = {
            "system_instruction": self.system_prompt,
            "response_mime_type": "application/json",
            "response_schema": BDRRiskAnalysisReport,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_output_tokens": self.max_tokens,
        }

        if hasattr(genai_types, "ThinkingConfig"):
            effort_str = str(self.reasoning_effort).lower()
            budget_map = {"low": 2048, "medium": 4096, "high": 8192, "auto": 4096}
            budget = budget_map.get(effort_str, 4096) if isinstance(self.reasoning_effort, str) else self.reasoning_effort
            config_kwargs["thinking_config"] = genai_types.ThinkingConfig(thinking_budget=budget)

        gen_config = genai_types.GenerateContentConfig(**config_kwargs)

        response = None
        for deneme in range(_RATE_LIMIT_DENEME):
            try:
                try:
                    chat = client.chats.create(model=self.model_name, config=gen_config)
                    response = chat.send_message(user_prompt)
                except Exception:
                    response = client.models.generate_content(
                        model=self.model_name,
                        contents=user_prompt,
                        config=gen_config
                    )
                break
            except Exception as e:
                if self._rate_limited(e) and deneme + 1 < _RATE_LIMIT_DENEME:
                    time.sleep(_RATE_LIMIT_BEKLEME_SN)
                    continue
                raise RuntimeError(f"❌ Gemini API Hatası ({self.model_name}): {e}")

        raw_text = response.text if hasattr(response, "text") and response.text else "{}"
        report = self._parse_report(raw_text)
        report.is_mock_fallback = False
        return report

    def raw_generate(self, user_prompt: str, *, json_mode: bool = False) -> str:
        if not self.api_key:
            raise RuntimeError(f"Gemini raw_generate: GEMINI_API_KEY yok ({self.model_name}).")
        if not HAS_GENAI:
            raise RuntimeError("Gemini raw_generate: google-genai paketi yüklü değil.")

        client = genai.Client(api_key=self.api_key)
        cfg_kwargs = {
            "system_instruction": self.system_prompt,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_output_tokens": self.max_tokens,
        }
        if json_mode:
            cfg_kwargs["response_mime_type"] = "application/json"

        response = client.models.generate_content(
            model=self.model_name,
            contents=user_prompt,
            config=genai_types.GenerateContentConfig(**cfg_kwargs),
        )
        return response.text if getattr(response, "text", None) else ""
