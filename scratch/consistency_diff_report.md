# Pipeline Run-to-Run Tutarsizlik ve Varyasyon Raporu

**Test Edilen BDR:** `data/bdr_samples/0f7bfcfebe7f422aa56aba17a28c610c.txt`
**Kosum Sayisi:** 3

## 📌 Risk Karsilastirma Matrisi (Diff Tablosu)

| No | Canonical Risk Konusu | Katilim Orani | Kosum 1 | Kosum 2 | Kosum 3 |
|---|---|---|---|---|
| 1 | Dipnot 7 - Akreditif Borçları ve Likidite Ris | 1/3 | VAR (Borç Vade Yapıs) | YOK | YOK |
| 2 | Dipnot 8 - İlişkili Taraflardan Ticari Borçla | 2/3 | VAR (İlişkili Taraf ) | YOK | VAR (İlişkili Taraf ) |
| 3 | Dipnot 10 - Vadeli Döviz İşlemleri ve Kur Ris | 1/3 | VAR (Net Yabancı Par) | YOK | YOK |
| 4 | Dipnot 7 - Kısa Vadeli Borçlanmaların Tamamen | 1/3 | VAR (Borç Vade Yapıs) | YOK | YOK |
| 5 | Dipnot 22 - Kıdem Tazminatı ve Çalışanlara Sa | 1/3 | VAR (Koşullu Yükümlü) | YOK | YOK |
| 6 | Net Yabancı Para Pozisyonu ve Kur Riski | 3/3 | VAR (Net Yabancı Par) | VAR (Net Yabancı Par) | VAR (Net Yabancı Par) |
| 7 | Grup'un Verdiği TRİ'ler | 3/3 | VAR (Teminat, Rehin,) | VAR (Teminat, Rehin,) | VAR (Teminat, Rehin,) |
| 8 | İhracat Taahhütleri | 1/3 | VAR (Koşullu Yükümlü) | YOK | YOK |
| 9 | Kıdem Tazminatı Karşılığı | 2/3 | VAR (Koşullu Yükümlü) | YOK | VAR (Koşullu Yükümlü) |
| 10 | Ertelenmiş Vergi | 3/3 | VAR (Vergi Tarhiyatl) | VAR (Vergi Tarhiyatl) | VAR (Vergi Tarhiyatl) |
| 11 | Bilanço Tarihinden Sonraki Olaylar | 2/3 | VAR (Faaliyet Sürekl) | YOK | VAR (Faaliyet Sürekl) |
| 12 | Akreditif Tutarı | 1/3 | VAR (Koşullu Yükümlü) | YOK | YOK |
| 13 | Forward/Opsiyon Kullanımı ile Kur Riskine Kar | 1/3 | VAR (Türev ve Hedge ) | YOK | YOK |
| 14 | Vergi Gideri | 1/3 | VAR (Vergi Tarhiyatl) | YOK | YOK |
| 15 | Alacak teminat mektubu | 1/3 | VAR (İlişkili Taraf ) | YOK | YOK |
| 16 | Alacak sigortası teminatı | 1/3 | VAR (İlişkili Taraf ) | YOK | YOK |
| 17 | 1.931.455 TL Vadeli Mevduatlar ve 520.007 TL  | 1/3 | YOK | VAR (Net Yabancı Par) | YOK |
| 18 | 1.981.211 TL Alınan Avanslar ve 7.517 TL Türe | 2/3 | YOK | VAR (Koşullu Yükümlü) | VAR (Koşullu Yükümlü) |
| 19 | Ticari Borçlar ve Akreditif Kullanımı | 1/3 | YOK | VAR (Borç Vade Yapıs) | YOK |
| 20 | Grup'un Verdiği 127.439 Milyon TL TRİ Yükü | 1/3 | YOK | VAR (Teminat, Rehin,) | YOK |
| 21 | 225.098 Bin USD Ihracat Taahhüdü | 2/3 | YOK | VAR (Koşullu Yükümlü) | VAR (Koşullu Yükümlü) |
| 22 | Grup'un Faiz Oranı Riski Yönetimi | 1/3 | YOK | VAR (Net Yabancı Par) | YOK |
| 23 | Borusan Birleşik Boru Fabrikaları Sanayi ve T | 1/3 | YOK | VAR (Faaliyet Sürekl) | YOK |
| 24 | Dipnot 21 - 2.321.260 TL Kendi Tüzel Kişiliği | 2/3 | YOK | VAR (Teminat, Rehin,) | VAR (Teminat, Rehin,) |
| 25 | Topluluk Denetimi ve İlişkili Taraf Alacaklar | 1/3 | YOK | YOK | VAR (İlişkili Taraf ) |
| 26 | Going Concern Şüphesi | 1/3 | YOK | YOK | VAR (Faaliyet Sürekl) |
| 27 | Dipnot 7 - Kısa Vadeli ve Uzun Vadeli Borçlar | 1/3 | YOK | YOK | VAR (Borç Vade Yapıs) |
| 28 | Dipnot 3 - Berg EuroPipe Holding Satın Alımı  | 1/3 | YOK | YOK | VAR (İşletme Birleşm) |
| 29 | Dipnot 38 - İşletme Birleşmesi: BMB Holding D | 1/3 | YOK | YOK | VAR (İşletme Birleşm) |
| 30 | İlişkili Taraflardan Diğer Alacaklar 720 Bin  | 1/3 | YOK | YOK | VAR (İlişkili Taraf ) |
| 31 | Dipnot 35 - Türev ve Hedge İşlemleri (Forward | 1/3 | YOK | YOK | VAR (Türev ve Hedge ) |