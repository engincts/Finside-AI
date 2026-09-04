import os
from finside.providers.base import BaseProvider
from finside.models import BDRRiskAnalysisReport

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class AnthropicProvider(BaseProvider):
    """Anthropic Claude API entegrasyon sağlayıcısı (Forced Tool-Use ile Yapılandırılmış Çıktı)."""

    TOOL_NAME = "bdr_risk_raporu"
    # Claude Sonnet 4.5 native çıktı üst sınırı 64K (beta başlığı gerektirmez). 32K,
    # risk yoğun BDR'lerde tek geçişte yetmiyordu.
    MAX_OUTPUT_TOKENS = 64000

    FALLBACK_CLAUDE_MODELS = [
        "claude-sonnet-4-5",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-5-20251101",
        "claude-sonnet-5"
    ]

    def analyze(self, user_prompt: str) -> BDRRiskAnalysisReport:
        if not self.api_key:
            raise RuntimeError(f"❌ ANTHROPIC_API_KEY eksik ({self.model_name}). Lütfen .env dosyanızı veya API anahtarınızı kontrol edin.")
        if not HAS_ANTHROPIC:
            raise RuntimeError("❌ anthropic paketi yüklü değil. Lütfen `pip install anthropic` çalıştırın.")

        tool = {
            "name": self.TOOL_NAME,
            "description": "BDR metnindeki kalitatif kredi risklerini yapılandırılmış rapor olarak döndürür.",
            "input_schema": BDRRiskAnalysisReport.model_json_schema(),
        }

        client_kwargs = {"api_key": self.api_key.strip()}
        workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
        if workspace_id and workspace_id.strip():
            client_kwargs["default_headers"] = {"anthropic-workspace-id": workspace_id.strip()}

        client = anthropic.Anthropic(**client_kwargs)

        try:
            create_kwargs = {
                "model": self.model_name,
                "max_tokens": min(self.max_tokens, self.MAX_OUTPUT_TOKENS),
                "system": self.system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "tools": [tool],
                "tool_choice": {"type": "tool", "name": self.TOOL_NAME},
            }

            if self.temperature is not None:
                create_kwargs["temperature"] = float(self.temperature)

            try:
                with client.messages.stream(**create_kwargs) as stream:
                    message = stream.get_final_message()
            except TypeError:
                create_kwargs.pop("temperature", None)
                with client.messages.stream(**create_kwargs) as stream:
                    message = stream.get_final_message()

            if message.stop_reason == "max_tokens":
                raise ValueError(
                    f"Yanıt {create_kwargs['max_tokens']} çıktı tokenına sığmadan kesildi; "
                    "model 'max_tokens' değerini artırın veya BDR girdisini kısaltın."
                )

            tool_input = next((b.input for b in message.content if getattr(b, "type", None) == "tool_use"), None)
            if tool_input is not None:
                report = BDRRiskAnalysisReport.model_validate(tool_input)
            else:
                raw_text = next((b.text for b in message.content if getattr(b, "type", None) == "text"), "{}")
                report = self._parse_report(raw_text)

            report.is_mock_fallback = False
            return report

        except Exception as e:
            raise RuntimeError(f"❌ Anthropic API Hatası ({self.model_name}): {e}")

    def raw_generate(self, user_prompt: str, *, json_mode: bool = False) -> str:
        if not self.api_key:
            raise RuntimeError(f"Anthropic raw_generate: ANTHROPIC_API_KEY yok ({self.model_name}).")
        if not HAS_ANTHROPIC:
            raise RuntimeError("Anthropic raw_generate: anthropic paketi yüklü değil.")

        client = anthropic.Anthropic(api_key=self.api_key.strip())
        system_prompt = self.system_prompt
        if json_mode:
            system_prompt += "\n\nYalnızca geçerli JSON döndür; başında/sonunda açıklama olmasın."

        with client.messages.stream(
            model=self.model_name,
            max_tokens=min(self.max_tokens, self.MAX_OUTPUT_TOKENS),
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            message = stream.get_final_message()
        return next((b.text for b in message.content if getattr(b, "type", None) == "text"), "")
