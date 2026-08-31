import json
from typing import Dict, Any, List
from finside.providers.base import BaseProvider
from prompts.schemas import BDRRiskAnalysisReport

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
            return self.generate_mock_report(user_prompt, is_fallback=True, reason=f"HF_TOKEN bulunamadı ({self.model_name}).")
        if not HAS_HUGGINGFACE:
            return self.generate_mock_report(user_prompt, is_fallback=True, reason="huggingface_hub paketi yüklü değil.")

        schema_str = json.dumps(BDRRiskAnalysisReport.model_json_schema(), ensure_ascii=False)
        strict_system_prompt = (
            f"{self.system_prompt}\n\n"
            "ÖNEMLİ: Yalnızca ve Yalnızca aşağıdaki JSON Şemasına %100 uyan GEÇERLİ BİR JSON OBJESİ DÖNDÜR. "
            "Cevabının başında veya sonunda hiçbir ek açıklama, selamlama veya markdown metni OLMAMALIDIR.\n"
            f"JSON Schema:\n{schema_str}"
        )

        # Denenecek model isimleri sırası (İstenen Model -> Lider HF Serverless Modeller)
        models_to_try = [self.model_name] + [m for m in self.FALLBACK_MODELS if m != self.model_name]
        last_error = None

        for current_model in models_to_try:
            try:
                client = InferenceClient(model=current_model, token=self.api_key)
                raw_text = None

                # 1. Deneme: Chat Completion API (Task: conversational)
                try:
                    response_chat = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": strict_system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        top_p=self.top_p,
                    )
                    raw_text = response_chat.choices[0].message.content
                except Exception as chat_err:
                    chat_err_str = str(chat_err).lower()
                    # Eğer "not a chat model" veya "not supported" ise text_generation dene veya sonraki modele geç
                    if "not a chat model" in chat_err_str:
                        prompt_formatted = f"System: {strict_system_prompt}\nUser: {user_prompt}\nAssistant:"
                        try:
                            raw_text = client.text_generation(
                                prompt=prompt_formatted,
                                max_new_tokens=self.max_tokens,
                                temperature=self.temperature,
                                top_p=self.top_p,
                            )
                        except Exception:
                            raise chat_err
                    else:
                        raise chat_err

                if raw_text:
                    json_str = self._extract_json(raw_text)
                    report = BDRRiskAnalysisReport.model_validate_json(json_str)
                    report.is_mock_fallback = False
                    
                    # Eğer fallback model kullanıldıysa kullanıcıyı şeffaf bilgilendir
                    if current_model != self.model_name:
                        report.kullanilan_model = f"{self.model_name} (HF Serverless Auto-Fallback: {current_model})"
                    return report

            except Exception as err:
                last_error = err
                err_str = str(err).lower()
                
                # Eğer model barındırılmıyorsa / sohbet modeli değilse / 404 ise sıradaki modele geç
                if any(k in err_str for k in [
                    "model_not_supported", "not supported by any provider", 
                    "not a chat model", "404", "not found", "invalid_request_error"
                ]):
                    continue
                else:
                    # Kota aşımı (402) veya yetki hatası (401) durumunda döngüyü sonlandır
                    break

        err_msg = f"HuggingFace API Hata ({self.model_name}): {last_error}"
        print(f"[HATA] {err_msg}")
        return self.generate_mock_report(user_prompt, is_fallback=True, reason=err_msg)
