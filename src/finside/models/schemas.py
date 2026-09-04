from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

# Python'da "İ".lower() araya U+0307 (combining dot above) bırakır — bu, plain-i
# içeren anahtar kelimelerin büyük-İ ile başlayan girdilere karşı eşleşmesini bozar.
_COMBINING_DOT = chr(0x0307)


def sadelestir_tr(text: str) -> str:
    return text.strip().lower().replace(_COMBINING_DOT, "")


@dataclass
class BenchmarkRequest:
    """Model kıyaslama isteği parametrelerini gruplayan veri sınıfı."""
    selected_model_ids: List[str]
    bdr_content: str
    bdr_name: str
    is_mock_mode: bool = False
    hyperparams: Optional[Dict[str, float]] = None
    system_prompt: Optional[str] = None
    user_template: Optional[str] = None


@dataclass
class SidebarState:
    """Yan kontrol paneli UI durumunu gruplayan veri sınıfı."""
    bdr_content: str
    bdr_name: str
    is_mock_mode: bool
    selected_model_ids: List[str]
    hyperparams: Dict[str, float]
    run_btn: bool


class RiskKategorisi(str, Enum):
    """BDR Raporu Kalitatif Risk Kategorileri."""
    DENETCI_GORUSU_VE_KAM = "Bağımsız Denetçi Görüşü ve Kilit Denetim Konuları"
    DAVA = "Dava, Hukuki İhtilaflar ve Karşılıklar"
    REHIN_IPOTEK_TRI = "Teminat, Rehin, İpotek (TRİ) ve Varlık Kısıtlamaları"
    KEFALET_TEMINAT = "Verilen Kefalet, Garanti ve Teminatlar"
    KOSULLU_YUKUMLULUK = "Koşullu Yükümlülükler ve Taahhütler"
    KUR_VE_DOVIZ_RISKI = "Net Yabancı Para Pozisyonu, Kur ve Faiz Oranı Riski"
    LIKIDITE_VE_BORCLANMA = "Borç Vade Yapısı, Akreditif ve Likidite Riski"
    ILISKILI_TARAF = "İlişkili Taraf İşlemleri ve Bakiyeleri"
    MEVZUAT_VERGI = "Vergi Tarhiyatları, Geçmiş Yıl Zararları ve Mevzuat Riskleri"
    FAALIYET_SUREKLILIGI_VE_SONRAKI_OLAYLAR = "Faaliyet Sürekliliği ve Bilanço Sonrası Olaylar"
    VARLIK_DEGER_DUSUKLUGU_VE_SEREFIYE = "Varlık Değer Düşüklüğü ve Şerefiye"
    MUHASEBE_TAHMINI_VE_HASILAT = "Kritik Muhasebe Tahminleri ve Hasılat Kaydı"
    IC_KONTROL_ZAFIYETI = "İç Kontrol Zafiyetleri"
    TUREV_VE_HEDGE_ISLEMLERI = "Türev ve Hedge İşlemleri"
    ISLETME_BIRLESMESI = "İşletme Birleşmeleri ve Satın Almalar"
    DIGER_KALITATIF_RISK = "Diğer Kalitatif Risk Unsuarları"


class RiskDerecesi(str, Enum):
    """Kalitatif Risk Derece Seviyesi."""
    DUSUK = "Düşük"
    ORTA = "Orta"
    YUKSEK = "Yüksek"
    KRITIK = "Kritik"


class DenetciGorusTuru(str, Enum):
    """Bağımsız Denetçi Rapor Görüş Türü."""
    OLUMLU = "Olumlu Görüş"
    SARTLI_OLUMLU = "Şartlı / Sınırlı Olumlu Görüş"
    OLUMSUZ = "Olumsuz Görüş"
    GORUS_BILDIRMEKTEN_KACINMA = "Görüş Bildirmekten Kaçınma"


class KomiteKararEgilimi(str, Enum):
    """Kredi Komitesi Karar Eğilimi."""
    OLUMLU = "Olumlu (Kredi Tahsis Edilebilir)"
    SARTLI_OLUMLU = "Şartlı Olumlu (Ek Teminat / Kısıtlayıcı Taahhüt-Covenant İle)"
    OLUMSUZ = "Olumsuz (Yüksek Kalitatif Risk)"
    BELIRSIZ = "Belirsiz (Model Karar Üretmedi)"


