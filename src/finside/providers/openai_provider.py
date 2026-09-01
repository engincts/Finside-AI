from typing import Dict, Any
from finside.providers.base import BaseProvider
from prompts.schemas import BDRRiskAnalysisReport

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class OpenAIProvider(BaseProvider):
    """OpenAI API entegrasyon sağlayıcısı (10K TPM Rate Limit & Safe Truncation Uyumlu)."""

    def analyze(self, user_prompt: str) -> BDRRiskAnalysisReport:
        if not self.api_key:
            return self.generate_mock_report(user_prompt, is_fallback=True, reason=f"OPENAI_API_KEY bulunamadı ({self.model_name}).")
        if not HAS_OPENAI:
            return self.generate_mock_report(user_prompt, is_fallback=True, reason="openai paketi yüklü değil.")

        # OpenAI Tier 1 GPT-4o hesabı için 10.000 - 30.000 TPM (Tokens Per Minute) sınırı koruması
        # gpt-4o için metin 30.000 karakterden (~7.500 token) büyükse güvenli kırpma yap
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
                completion_kwargs["max_tokens"] = min(self.max_tokens, 4096)

            try:
                completion = client.beta.chat.completions.parse(**completion_kwargs)
            except Exception as first_err:
                err_str = str(first_err).lower()
                if "rate_limit_exceeded" in err_str or "tokens per min" in err_str or "tpm" in err_str:
                    # Metni 15.000 karaktere indirip tekrar dene (Rate limit kurtarma)
                    completion_kwargs["messages"][1]["content"] = user_prompt[:15000] + "\n\n[TPM Limit Kurtarma: Metin ilk 15.000 karakter ile sınırlandırıldı.]"
                    completion = client.beta.chat.completions.parse(**completion_kwargs)
                else:
                    raise first_err

            report = completion.choices[0].message.parsed
            report.is_mock_fallback = False
            return report
        except Exception as e:
            err_str = str(e)
            if "tokens per min" in err_str.lower() or "tpm" in err_str.lower():
                err_msg = f"OpenAI Tier 1 gpt-4o dakikalık 10.000 token (TPM) limitini aştı. OpenAI hesabınızda Tier 2'ye geçene kadar 200K TPM limitli 'gpt-4o-mini' modelini kullanabilirsiniz. (Hata: {e})"
            else:
                err_msg = f"OpenAI API Hata ({self.model_name}): {e}"
            print(f"[HATA] {err_msg}")
            return self.generate_mock_report(user_prompt, is_fallback=True, reason=err_msg)
