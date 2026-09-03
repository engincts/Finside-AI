"""Faz 2 triyaj için `RiskKategorisi` → anahtar-kelime ileri eşlemesi.

`schemas.normalize_risk_kategorisi` içindeki geriye-eşleme mantığının ileri yönlü,
kural-tabanlı ön-filtre hali. Tek kaynak burada tutulur.
"""

from typing import Optional

from finside.models import RiskKategorisi

KATEGORI_ANAHTARLARI = {
    RiskKategorisi.FAALIYET_SUREKLILIGI_VE_SONRAKI_OLAYLAR: [
        "faaliyet sürekliliği", "süreklilik", "sonraki olay", "bilanço sonrası",
        "raporlama döneminden sonra", "going concern", "birleşme", "devralma",
    ],
    RiskKategorisi.KEFALET_TEMINAT: ["kefalet", "garanti", "kontrgaranti", "müteselsil"],
    RiskKategorisi.DAVA: ["dava", "ihtilaf", "hukuki", "tazminat", "tarhiyat davası", "karşılık"],
    RiskKategorisi.REHIN_IPOTEK_TRI: [
        "trİ", "tri ", "ipotek", "rehin", "teminat", "varlık kısıt", "temlik",
    ],
    RiskKategorisi.KUR_VE_DOVIZ_RISKI: [
        "döviz", "kur riski", "yabancı para", "açık pozisyon", "kambiyo", "çevrim farkı",
    ],
    RiskKategorisi.LIKIDITE_VE_BORCLANMA: [
        "likidite", "akreditif", "borçlanma", "kredi sözleşme", "vade yapısı", "finansal borç",
    ],
    RiskKategorisi.ILISKILI_TARAF: ["ilişkili taraf", "ilişkili kuruluş", "grup içi"],
    RiskKategorisi.MEVZUAT_VERGI: [
        "vergi", "tarhiyat", "geçmiş yıl zarar", "ertelenmiş vergi", "mevzuat", "spk", "kgk",
    ],
    RiskKategorisi.DENETCI_GORUSU_VE_KAM: [
        "denetçi görüş", "kilit denetim", "kam", "görüşün dayanağı", "şartlı görüş",
    ],
    RiskKategorisi.KOSULLU_YUKUMLULUK: ["koşullu yükümlülük", "koşullu varlık", "taahhüt"],
}

BOILERPLATE_IBARELERI = [
    "sunum esasları", "muhasebe politikaları", "yeni ve revize", "standartlar ve yorumlar",
    "önemli muhasebe tahminleri", "karşılaştırmalı bilgiler", "netleştirme",
    "raporlama para birimi", "konsolidasyon esasları", "içindekiler",
    "işletmenin organizasyonu", "grup'un yapısı", "faaliyet konusu",
    "finansal tabloların onaylanması", "bölümlere göre raporlama",
]


def kategori_eslesmesi(metin: str) -> Optional[RiskKategorisi]:
    dusuk = metin.lower()
    for kategori, anahtarlar in KATEGORI_ANAHTARLARI.items():
        if any(anahtar in dusuk for anahtar in anahtarlar):
            return kategori
    return None


def boilerplate_mi(baslik: str) -> bool:
    dusuk = baslik.lower()
    return any(ibare in dusuk for ibare in BOILERPLATE_IBARELERI)
