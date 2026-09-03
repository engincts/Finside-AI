from typing import Dict, Any
from finside.providers.base import BaseProvider
from finside.models import BDRRiskAnalysisReport

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class OpenAIProvider(BaseProvider):
    """OpenAI API entegrasyon sağlayıcısı (Rate Limit & Safe Truncation Uyumlu)."""

    # gpt-4o / gpt-4o-mini çıktı tavanı 16384. Pipeline reconcile/sentez rolleri
    # büyük yapılandırılmış JSON üretiyor; 4096 tavanı "length limit reached" hatası
    # verip mock fallback'e düşürüyordu.
    MAX_OUTPUT_TOKENS = 16384

    def analyze(self, user_prompt: str) -> BDRRiskAnalysisReport:
        if not self.api_key:
            raise RuntimeError(f"❌ OPENAI_API_KEY eksik ({self.model_name}). Lütfen .env dosyanızı veya API anahtarınızı kontrol edin.")
        if not HAS_OPENAI:
            raise RuntimeError("❌ openai paketi yüklü değil. Lütfen `pip install openai` çalıştırın.")

        active_user_prompt = user_prompt
        if len(user_prompt) > 30000 and "gpt-4o" in self.model_name and "mini" not in self.model_name:
            active_user_prompt = user_prompt[:30000] + "\n\n[UYARI: Metin OpenAI Tier 1 (10K TPM) limitine takılmamak için ilk 30.000 karakter ile sınırlandırılmıştır.]"

        try:
            client = OpenAI(api_key=self.api_key)
            completion_kwargs = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": active_user_prompt}
                ],
                "response_format": BDRRiskAnalysisReport,
                "temperature": self.temperature,
                "top_p": self.top_p,
            }

            if "o1" in self.model_name or "o3" in self.model_name:
                completion_kwargs["reasoning_effort"] = str(self.reasoning_effort).lower()
                completion_kwargs["max_completion_tokens"] = self.max_tokens
                completion_kwargs.pop("temperature", None)
                completion_kwargs.pop("top_p", None)
            else:
                completion_kwargs["max_tokens"] = min(self.max_tokens, self.MAX_OUTPUT_TOKENS)

            try:
                completion = client.beta.chat.completions.parse(**completion_kwargs)
            except Exception as first_err:
                err_str = str(first_err).lower()
                if "rate_limit_exceeded" in err_str or "tokens per min" in err_str or "tpm" in err_str:
                    completion_kwargs["messages"][1]["content"] = user_prompt[:15000] + "\n\n[TPM Limit Kurtarma: Metin ilk 15.000 karakter ile sınırlandırıldı.]"
                    completion = client.beta.chat.completions.parse(**completion_kwargs)
                else:
                    raise first_err

            report = completion.choices[0].message.parsed
            report.is_mock_fallback = False
            return report
        except Exception as e:
            raise RuntimeError(f"❌ OpenAI API Hatası ({self.model_name}): {e}")

    def raw_generate(self, user_prompt: str, *, json_mode: bool = False) -> str:
        if not self.api_key:
            raise RuntimeError(f"OpenAI raw_generate: OPENAI_API_KEY yok ({self.model_name}).")
        if not HAS_OPENAI:
            raise RuntimeError("OpenAI raw_generate: openai paketi yüklü değil.")

        client = OpenAI(api_key=self.api_key)
        kwargs = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if "o1" in self.model_name or "o3" in self.model_name:
            kwargs["max_completion_tokens"] = self.max_tokens
            kwargs["reasoning_effort"] = str(self.reasoning_effort).lower()
        else:
            kwargs["max_tokens"] = min(self.max_tokens, 4096)
            kwargs["temperature"] = self.temperature
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        return client.chat.completions.create(**kwargs).choices[0].message.content or ""
