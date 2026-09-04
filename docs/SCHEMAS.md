# 📋 Finside AI — Veri Şemaları ve Pydantic Modelleri Rehberi

Bu doküman, sistemde modeller arası veri transferini ve çıktı yapılandırmasını sağlayan Pydantic veri modellerini açıklar.

---

## 🏢 1. `BDRRiskAnalysisReport` (Nihai Rapor Şeması)

Tüm modellerin veya Multi-Agent pipeline'ın ürettiği ana çıktıdır:

| Alan Adı | Tip | Açıklama |
| :--- | :--- | :--- |
| `firma_adi` | `str` | Analiz edilen şirketin ticari unvanı. |
| `rapor_donemi` | `str` | BDR rapor dönemi (Örn: 31 Aralık 2024). |
| `denetim_firmasi` | `str` | Bağımsız denetim kuruluşu (EY, PwC, Deloitte vb.). |
| `denetci_gorusu` | `DenetciGorusTuru` | Olumlu / Şartlı Olumlu / Olumsuz / Kaçınma. |
| `tespit_edilen_riskler` | `List[BDRRiskItem]` | Konsolide edilmiş kalitatif risk kalemleri listesi. |
| `ml_sayisal_kredi_skoru`| `float` | ML.NET sayısal makine öğrenmesi skoru (0-100). |
| `sayisal_skor_kategorisi`| `str` | Sayısal risk seviyesi (Düşük / Orta / Yüksek). |
| `finansal_rasyo_ozeti` | `FinansalRasyoOzeti` | Likidite, kaldıraç, cari oran ve net borç/FAVÖK rasyoları. |
| `karar_egilimi` | `KomiteKararEgilimi`| 5 Seviyeli Kredi Komitesi Tahsis Seviyesi kararı. |
| `komite_tavsiyesi_ve_sartlar` | `List[str]` | Kısıtlayıcı taahhütler ve teminat şartları (Covenants). |
| `analist_gerekce_metni` | `str` | 3-4 paragraflık derin kıdemli analist gerekçelendirme yazısı. |

---

## 🏛️ 2. `KomiteKararEgilimi` (Bankacılık Standardında Karar Tiyerleri)

* **`OLUMLU`**: Olumlu (Koşulsuz Tahsis / Standart Limit)
* **`SARTLI_TAAHHUTLU`**: Şartlı Olumlu (Finansal Covenant / Taahhüt Şartlı)
* **`SARTLI_TEMINATLI`**: Şartlı Olumlu (Ek Teminat / Limit Kısıtlaması Bağlı)
* **`ASKIDA_EK_INCELEME`**: Askıda (Ek Denetim / Hukuki Görüş İsteniyor)
* **`OLUMSUZ`**: Olumsuz (Yüksek Kalitatif Risk / Red)
* **`BELIRSIZ`**: Belirsiz (Model Karar Üretmedi)

---

## ⚠️ 3. `BDRRiskItem` (Tekil Risk Kalemi Şeması)

| Alan Adı | Tip | Varsayılan Değer | Açıklama |
| :--- | :--- | :--- | :--- |
| `risk_kategorisi` | `RiskKategorisi` | `DIGER_KALITATIF_RISK` | Ait olduğu ana TFRS/BDR kategorisi. |
| `dipnot_referansi` | `str` | `None` | Özgün BDR dipnot numarası. |
| `baslik` | `str` | `"Kalitatif Risk Kalemi"` | Kısa ve net spesifik başlık. |
| `detay` | `str` | `"Dipnot detayı..."` | Riskin detaylı açıklaması. |
| `tutar_bilgisi` | `str` | `None` | Parasal tutar (TL/USD/EUR). |
| `etki_degerlendirmesi`| `str` | `"Borç ödeme etkisi..."` | Borç ödeme ve likiditeye etkisi. |
| `risk_derecesi` | `RiskDerecesi` | `ORTA` | Düşük / Orta / Yüksek / Kritik. |
| `kaynak_metin_alintisi`| `str` | `"BDR alıntısı..."` | Metindeki TEK ve net kanıt cümlesi. |
| `ek_kanitlar` | `List[str]` | `[]` | Varsa ilave kanıt cümleleri parçası. |
| `dogrulanmadi` | `bool` | `False` | Grounding doğrulama sonucu. |
| `kaynak_modeller` | `List[str]` | `[]` | Tespit eden modeller (Örn: `["gpt-4o"]` veya `["critic"]`). |

---

## 📊 4. `FinansalRasyoOzeti` (Sayısal Rasyo Şeması)

OpenAI Strict Mode ve Gemini API uyumluluğu için özel tipleştirilmiş modeldir:
- `cari_oran`: Dönen Varlıklar / Kısa Vadeli Yükümlülükler.
- `likidite_orani`: Asit-test oranı.
- `kaldirac_orani`: Toplam Borç / Pasif Toplamı.
- `net_borc_favok`: Net Borç / FAVÖK çarpanı.
- `ozkaynak_orani`: Özkaynak / Pasif Toplamı.
- `net_doviz_pozisyonu`: Net yabancı para açık/fazla pozisyonu.
