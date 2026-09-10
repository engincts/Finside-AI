"""OpenRouter (OpenAI-uyumlu router) sağlayıcısı.

Tek `OPENROUTER_API_KEY` ile çok sayıda açık kaynak / ticari modele erişim
(openai/gpt-oss-120b, meta-llama/*, qwen/*, deepseek/* ...). HF Inference'a göre
daha güvenilir; `:free` sonekli modeller ücretsiz (rate-limitli). Strict şema
sistem-prompt ipucu + `_parse_report` ile sağlanır.
"""

import json
from finside.providers.base import BaseProvider
from finside.models import BDRRiskAnalysisReport

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(BaseProvider):
    def _client(self):
        if not self.api_key:
            raise RuntimeError(f"❌ OPENROUTER_API_KEY eksik ({self.model_name}).")
        if not HAS_OPENAI:
            raise RuntimeError("❌ openai paketi yüklü değil.")
        return OpenAI(base_url=_BASE_URL, api_key=self.api_key.strip())

    def _strict_system(self) -> str:
        schema = json.dumps(BDRRiskAnalysisReport.model_json_schema(), ensure_ascii=False)
        return (
            f"{self.system_prompt}\n\nÖNEMLİ: Yalnızca aşağıdaki JSON şemasına %100 uyan "
            "GEÇERLİ BİR JSON OBJESİ döndür. Başında veya sonunda açıklama, markdown OLMASIN.\n"
            f"JSON Schema:\n{schema}"
        )

    def analyze(self, user_prompt: str) -> BDRRiskAnalysisReport:
        try:
            resp = self._client().chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self._strict_system()},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
            )
            text = (resp.choices[0].message.content or "").strip()
        except Exception as err:
            raise RuntimeError(f"❌ OpenRouter API Hatası ({self.model_name}): {err}")

        if not text:
            raise RuntimeError(f"❌ OpenRouter boş yanıt ({self.model_name}).")
        report = self._parse_report(text)
        report.is_mock_fallback = False
        return report

    def raw_generate(self, user_prompt: str, *, json_mode: bool = False) -> str:
        system_prompt = self.system_prompt
        if json_mode:
            system_prompt += "\n\nYalnızca geçerli JSON döndür; başında/sonunda açıklama olmasın."
        return self._client().chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=min(self.max_tokens, 4096),
            temperature=self.temperature,
        ).choices[0].message.content or ""
