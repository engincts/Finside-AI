from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RiskKategorisi(str, Enum):
    DENETCI_GORUSU_VE_KAM = "Bağımsız Denetçi Görüşü ve Kilit Denetim Konuları (KAM)"
    DAVA = "Dava, Hukuki İhtilaflar ve Karşılıklar"
    REHIN_IPOTEK_TRI = "Teminat, Rehin, İpotek (TRİ) ve Varlık Kısıtlamaları"
    KEFALET_TEMINAT = "Verilen Kefalet, Garanti ve Kontrgarantiler (Grup Bulaşma Riski)"
    KOSULLU_YUKUMLULUK = "Koşullu Yükümlülükler, Borçlar ve Taahhütler"
    KUR_VE_DOVIZ_RISKI = "Net Yabancı Para Açık Pozisyonu ve Kur Riski"
    LIKIDITE_VE_BORCLANMA = "Borç Vade Yapısı, Akreditif ve Likidite Riski"
    ILISKILI_TARAF = "İlişkili Taraf İşlemleri, Alacak/Borç Yoğunluğu"
    MEVZUAT_VERGI = "Vergi Tarhiyatları, Geçmiş Yıl Zararları ve Mevzuat Riskleri"
    FAALIYET_SUREKLILIGI_VE_SONRAKI_OLAYLAR = "Faaliyet Sürekliliği (Going Concern) ve Bilanço Sonrası Olaylar"
    DIGER_KALITATIF_RISK = "Diğer Kalitatif Risk Unsuarları"


class RiskDerecesi(str, Enum):
    DUSUK = "Düşük"
    ORTA = "Orta"
    YUKSEK = "Yüksek"
    KRITIK = "Kritik"


class DenetciGorusTuru(str, Enum):
    OLUMLU = "Olumlu Görüş (Unqualified Opinion)"
    SARTLI_OLUMLU = "Şartlı / Sınırlı Olumlu Görüş (Qualified Opinion)"
    OLUMSUZ = "Olumsuz Görüş (Adverse Opinion)"
    GORUS_BILDIRMEKTEN_KACINMA = "Görüş Bildirmekten Kaçınma (Disclaimer of Opinion)"


class BDRRiskItem(BaseModel):
    risk_kategorisi: RiskKategorisi = Field(
        ...,
        description="Risk kaleminin dahil olduğu ana TFRS/BDR kategorisi."
    )
    dipnot_referansi: Optional[str] = Field(
        None,
        description="Riskin ait olduğu BDR dipnot numarası ve başlığı (örn: 'Dipnot 21 - TRİ'ler')."
    )
    baslik: str = Field(
        ...,
        description="Risk kaleminin kısa ve net başlığı (örn: 'Grup Şirketi Lehine Verilen TRİ Yükü')."
    )
    detay: str = Field(
        ...,
        description="BDR dipnotundaki riskin özeti ve ayrıntıları."
    )
    tutar_bilgisi: Optional[str] = Field(
        None,
        description="Riskin TL, USD veya EUR cinsinden tutarı ve varsa ayrılan karşılık bilgisi."
    )
    etki_degerlendirmesi: str = Field(
        ...,
        description="Riskin borç ödeme kapasitesi, özkaynak eritme potansiyeli veya likidite üzerindeki kredi etkisi."
    )
    risk_derecesi: RiskDerecesi = Field(
        ...,
        description="Kredi analisti açısından riskin derece sınıfı."
    )
    kaynak_metin_alintisi: str = Field(
        ...,
        description="BDR metninden doğrudan kanıt niteliğindeki alıntı."
    )


class KomiteKararEgilimi(str, Enum):
    OLUMLU = "Olumlu (Kredi Tahsis Edilebilir)"
    SARTLI_OLUMLU = "Şartlı Olumlu (Ek Teminat / Kısıtlayıcı Taahhüt-Covenant İle)"
    OLUMSUZ = "Olumsuz (Yüksek Kalitatif Risk)"


class BDRRiskAnalysisReport(BaseModel):
    kullanilan_model: Optional[str] = Field(None, description="Analizi gerçekleştiren LLM modeli.")
    analiz_suresi_saniye: Optional[float] = Field(None, description="Analiz süresi (saniye).")
    firma_adi: Optional[str] = Field("Belirtilmemiş Şirket", description="BDR raporunun ait olduğu firma adı.")
    rapor_donemi: Optional[str] = Field("Belirtilmemiş Dönem", description="BDR raporlama dönemi (örn: 31 Aralık 2024).")
    denetim_firmasi: Optional[str] = Field(None, description="Raporu hazırlayan Bağımsız Denetim Kuruluşu (EY, PwC, Deloitte, KPMG vb.).")
    denetci_gorusu: Optional[DenetciGorusTuru] = Field(DenetciGorusTuru.OLUMLU, description="Bağımsız denetçinin rapor görüşü.")
    tespit_edilen_riskler: List[BDRRiskItem] = Field(default_factory=list, description="BDR'den çıkarılan tüm kalitatif risk kalemleri.")
    genel_kredi_risk_ozeti: str = Field(..., description="Tüm risklerin toplu kredi riski özeti.")
    komite_tavsiyesi_ve_sartlar: List[str] = Field(default_factory=list, description="Kredi Komitesine önerilen şartlar ve kısıtlar (Covenants).")
    karar_egilimi: KomiteKararEgilimi = Field(..., description="Genel kredi komitesi karar eğilimi.")
    analist_gerekce_metni: str = Field(..., description="Analist kalitesinde gerekçelendirilmiş komite paragrafı.")
