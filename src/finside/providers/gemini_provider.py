from typing import Dict, Any
from finside.providers.base import BaseProvider
from prompts.schemas import BDRRiskAnalysisReport

try:
    from google import genai
    from google.genai import types as genai_types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


class GeminiProvider(BaseProvider):
    """Google Gemini API entegrasyon sağlayıcısı (Google GenAI Chat SDK Uyumlu)."""

    def analyze(self, user_prompt: str) -> BDRRiskAnalysisReport:
        if not self.api_key:
            return self.generate_mock_report(user_prompt, is_fallback=True, reason=f"GEMINI_API_KEY bulunamadı ({self.model_name}).")
        if not HAS_GENAI:
            return self.generate_mock_report(user_prompt, is_fallback=True, reason="google-genai paketi yüklü değil.")

        try:
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

            # Google GenAI SDK Tavsiyesi: AFC / Structured Output için Chat.send_message kullanımı
            try:
                chat = client.chats.create(model=self.model_name, config=gen_config)
                response = chat.send_message(user_prompt)
            except Exception:
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=user_prompt,
                    config=gen_config
                )

            raw_text = response.text if hasattr(response, "text") and response.text else "{}"
            report = self._parse_report(raw_text)
            report.is_mock_fallback = False
            return report
        except Exception as e:
            err_msg = f"Gemini API Hata ({self.model_name}): {e}"
            print(f"[HATA] {err_msg}")
            return self.generate_mock_report(user_prompt, is_fallback=True, reason=err_msg)
