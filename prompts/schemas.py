from enum import Enum
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class RiskKategorisi(str, Enum):
    DENETCI_GORUSU_VE_KAM = "Bağımsız Denetçi Görüşü ve Kilit Denetim Konuları"
    DAVA = "Dava, Hukuki İhtilaflar ve Karşılıklar"
    REHIN_IPOTEK_TRI = "Teminat, Rehin, İpotek (TRİ) ve Varlık Kısıtlamaları"
    KEFALET_TEMINAT = "Verilen Kefalet, Garanti ve Teminatlar"
    KOSULLU_YUKUMLULUK = "Koşullu Yükümlülükler ve Taahhütler"
    KUR_VE_DOVIZ_RISKI = "Net Yabancı Para Pozisyonu ve Kur Riski"
    LIKIDITE_VE_BORCLANMA = "Borç Vade Yapısı, Akreditif ve Likidite Riski"
    ILISKILI_TARAF = "İlişkili Taraf İşlemleri ve Bakiyeleri"
    MEVZUAT_VERGI = "Vergi Tarhiyatları, Geçmiş Yıl Zararları ve Mevzuat Riskleri"
    FAALIYET_SUREKLILIGI_VE_SONRAKI_OLAYLAR = "Faaliyet Sürekliliği ve Bilanço Sonrası Olaylar"
    DIGER_KALITATIF_RISK = "Diğer Kalitatif Risk Unsuarları"


class RiskDerecesi(str, Enum):
    DUSUK = "Düşük"
    ORTA = "Orta"
    YUKSEK = "Yüksek"
    KRITIK = "Kritik"


class DenetciGorusTuru(str, Enum):
    OLUMLU = "Olumlu Görüş"
    SARTLI_OLUMLU = "Şartlı / Sınırlı Olumlu Görüş"
    OLUMSUZ = "Olumsuz Görüş"
    GORUS_BILDIRMEKTEN_KACINMA = "Görüş Bildirmekten Kaçınma"


class BDRRiskItem(BaseModel):
    risk_kategorisi: RiskKategorisi = Field(..., description="Risk kaleminin dahil olduğu ana TFRS/BDR kategorisi.")
    dipnot_referansi: Optional[str] = Field(
        None, 
        description="Riskin ait olduğu BDR dipnot numarası ve başlığı (örn: 'Dipnot 21 - Taahhütler'). Şirketten şirkete ve denetim firmasından denetim firmasına dipnot numaraları değişebileceğinden metindeki özgün referansı yazınız."
    )
    baslik: str = Field(..., description="Risk kaleminin kısa ve net başlığı.")
    detay: str = Field(..., description="BDR dipnotundaki riskin özeti ve ayrıntıları.")
    tutar_bilgisi: Optional[str] = Field(None, description="Riskin TL, USD veya EUR cinsinden tutarı.")
    etki_degerlendirmesi: str = Field(..., description="Riskin borç ödeme kapasitesi veya likidite üzerindeki etkisi.")
    risk_derecesi: RiskDerecesi = Field(..., description="Kredi analisti açısından riskin derece sınıfı.")
    kaynak_metin_alintisi: str = Field(..., description="BDR metninden alınan doğrudan alıntı.")
    dogrulanmadi: bool = Field(False, description="Pipeline Faz 4: kaynak alıntısı ham metinde bulunamadı.")
    kaynak_modeller: List[str] = Field(default_factory=list, description="Pipeline Faz 3: bu kalemi üreten map modelleri.")

    @field_validator("risk_kategorisi", mode="before")
    @classmethod
    def normalize_risk_kategorisi(cls, v: Any) -> str:
        if isinstance(v, str):
            v_clean = v.strip().lower()
            for cat in RiskKategorisi:
                if cat.value.lower() in v_clean or v_clean in cat.value.lower():
                    return cat.value
            
            if "faaliyet" in v_clean or "süreklilik" in v_clean or "sonraki" in v_clean or "bilanço" in v_clean:
                return RiskKategorisi.FAALIYET_SUREKLILIGI_VE_SONRAKI_OLAYLAR.value
            if "kefalet" in v_clean or "garanti" in v_clean:
                return RiskKategorisi.KEFALET_TEMINAT.value
            if "dava" in v_clean or "ihtilaf" in v_clean:
                return RiskKategorisi.DAVA.value
            if "tri" in v_clean or "ipotek" in v_clean or "rehin" in v_clean:
                return RiskKategorisi.REHIN_IPOTEK_TRI.value
            if "döviz" in v_clean or "kur" in v_clean or "yabancı para" in v_clean:
                return RiskKategorisi.KUR_VE_DOVIZ_RISKI.value
            if "vergi" in v_clean or "tarhiyat" in v_clean:
                return RiskKategorisi.MEVZUAT_VERGI.value
            if "ilişkili" in v_clean:
                return RiskKategorisi.ILISKILI_TARAF.value
            if "likidite" in v_clean or "akreditif" in v_clean or "borç" in v_clean:
                return RiskKategorisi.LIKIDITE_VE_BORCLANMA.value
            if "denetçi" in v_clean or "görüş" in v_clean or "kam" in v_clean or "kilit" in v_clean:
                return RiskKategorisi.DENETCI_GORUSU_VE_KAM.value
            if "koşullu" in v_clean or "taahhüt" in v_clean:
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


