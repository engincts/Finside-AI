import os
from finside.providers.base import BaseProvider
from prompts.schemas import BDRRiskAnalysisReport

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class AnthropicProvider(BaseProvider):
    """Anthropic Claude API entegrasyon sağlayıcısı (Forced Tool-Use ile Yapılandırılmış Çıktı)."""

    TOOL_NAME = "bdr_risk_raporu"
    MAX_OUTPUT_TOKENS = 32000

    FALLBACK_CLAUDE_MODELS = [
        "claude-sonnet-4-5",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-5-20251101",
        "claude-sonnet-5"
    ]

    def analyze(self, user_prompt: str) -> BDRRiskAnalysisReport:
        if not self.api_key:
            return self.generate_mock_report(user_prompt, is_fallback=True, reason=f"ANTHROPIC_API_KEY bulunamadı ({self.model_name}).")
        if not HAS_ANTHROPIC:
            return self.generate_mock_report(user_prompt, is_fallback=True, reason="anthropic paketi yüklü değil.")

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

        models_to_try = [self.model_name] + [m for m in self.FALLBACK_CLAUDE_MODELS if m != self.model_name]
        last_error = None

        for current_model in models_to_try:
            try:
                create_kwargs = {
                    "model": current_model,
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

                if current_model != self.model_name:
                    report.kullanilan_model = f"{self.model_name} (Anthropic Auto-Fallback: {current_model})"
                return report

            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                if "not_found_error" in err_str or "404" in err_str or "model:" in err_str:
                    continue
                else:
                    break

        err_str = str(last_error)
        if "anthropic-workspace-id is required" in err_str:
            err_msg = (
                "Anthropic API Anahtarınız bir kurumsal hesaba bağlıdır. "
                "Anthropic Console (console.anthropic.com/settings/keys) sekmesinden yeni standart 'Create Key' diyerek "
                "bireysel API anahtarı (sk-ant-api03-...) oluşturabilirsiniz."
            )
        else:
            err_msg = f"Anthropic API Hata ({self.model_name}): {last_error}"
        print(f"[HATA] {err_msg}")
        return self.generate_mock_report(user_prompt, is_fallback=True, reason=err_msg)

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
