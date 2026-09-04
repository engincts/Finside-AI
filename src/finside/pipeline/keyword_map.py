"""Faz 2 triyaj için `RiskKategorisi` → anahtar-kelime ileri eşlemesi.

`schemas.normalize_risk_kategorisi` içindeki geriye-eşleme mantığının ileri yönlü,
kural-tabanlı ön-filtre hali. Tek kaynak burada tutulur.
"""

from typing import Optional

from finside.models import RiskKategorisi
from finside.models.schemas import sadelestir_tr

KATEGORI_ANAHTARLARI = {
    RiskKategorisi.IC_KONTROL_ZAFIYETI: [
        "iç kontrol", "kontrol zafiyeti", "kontrol eksikliği",
    ],
    RiskKategorisi.VARLIK_DEGER_DUSUKLUGU_VE_SEREFIYE: [
        "şerefiye", "değer düşüklüğü", "değer düşüklüğü testi", "geri kazanılabilir tutar",
    ],
    RiskKategorisi.TUREV_VE_HEDGE_ISLEMLERI: [
        "türev", "forward", "vadeli döviz", "swap", "opsiyon sözleşme",
        "korunma muhasebesi", "hedge",
    ],
    RiskKategorisi.ISLETME_BIRLESMESI: [
        "işletme birleşmesi", "satın alma bedeli", "satın alınan şirket", "iktisap",
        "şirket devralma", "devralma",
    ],
    RiskKategorisi.MUHASEBE_TAHMINI_VE_HASILAT: [
        "hasılatın muhasebeleştir", "hasılat kaydı", "hasılatın kaydedilmesi",
        "muhasebe tahmini", "önemli tahmin ve varsayım",
    ],
    RiskKategorisi.FAALIYET_SUREKLILIGI_VE_SONRAKI_OLAYLAR: [
        "faaliyet sürekliliği", "süreklilik", "sonraki olay", "bilanço sonrası",
        "raporlama döneminden sonra", "going concern", "önemli belirsizlik",
        "sermaye artır", "sermaye artış",
    ],
    RiskKategorisi.KEFALET_TEMINAT: ["kefalet", "garanti", "kontrgaranti", "müteselsil"],
    # DAVA'dan önce: "kıdem tazminatı" hem "tazminat" hem "karşılık" içerdiğinden
    # aksi halde DAVA'ya kaçar.
    RiskKategorisi.KOSULLU_YUKUMLULUK: [
        "koşullu yükümlülük", "koşullu varlık", "taahhüt", "kıdem tazminatı",
        "çalışan hakları", "emeklilik yükümlülü",
    ],
    RiskKategorisi.DAVA: ["dava", "ihtilaf", "hukuki", "tazminat", "tarhiyat davası", "karşılık"],
    RiskKategorisi.REHIN_IPOTEK_TRI: [
        "trİ", "tri ", "ipotek", "rehin", "teminat", "varlık kısıt", "temlik",
    ],
    RiskKategorisi.KUR_VE_DOVIZ_RISKI: [
        "döviz", "kur riski", "yabancı para", "açık pozisyon", "kambiyo", "çevrim farkı",
        "libor", "faiz oranı riski", "faiz oranı swap",
    ],
    RiskKategorisi.LIKIDITE_VE_BORCLANMA: [
        "likidite", "akreditif", "borçlanma", "kredi sözleşme", "vade yapısı", "finansal borç",
    ],
    RiskKategorisi.ILISKILI_TARAF: [
        "ilişkili taraf", "ilişkili kuruluş", "grup içi", "üst yönetim",
        "kilit yönetici", "yönetim kuruluna sağlanan",
    ],
    RiskKategorisi.MEVZUAT_VERGI: [
        "vergi", "tarhiyat", "geçmiş yıl zarar", "ertelenmiş vergi", "mevzuat", "spk", "kgk",
    ],
    RiskKategorisi.DENETCI_GORUSU_VE_KAM: [
        "denetçi görüş", "kilit denetim", "kam", "görüşün dayanağı", "şartlı görüş",
    ],
}

BOILERPLATE_IBARELERI = [
    "sunum esasları", "muhasebe politikaları", "yeni ve revize", "standartlar ve yorumlar",
    "önemli muhasebe tahminleri", "karşılaştırmalı bilgiler", "netleştirme",
    "raporlama para birimi", "konsolidasyon esasları", "içindekiler",
    "işletmenin organizasyonu", "grup'un yapısı", "faaliyet konusu",
    "finansal tabloların onaylanması", "bölümlere göre raporlama",
]


def kategori_eslesmesi(metin: str) -> Optional[RiskKategorisi]:
    dusuk = sadelestir_tr(metin)
    for kategori, anahtarlar in KATEGORI_ANAHTARLARI.items():
        if any(anahtar in dusuk for anahtar in anahtarlar):
            return kategori
    return None


def boilerplate_mi(baslik: str) -> bool:
    dusuk = sadelestir_tr(baslik)
    return any(ibare in dusuk for ibare in BOILERPLATE_IBARELERI)