class KomiteKararEgilimi(str, Enum):
    OLUMLU = "Olumlu (Kredi Tahsis Edilebilir)"
    SARTLI_OLUMLU = "Şartlı Olumlu (Ek Teminat / Kısıtlayıcı Taahhüt-Covenant İle)"
    OLUMSUZ = "Olumsuz (Yüksek Kalitatif Risk)"


class BDRRiskAnalysisReport(BaseModel):
    kullanilan_model: Optional[str] = Field(None, description="Analizi gerçekleştiren LLM modeli.")
    analiz_suresi_saniye: Optional[float] = Field(None, description="Analiz süresi (saniye).")
    is_mock_fallback: bool = Field(False, description="API çağrısı başarısız olduğu için mock fallback üretilip üretilmediği şeffaflık bayrağı.")
    fallback_reason: Optional[str] = Field(None, description="Mock fallback tetiklenme nedeni/hata mesajı.")
    firma_adi: Optional[str] = Field("Belirtilmemiş Şirket", description="BDR raporunun ait olduğu firma adı.")
    rapor_donemi: Optional[str] = Field("Belirtilmemiş Dönem", description="BDR raporlama dönemi.")
    denetim_firmasi: Optional[str] = Field(None, description="Bağımsız Denetim Kuruluşu (EY, PwC, Deloitte, KPMG vb.).")
    denetci_gorusu: Optional[DenetciGorusTuru] = Field(DenetciGorusTuru.OLUMLU, description="Bağımsız denetçinin rapor görüşü.")
    tespit_edilen_riskler: List[BDRRiskItem] = Field(default_factory=list, description="BDR'den çıkarılan kalitatif risk kalemleri.")
    genel_kredi_risk_ozeti: str = Field(..., description="Tüm risklerin toplu kredi riski özeti.")
    komite_tavsiyesi_ve_sartlar: List[str] = Field(default_factory=list, description="Kredi Komitesine önerilen şartlar ve kısıtlar.")
    karar_egilimi: KomiteKararEgilimi = Field(..., description="Genel kredi komitesi karar eğilimi.")
    analist_gerekce_metni: str = Field(..., description="Analist kalitesinde gerekçelendirilmiş komite paragrafı.")
    qa_bayraklari: List[str] = Field(default_factory=list, description="Pipeline Faz 8: kural tabanlı tutarlılık uyarıları.")

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
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if "şartlı" in v_clean or "sartli" in v_clean or "covenant" in v_clean:
                return KomiteKararEgilimi.SARTLI_OLUMLU.value
            if "olumsuz" in v_clean or "reddedil" in v_clean or "rejected" in v_clean:
                return KomiteKararEgilimi.OLUMSUZ.value
            if "olumlu" in v_clean:
                return KomiteKararEgilimi.OLUMLU.value
        return v