class BDRRiskItem(BaseModel):
    """Tekil BDR Kalitatif Risk Kalemi Nesnesi."""
    risk_kategorisi: RiskKategorisi = Field(..., description="Risk kaleminin dahil olduğu ana TFRS/BDR kategorisi.")
    dipnot_referansi: Optional[str] = Field(None, description="Ait olduğu BDR dipnot referansı.")
    baslik: str = Field(..., description="Risk kaleminin kısa ve net başlığı.")
    detay: str = Field(..., description="BDR dipnotundaki riskin ayrıntıları.")
    tutar_bilgisi: Optional[str] = Field(None, description="Riskin parasal tutarı (TL/USD/EUR).")
    etki_degerlendirmesi: str = Field(..., description="Riskin borç ödeme veya likiditeye etkisi.")
    risk_derecesi: RiskDerecesi = Field(..., description="Risk derece sınıfı.")
    kaynak_metin_alintisi: str = Field(..., description="BDR metninden doğrudan alıntı.")
    dogrulanmadi: bool = Field(False, description="Kaynak alıntısının ham metinde doğrulanma durumu.")
    kaynak_modeller: List[str] = Field(default_factory=list, description="Bu riski tespit eden LLM modelleri.")

    @field_validator("risk_kategorisi", mode="before")
    @classmethod
    def normalize_risk_kategorisi(cls, v: Any) -> str:
        if isinstance(v, str):
            # Python'da "İ".lower() araya U+0307 combining nokta bırakır; bu, "ilişkili"
            # gibi i-başlı anahtar kelimelerin büyük-İ girdilerine karşı eşleşmesini
            # bozar. Her iki tarafı da bu noktadan arındır.
            v_clean = sadelestir_tr(v)
            for cat in RiskKategorisi:
                cat_clean = sadelestir_tr(cat.value)
                if cat_clean in v_clean or v_clean in cat_clean:
                    return cat.value

            if "iç kontrol" in v_clean or "ic kontrol" in v_clean or "kontrol zafiyet" in v_clean or "kontrol eksikli" in v_clean:
                return RiskKategorisi.IC_KONTROL_ZAFIYETI.value
            if "şerefiye" in v_clean or "serefiye" in v_clean or "değer düşüklüğü" in v_clean or "deger dusuklugu" in v_clean:
                return RiskKategorisi.VARLIK_DEGER_DUSUKLUGU_VE_SEREFIYE.value
            if "türev" in v_clean or "turev" in v_clean or "forward" in v_clean or "hedge" in v_clean or "swap" in v_clean or "korunma muhasebesi" in v_clean:
                return RiskKategorisi.TUREV_VE_HEDGE_ISLEMLERI.value
            if "birleşme" in v_clean or "birlesme" in v_clean or "satın alma" in v_clean or "satin alma" in v_clean or "iktisap" in v_clean or "devralma" in v_clean:
                return RiskKategorisi.ISLETME_BIRLESMESI.value
            if "hasılat" in v_clean or "hasilat" in v_clean or "muhasebe tahmini" in v_clean or "kritik tahmin" in v_clean or "önemli tahmin" in v_clean:
                return RiskKategorisi.MUHASEBE_TAHMINI_VE_HASILAT.value
            if (
                "faaliyet" in v_clean or "süreklilik" in v_clean or "sonraki" in v_clean
                or "bilanço" in v_clean or "sermaye artır" in v_clean or "sermaye artış" in v_clean
            ):
                return RiskKategorisi.FAALIYET_SUREKLILIGI_VE_SONRAKI_OLAYLAR.value
            if "kefalet" in v_clean or "garanti" in v_clean:
                return RiskKategorisi.KEFALET_TEMINAT.value
            if "dava" in v_clean or "ihtilaf" in v_clean:
                return RiskKategorisi.DAVA.value
            if "tri" in v_clean or "ipotek" in v_clean or "rehin" in v_clean:
                return RiskKategorisi.REHIN_IPOTEK_TRI.value
            if (
                "üst yönetim" in v_clean or "üst düzey yönetici" in v_clean
                or "kilit yönetici" in v_clean or "yönetim kurulu ücret" in v_clean
                or "yönetim kuruluna sağlanan" in v_clean
            ):
                return RiskKategorisi.ILISKILI_TARAF.value
            if (
                "döviz" in v_clean or "kur" in v_clean or "yabancı para" in v_clean
                or "libor" in v_clean or "faiz oran" in v_clean or "faiz riski" in v_clean
            ):
                return RiskKategorisi.KUR_VE_DOVIZ_RISKI.value
            if "vergi" in v_clean or "tarhiyat" in v_clean:
                return RiskKategorisi.MEVZUAT_VERGI.value
            if "ilişkili" in v_clean:
                return RiskKategorisi.ILISKILI_TARAF.value
            if "likidite" in v_clean or "akreditif" in v_clean or "borç" in v_clean:
                return RiskKategorisi.LIKIDITE_VE_BORCLANMA.value
            if "denetçi" in v_clean or "görüş" in v_clean or "kam" in v_clean or "kilit" in v_clean:
                return RiskKategorisi.DENETCI_GORUSU_VE_KAM.value
            if (
                "koşullu" in v_clean or "taahhüt" in v_clean or "kıdem tazminat" in v_clean
                or "kidem tazminat" in v_clean or "çalışan hakları" in v_clean
                or "emeklilik yükümlülü" in v_clean
            ):
                return RiskKategorisi.KOSULLU_YUKUMLULUK.value
            return RiskKategorisi.DIGER_KALITATIF_RISK.value
        return v

    @field_validator("risk_derecesi", mode="before")
    @classmethod
    def normalize_risk_derecesi(cls, v: Any) -> str:
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if "kritik" in v_clean:
                return RiskDerecesi.KRITIK.value
            if "yüksek" in v_clean or "yuksek" in v_clean or "high" in v_clean:
                return RiskDerecesi.YUKSEK.value
            if "orta" in v_clean or "medium" in v_clean:
                return RiskDerecesi.ORTA.value
            if "düşük" in v_clean or "dusuk" in v_clean or "low" in v_clean:
                return RiskDerecesi.DUSUK.value
            return RiskDerecesi.ORTA.value
        return v


