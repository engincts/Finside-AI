import json
import os
from typing import Dict, Any
from finside.providers.base import BaseProvider
from prompts.schemas import BDRRiskAnalysisReport

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class AnthropicProvider(BaseProvider):
    """Anthropic Claude API entegrasyon sağlayıcısı (Standart & Organization Key Uyumlu)."""

    def analyze(self, user_prompt: str) -> BDRRiskAnalysisReport:
        if not self.api_key:
            return self.generate_mock_report(user_prompt, is_fallback=True, reason=f"ANTHROPIC_API_KEY bulunamadı ({self.model_name}).")
        if not HAS_ANTHROPIC:
            return self.generate_mock_report(user_prompt, is_fallback=True, reason="anthropic paketi yüklü değil.")

        try:
            client_kwargs = {"api_key": self.api_key.strip()}
            workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
            if workspace_id and workspace_id.strip():
                client_kwargs["default_headers"] = {"anthropic-workspace-id": workspace_id.strip()}

            client = anthropic.Anthropic(**client_kwargs)
            schema_str = json.dumps(BDRRiskAnalysisReport.model_json_schema(), ensure_ascii=False)
            system_prompt = f"{self.system_prompt}\nStrict JSON Schema:\n{schema_str}"
            
            create_kwargs = {
                "model": self.model_name,
                "max_tokens": self.max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}]
            }

            if self.temperature is not None:
                create_kwargs["temperature"] = float(self.temperature)

            try:
                message = client.messages.create(**create_kwargs)
            except TypeError:
                create_kwargs.pop("temperature", None)
                create_kwargs.pop("top_p", None)
                message = client.messages.create(**create_kwargs)

            raw_text = message.content[0].text if message.content else "{}"
            json_str = self._extract_json(raw_text)
            report = BDRRiskAnalysisReport.model_validate_json(json_str)
            report.is_mock_fallback = False
            return report
        except Exception as e:
            err_str = str(e)
            if "anthropic-workspace-id is required" in err_str:
                err_msg = (
                    "Anthropic API Anahtarınız bir kurumsal hesaba bağlıdır. "
                    "Anthropic Console (console.anthropic.com/settings/keys) sekmesinden yeni standart 'Create Key' diyerek "
                    "bireysel API anahtarı (sk-ant-api03-...) oluşturabilirsiniz."
                )
            else:
                err_msg = f"Anthropic API Hata ({self.model_name}): {e}"
            print(f"[HATA] {err_msg}")
            return self.generate_mock_report(user_prompt, is_fallback=True, reason=err_msg)
