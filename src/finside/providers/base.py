import json
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from config import Config
from finside.models import (
    BDRRiskAnalysisReport,
    DenetciGorusTuru,
    KomiteKararEgilimi,
    BDRRiskItem,
    RiskKategorisi,
    RiskDerecesi,
)


class BaseProvider(ABC):
    """SOLID Dependency Inversion & Open/Closed Principle: Soyut LLM Sağlayıcı Sınıfı."""

    def __init__(self, model_config: Dict[str, Any], system_prompt: str, api_key: str):
        self.model_config = model_config
        self.model_name = model_config.get("model_name", "unknown")
        self.system_prompt = system_prompt
        self.api_key = api_key
        self.temperature = model_config.get("temperature", 0.1)
        self.top_p = model_config.get("top_p", 0.9)
        self.repetition_penalty = model_config.get("repetition_penalty", 1.0)
        self.reasoning_effort = model_config.get("reasoning_effort", "high")
        
        # Max Tokens Override (Default from Config.EFFORT_TOKEN_MAP or model specific)
        default_tokens = Config.EFFORT_TOKEN_MAP.get(str(self.reasoning_effort).lower(), 8192)
        self.max_tokens = model_config.get("max_tokens", default_tokens)

    @abstractmethod
    def analyze(self, user_prompt: str) -> BDRRiskAnalysisReport:
        """Kullanıcı promptunu alır ve BDRRiskAnalysisReport Pydantic nesnesini döndürür."""
        pass

    def raw_generate(self, user_prompt: str, *, json_mode: bool = False) -> str:
        """Şemasız ham metin üretimi (triyaj, segmenter gibi pipeline rolleri için).

        `json_mode=True` yalnızca 'geçerli JSON döndür' ipucu/kip verir, Pydantic şema
        zorlamaz. Hata durumunda exception atar (çağıran trace'e yazar)."""
        raise NotImplementedError(f"{type(self).__name__} raw_generate desteklemiyor.")

    def _extract_json(self, text: str) -> str:
        """Metin içindeki en dıştaki geçerli JSON objesini ({ ... }) temizler ve çıkarır."""
        if not text:
            return "{}"
        
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1].strip()

        # En dıştaki { ile sonundaki } arasını regex ile bulur
        match = re.search(r'(\{[\s\S]*\})', text)
        if match:
            return match.group(1).strip()
        start = text.find("{")
        return text[start:].strip() if start != -1 else text

    def _repair_json(self, text: str) -> str:
        """Kesilmiş JSON'u açık parantez/tırnakları kapatarak kurtarmayı dener."""
        text = text.strip().rstrip(",")
        stack = []
        in_str = False
        esc = False
        for ch in text:
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch in "{[":
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]" and stack:
                stack.pop()
        if in_str:
            text += '"'
        return text + "".join(reversed(stack))

    def _parse_report(self, raw_text: str) -> BDRRiskAnalysisReport:
        json_str = self._extract_json(raw_text)
        try:
            return BDRRiskAnalysisReport.model_validate_json(json_str)
        except Exception:
            pass

        repaired = self._repair_json(json_str)
        try:
            return BDRRiskAnalysisReport.model_validate_json(repaired)
        except Exception:
            pass

        # Sözlük seviyesinde temizlik ve zorunlu alan tamamlama (Açık kaynak modeller için %100 dayanıklılık)
        try:
            data = json.loads(repaired if repaired.strip().endswith("}") else json_str)
            if isinstance(data, dict):
                if "tespit_edilen_riskler" in data and isinstance(data["tespit_edilen_riskler"], list):
                    cleaned_risks = []
                    for r in data["tespit_edilen_riskler"]:
                        if isinstance(r, dict):
                            if not r.get("baslik"):
                                r["baslik"] = "Kalitatif Risk Kalemi"
                            if not r.get("detay"):
                                r["detay"] = "Dipnot detayı belirtilmedi."
                            if not r.get("kaynak_metin_alintisi"):
                                r["kaynak_metin_alintisi"] = "BDR metin alıntısı bulunamadı."
                            cleaned_risks.append(r)
                    data["tespit_edilen_riskler"] = cleaned_risks
                return BDRRiskAnalysisReport.model_validate(data)
        except Exception as parse_err:
            raise ValueError(f"JSON Raporu Ayrıştırılamadı: {parse_err}")

        return BDRRiskAnalysisReport.model_validate_json(json_str)

    def generate_mock_report(self, user_prompt: str, is_fallback: bool = False, reason: Optional[str] = None) -> BDRRiskAnalysisReport:
        """API hatası veya test modunda kullanılan güvenilir mock simülasyon raporu."""
        is_borusan = "borusan" in user_prompt.lower()
        model_display = self.model_config.get("name", self.model_name)

        if is_borusan:
            return BDRRiskAnalysisReport(
                is_mock_fallback=is_fallback,
                fallback_reason=reason,
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
            is_mock_fallback=is_fallback,
            fallback_reason=reason,
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
