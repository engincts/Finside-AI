import json
from typing import Dict, Any, List
from finside.providers.base import BaseProvider
from finside.models import BDRRiskAnalysisReport

try:
    from huggingface_hub import InferenceClient
    HAS_HUGGINGFACE = True
except ImportError:
    HAS_HUGGINGFACE = False


class HuggingFaceProvider(BaseProvider):
    """HuggingFace Inference API entegrasyon sağlayıcısı (Çok Seviyeli Esnek Fallback Destekli)."""

    # HF Serverless Router üzerinde 7/24 %100 aktif olarak barındırılan lider açık kaynak modeller
    FALLBACK_MODELS = [
        "Qwen/Qwen2.5-72B-Instruct",
        "meta-llama/Llama-3.3-70B-Instruct",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        "mistralai/Mistral-Small-24B-Instruct-2501",
        "google/gemma-2-27b-it"
    ]

    def analyze(self, user_prompt: str) -> BDRRiskAnalysisReport:
        if not self.api_key:
            raise RuntimeError(f"❌ HF_TOKEN eksik ({self.model_name}). Lütfen .env dosyanızı veya API anahtarınızı kontrol edin.")
        if not HAS_HUGGINGFACE:
            raise RuntimeError("❌ huggingface_hub paketi yüklü değil. Lütfen `pip install huggingface_hub` çalıştırın.")

        schema_str = json.dumps(BDRRiskAnalysisReport.model_json_schema(), ensure_ascii=False)
        strict_system_prompt = (
            f"{self.system_prompt}\n\n"
            "ÖNEMLİ: Yalnızca ve Yalnızca aşağıdaki JSON Şemasına %100 uyan GEÇERLİ BİR JSON OBJESİ DÖNDÜR. "
            "Cevabının başında veya sonunda hiçbir ek açıklama, selamlama veya markdown metni OLMAMALIDIR.\n"
            f"JSON Schema:\n{schema_str}"
        )

        try:
            client = InferenceClient(model=self.model_name, token=self.api_key)
            raw_text = None

            try:
                # 1. Deneme: Chat completion streaming
                stream = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": strict_system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    stream=True,
                )
                raw_text = "".join(
                    (part.choices[0].delta.content or "")
                    for part in stream
                    if part.choices
                )
            except Exception:
                raw_text = None

            # 2. Deneme: Chat completion non-streaming
            if not raw_text:
                try:
                    comp = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": strict_system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        top_p=self.top_p,
                        stream=False,
                    )
                    if comp and comp.choices and comp.choices[0].message:
                        raw_text = comp.choices[0].message.content
                except Exception:
                    pass

            # 3. Deneme: Text generation API
            if not raw_text:
                try:
                    prompt_formatted = f"System: {strict_system_prompt}\nUser: {user_prompt}\nAssistant:"
                    raw_text = client.text_generation(
                        prompt=prompt_formatted,
                        max_new_tokens=self.max_tokens,
                        temperature=self.temperature,
                        top_p=self.top_p,
                    )
                except Exception:
                    pass

            # 4. Deneme: Yüksek Performanslı Serverless Fallback Modelleri
            if not raw_text:
                for fb_model in self.FALLBACK_MODELS:
                    if fb_model == self.model_name:
                        continue
                    try:
                        fb_client = InferenceClient(model=fb_model, token=self.api_key)
                        comp = fb_client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": strict_system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            max_tokens=self.max_tokens,
                            temperature=self.temperature,
                            top_p=self.top_p,
                            stream=False,
                        )
                        if comp and comp.choices and comp.choices[0].message:
                            raw_text = comp.choices[0].message.content
                            if raw_text:
                                break
                    except Exception:
                        continue

            if raw_text and raw_text.strip():
                report = self._parse_report(raw_text)
                report.is_mock_fallback = False
                return report
            else:
                raise RuntimeError("HuggingFace modellerinden yanıt alınamadı.")

        except Exception as err:
            raise RuntimeError(f"❌ HuggingFace API Hatası ({self.model_name}): {err}")

    def raw_generate(self, user_prompt: str, *, json_mode: bool = False) -> str:
        if not self.api_key:
            raise RuntimeError(f"HuggingFace raw_generate: HF_TOKEN yok ({self.model_name}).")
        if not HAS_HUGGINGFACE:
            raise RuntimeError("HuggingFace raw_generate: huggingface_hub paketi yüklü değil.")

        system_prompt = self.system_prompt
        if json_mode:
            system_prompt += "\n\nYalnızca geçerli JSON döndür; başında/sonunda açıklama olmasın."

        client = InferenceClient(model=self.model_name, token=self.api_key)
        stream = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            stream=True,
        )
        return "".join((part.choices[0].delta.content or "") for part in stream if part.choices)