_ALAN_URETILMEDI = "(Model bu alanı üretmedi)"


class BDRRiskAnalysisReport(BaseModel):
    """Nihai BDR Risk Analiz Raporu Nesnesi."""
    kullanilan_model: Optional[str] = Field(None, description="Analiz gerçekleştiren model.")
    analiz_suresi_saniye: Optional[float] = Field(None, description="Analiz süresi (sn).")
    is_mock_fallback: bool = Field(False, description="Mock simülasyon fallback bayrağı.")
    fallback_reason: Optional[str] = Field(None, description="Fallback nedeni.")
    firma_adi: Optional[str] = Field("Belirtilmemiş Şirket", description="Firma adı.")
    rapor_donemi: Optional[str] = Field("Belirtilmemiş Dönem", description="Rapor dönemi.")
    denetim_firmasi: Optional[str] = Field(None, description="Denetim kuruluşu.")
    denetci_gorusu: Optional[DenetciGorusTuru] = Field(DenetciGorusTuru.OLUMLU, description="Denetçi görüşü.")
    tespit_edilen_riskler: List[BDRRiskItem] = Field(default_factory=list, description="Risk kalemleri.")
    genel_kredi_risk_ozeti: str = Field(_ALAN_URETILMEDI, description="Risk özeti.")
    komite_tavsiyesi_ve_sartlar: List[str] = Field(default_factory=list, description="Komite tavsiyeleri.")
    karar_egilimi: KomiteKararEgilimi = Field(KomiteKararEgilimi.BELIRSIZ, description="Karar eğilimi.")
    analist_gerekce_metni: str = Field(_ALAN_URETILMEDI, description="Analist gerekçesi.")
    qa_bayraklari: List[str] = Field(default_factory=list, description="QA uyarı bayrakları.")

    @field_validator("denetci_gorusu", mode="before")
    @classmethod
    def normalize_denetci_gorusu(cls, v: Any) -> str:
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if "şartlı" in v_clean or "sınırlı" in v_clean or "qualified" in v_clean:
                return DenetciGorusTuru.SARTLI_OLUMLU.value
            if "olumsuz" in v_clean or "adverse" in v_clean:
                return DenetciGorusTuru.OLUMSUZ.value
            if "kaçınma" in v_clean or "disclaimer" in v_clean:
                return DenetciGorusTuru.GORUS_BILDIRMEKTEN_KACINMA.value
            if "olumlu" in v_clean or "unqualified" in v_clean:
                return DenetciGorusTuru.OLUMLU.value
        return v

    @field_validator("karar_egilimi", mode="before")
    @classmethod
    def normalize_karar_egilimi(cls, v: Any) -> str:
        if v is None:
            return KomiteKararEgilimi.BELIRSIZ.value
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if "şartlı" in v_clean or "sartli" in v_clean or "covenant" in v_clean:
                return KomiteKararEgilimi.SARTLI_OLUMLU.value
            if "olumsuz" in v_clean or "reddedil" in v_clean or "rejected" in v_clean:
                return KomiteKararEgilimi.OLUMSUZ.value
            if "olumlu" in v_clean:
                return KomiteKararEgilimi.OLUMLU.value
            return KomiteKararEgilimi.BELIRSIZ.value
        return v
