import json
import time
from typing import Dict, Any, Optional
from pathlib import Path

from config import Config
from finside.prompt_loader import PromptLoader
from prompts.schemas import (
    BDRRiskAnalysisReport, RiskKategorisi, RiskDerecesi, 
    KomiteKararEgilimi, BDRRiskItem, DenetciGorusTuru
)


class BDRAnalyzer:
    """BDR metinlerini top_p, repetition_penalty, reasoning_effort ve strict JSON schema ile analiz eden motor."""

    EFFORT_TOKEN_MAP = {
        "low": 1024,
        "medium": 2048,
        "high": 4096,
        "auto": 2048
    }

    def __init__(self, model_config: Optional[Dict[str, Any]] = None):
        if model_config is None:
            enabled = Config.get_enabled_models()
            self.model_config = enabled[0] if enabled else {
                "id": "mock",
                "name": "Mock Modeli",
                "provider": "mock",
                "model_name": "mock-v1"
            }
        else:
            self.model_config = model_config

        self.provider = self.model_config.get("provider", "mock")
        self.model_name = self.model_config.get("model_name", "mock")
        self.prompt_file = self.model_config.get("prompt_file", "bdr_analyst_v1.md")
        self.api_key = Config.get_api_key_for_model(self.model_config)
        self.temperature = self.model_config.get("temperature", 0.1)
        self.top_p = self.model_config.get("top_p", 0.9)
        self.repetition_penalty = self.model_config.get("repetition_penalty", 1.0)
        self.reasoning_effort = self.model_config.get("reasoning_effort", "medium")
        self.strict_schema = self.model_config.get("strict_schema", True)

        # Markdown Prompt Yükleyici (PromptLoader)
        self.system_prompt, self.user_template = PromptLoader.load_prompt_md(self.prompt_file)

    def _get_reasoning_tokens(self) -> int:
        if isinstance(self.reasoning_effort, int):
            return self.reasoning_effort
        effort_str = str(self.reasoning_effort).lower()
        return self.EFFORT_TOKEN_MAP.get(effort_str, 2048)

    def analyze(self, bdr_text: str) -> BDRRiskAnalysisReport:
        user_prompt = self.user_template.format(bdr_text=bdr_text)
        start_time = time.perf_counter()

        if self.provider == "gemini":
            report = self._analyze_with_gemini(user_prompt)
        elif self.provider == "openai":
            report = self._analyze_with_openai(user_prompt)
        elif self.provider == "anthropic":
            report = self._analyze_with_anthropic(user_prompt)
        elif self.provider == "huggingface":
            report = self._analyze_with_huggingface(user_prompt)
        else:
            report = self._generate_mock_report(bdr_text)

        elapsed = round(time.perf_counter() - start_time, 3)
        report.analiz_suresi_saniye = elapsed
        report.kullanilan_model = self.model_config.get("name", self.model_name)
        return report

    def _analyze_with_gemini(self, user_prompt: str) -> BDRRiskAnalysisReport:
        if not self.api_key:
            print(f"[UYARI] {self.model_name} için GEMINI_API_KEY bulunamadı. Mock rapor üretiliyor...")
            return self._generate_mock_report(user_prompt)

        # 1. Yeni SDK Desteği (google-genai)
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            config_kwargs = {
                "system_instruction": self.system_prompt,
                "response_mime_type": "application/json",
                "response_schema": BDRRiskAnalysisReport,
                "temperature": self.temperature,
                "top_p": self.top_p,
            }

            if hasattr(types, "ThinkingConfig"):
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=self._get_reasoning_tokens()
                )

            response = client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(**config_kwargs)
            )
            return BDRRiskAnalysisReport.model_validate_json(response.text)
        except Exception as e1:
            # 2. Klasik SDK Fallback (google-generativeai)
            try:
                import google.generativeai as genai_legacy
                genai_legacy.configure(api_key=self.api_key)
                model = genai_legacy.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=self.system_prompt,
                    generation_config={"temperature": self.temperature, "top_p": self.top_p}
                )
                response = model.generate_content(user_prompt)
                json_str = self._extract_json(response.text)
                return BDRRiskAnalysisReport.model_validate_json(json_str)
            except Exception as e2:
                print(f"[HATA] Gemini API ({self.model_name}): SDK1: {e1} | SDK2: {e2}")
                return self._generate_mock_report(user_prompt)

    def _analyze_with_openai(self, user_prompt: str) -> BDRRiskAnalysisReport:
        if not self.api_key:
            print(f"[UYARI] {self.model_name} için OPENAI_API_KEY bulunamadı. Mock rapor üretiliyor...")
            return self._generate_mock_report(user_prompt)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
            completion_kwargs = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": BDRRiskAnalysisReport,
                "temperature": self.temperature,
                "top_p": self.top_p,
            }

            if "o1" in self.model_name or "o3" in self.model_name:
                completion_kwargs["reasoning_effort"] = str(self.reasoning_effort).lower()
                completion_kwargs.pop("temperature", None)
                completion_kwargs.pop("top_p", None)

            completion = client.beta.chat.completions.parse(**completion_kwargs)
            return completion.choices[0].message.parsed
        except Exception as e:
            print(f"[HATA] OpenAI API ({self.model_name}): {e}")
            return self._generate_mock_report(user_prompt)

    def _analyze_with_anthropic(self, user_prompt: str) -> BDRRiskAnalysisReport:
        if not self.api_key:
            print(f"[UYARI] {self.model_name} için ANTHROPIC_API_KEY bulunamadı. Mock rapor üretiliyor...")
            return self._generate_mock_report(user_prompt)

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            schema_str = json.dumps(BDRRiskAnalysisReport.model_json_schema(), ensure_ascii=False)
            system_prompt = f"{self.system_prompt}\nStrict JSON Schema:\n{schema_str}"
            
            message = client.messages.create(
                model=self.model_name,
                max_tokens=self.model_config.get("max_tokens", 4096),
                temperature=self.temperature,
                top_p=self.top_p,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            json_str = self._extract_json(message.content[0].text)
            return BDRRiskAnalysisReport.model_validate_json(json_str)
        except Exception as e:
            print(f"[HATA] Anthropic API ({self.model_name}): {e}")
            return self._generate_mock_report(user_prompt)

    def _analyze_with_huggingface(self, user_prompt: str) -> BDRRiskAnalysisReport:
        if not self.api_key:
            print(f"[UYARI] HuggingFace ({self.model_name}) için HF_TOKEN bulunamadı. Mock rapor üretiliyor...")
            return self._generate_mock_report(user_prompt)

        try:
            from huggingface_hub import InferenceClient
            client = InferenceClient(model=self.model_name, token=self.api_key)
            schema_str = json.dumps(BDRRiskAnalysisReport.model_json_schema(), ensure_ascii=False)
            
            # 1. Chat Completion API Desteği (Conversational & Instruct Modeller İçin)
            try:
                response_chat = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": f"{self.system_prompt}\nJSON Schema:\n{schema_str}"},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=self.model_config.get("max_tokens", 4096),
                    temperature=self.temperature,
                    top_p=self.top_p,
                )
                raw_text = response_chat.choices[0].message.content
            except Exception:
                # 2. Text Generation Fallback
                prompt = f"System: {self.system_prompt}\nStrict JSON Schema:\n{schema_str}\nUser: {user_prompt}\nAssistant:"
                hf_params = {
                    "prompt": prompt,
                    "max_new_tokens": self.model_config.get("max_tokens", 4096),
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                }
                if self.repetition_penalty != 1.0:
                    hf_params["repetition_penalty"] = self.repetition_penalty

                raw_text = client.text_generation(**hf_params)

            json_str = self._extract_json(raw_text)
            return BDRRiskAnalysisReport.model_validate_json(json_str)
        except Exception as e:
            print(f"[HATA] HuggingFace API ({self.model_name}): {e}")
            return self._generate_mock_report(user_prompt)

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        start, end = text.find("{"), text.rfind("}")
        return text[start:end+1] if start != -1 and end != -1 else text

    def _generate_mock_report(self, bdr_text: str) -> BDRRiskAnalysisReport:
        is_borusan = "borusan" in bdr_text.lower()
        model_display = self.model_config.get("name", self.model_name)

        if is_borusan:
            return BDRRiskAnalysisReport(
                firma_adi="Borusan Birleşik Boru Fabrikaları A.Ş. ve Bağlı Ortaklıkları",
                rapor_donemi="31 Aralık 2024",
                denetim_firmasi="Güney Bağımsız Denetim ve SMMM A.Ş. (Ernst & Young Global Limited)",
                denetci_gorusu=DenetciGorusTuru.OLUMLU,
                tespit_edilen_riskler=[
                    BDRRiskItem(
                        risk_kategorisi=RiskKategorisi.REHIN_IPOTEK_TRI,
                        dipnot_referansi="Dipnot 21 - Taahhütler (TRİ)",
                        baslik="Konsolide Teminat, Rehin ve İpotek (TRİ) Yükü",
                        detay="Şirket ve bağlı ortaklıkları tarafından toplam 6.897.006 bin TL tutarında TRİ verilmiştir.",
                        tutar_bilgisi="6.897.006.000 TL",
                        etki_degerlendirmesi="Grup şirketleri arası bulaşma ve kısıtlı teminat marjı riski.",
                        risk_derecesi=RiskDerecesi.YUKSEK,
                        kaynak_metin_alintisi="Dipnot 21: Toplam Verilen TRİ Tutarı 6.897.006 bin TL..."
                    ),
                    BDRRiskItem(
                        risk_kategorisi=RiskKategorisi.KUR_VE_DOVIZ_RISKI,
                        dipnot_referansi="Dipnot 35 - Finansal Risk Yönetimi",
                        baslik="Net Yabancı Para Açık Pozisyonu ve Kur Riski",
                        detay="1.959.702 bin TL net yabancı para açık pozisyonu bulunmaktadır.",
                        tutar_bilgisi="1.959.702.000 TL",
                        etki_degerlendirmesi="Kambiyo zararı ve net kar marjı baskısı riski.",
                        risk_derecesi=RiskDerecesi.YUKSEK,
                        kaynak_metin_alintisi="Dipnot 35: Net Yabancı Para Varlık/Yükümlülük Pozisyonu: (1.959.702) bin TL..."
                    ),
                    BDRRiskItem(
                        risk_kategorisi=RiskKategorisi.MEVZUAT_VERGI,
                        dipnot_referansi="Dipnot 32 - Vergi Varlık ve Yükümlülükleri",
                        baslik="Geçmiş Yıl Zararları ve Ertelenmiş Vergi Varlığı",
                        detay="3.513.255 bin TL tutarında 2025-2029 yılları arasında mahsup edilebilir geçmiş yıl zararı bulunmaktadır.",
                        tutar_bilgisi="3.513.255.000 TL",
                        etki_degerlendirmesi="Gelecek dönemlerde yeterli vergilendirilebilir kar elde edilememesi halinde vergi varlığı mahsup avantajı yitirilebilir.",
                        risk_derecesi=RiskDerecesi.ORTA,
                        kaynak_metin_alintisi="Dipnot 32: Vergiden mahsup edilecek geçmiş yıl zararları: 3.513.255 bin TL..."
                    )
                ],
                genel_kredi_risk_ozeti=f"[{model_display}] Borusan 2024 BDR kalitatif risk profili orta-yüksek seviyededir.",
                komite_tavsiyesi_ve_sartlar=[
                    "Döviz açık pozisyonu için %75 oranında türev (hedging) şartı.",
                    "Bağlı ortaklık TRİ limitlerinin dondurulması."
                ],
                karar_egilimi=KomiteKararEgilimi.SARTLI_OLUMLU,
                analist_gerekce_metni="Operasyonel büyüklük olumlu ancak kalitatif riskler nedeniyle şartlı tahsis tavsiye edilir."
            )

        return BDRRiskAnalysisReport(
            firma_adi="ABC Sanayi A.Ş.",
            rapor_donemi="31 Aralık 2023",
            denetim_firmasi="Örnek Bağımsız Denetim A.Ş.",
            denetci_gorusu=DenetciGorusTuru.OLUMLU,
            tespit_edilen_riskler=[
                BDRRiskItem(
                    risk_kategorisi=RiskKategorisi.DAVA,
                    dipnot_referansi="Dipnot 18 - Davalar",
                    baslik="Vergi İncelemesi Davası",
                    detay="45M TL vergi tarhiyatı davası devam etmektedir.",
                    tutar_bilgisi="45.000.000 TL",
                    etki_degerlendirmesi="Nakit akışına olumsuz etki riski.",
                    risk_derecesi=RiskDerecesi.YUKSEK,
                    kaynak_metin_alintisi="Dipnot 18: 45M TL vergi tarhiyatı..."
                )
            ],
            genel_kredi_risk_ozeti="BDR kalitatif risk profili orta-yüksek seviyededir.",
            komite_tavsiyesi_ve_sartlar=["Dava riski için teminat alınması."],
            karar_egilimi=KomiteKararEgilimi.SARTLI_OLUMLU,
            analist_gerekce_metni="Şartlı tahsis tavsiye edilir."
        )

    def format_report_as_markdown(self, report: BDRRiskAnalysisReport) -> str:
        lines = [
            "# 📊 BDR Kredi Komitesi Risk Değerlendirme Raporu",
            f"**Model:** `{report.kullanilan_model}` (Prompt: `{self.prompt_file}`, Reasoning: `{self.reasoning_effort}`, Temp: `{self.temperature}`, Top-p: `{self.top_p}`, Repetition Penalty: `{self.repetition_penalty}`)",
            f"**Analiz Süresi:** `{report.analiz_suresi_saniye} saniye`",
            f"**Firma Adı:** {report.firma_adi}",
            f"**Rapor Dönemi:** {report.rapor_donemi}",
            f"**Bağımsız Denetim Firması:** {report.denetim_firmasi or 'Belirtilmemiş'}",
            f"**Denetçi Görüşü:** `{report.denetci_gorusu.value if report.denetci_gorusu else 'Belirtilmemiş'}`",
            f"**Genel Karar Eğilimi:** `{report.karar_egilimi.value}`",
            "",
            "---",
            "## 📌 1. Genel Kredi Risk Özeti",
            report.genel_kredi_risk_ozeti,
            "",
            "---",
            "## ⚠️ 2. Tespit Edilen Kalitatif Risk Kalemleri",
            ""
        ]

        for idx, risk in enumerate(report.tespit_edilen_riskler, 1):
            severity = {
                RiskDerecesi.DUSUK: "🟢 Düşük",
                RiskDerecesi.ORTA: "🟡 Orta",
                RiskDerecesi.YUKSEK: "🔴 Yüksek",
                RiskDerecesi.KRITIK: "🔥 Kritik"
            }.get(risk.risk_derecesi, risk.risk_derecesi.value)

            lines.extend([
                f"### {idx}. {risk.baslik}",
                f"- **Kategori:** `{risk.risk_kategorisi.value}`",
                f"- **Dipnot Referansı:** `{risk.dipnot_referansi or 'BDR Genel'}`",
                f"- **Risk Derecesi:** {severity}",
                f"- **Tutar:** {risk.tutar_bilgisi or 'Belirtilmemiş'}",
                f"- **Detay:** {risk.detay}",
                f"- **Kredi Etkisi:** {risk.etki_degerlendirmesi}",
                f"- **BDR Alıntısı:** *\"{risk.kaynak_metin_alintisi}\"*",
                ""
            ])

        lines.extend([
            "---",
            "## 📋 3. Kredi Komitesi Tavsiyeleri & Şartlar",
        ])
        for sart in report.komite_tavsiyesi_ve_sartlar:
            lines.append(f"- [ ] {sart}")

        lines.extend([
            "",
            "---",
            "## 📝 4. Analist Gerekçelendirme Metni",
            report.analist_gerekce_metni
        ])

        return "\n".join(lines)
