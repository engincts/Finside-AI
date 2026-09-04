# Pipeline Run-to-Run Tutarsizlik ve Varyasyon Raporu

**Test Edilen BDR:** `data/bdr_samples/0f7bfcfebe7f422aa56aba17a28c610c.txt`
**Kosum Sayisi:** 3

## 📌 Risk Karsilastirma Matrisi (Diff Tablosu)

| No | Canonical Risk Konusu | Katilim Orani | Kosum 1 | Kosum 2 | Kosum 3 |
|---|---|---|---|---|
| 1 | Hasılatın Finansal Tablo Kaydedilmesi | 3/3 | VAR (Bağımsız Denetç) | VAR (Bağımsız Denetç) | VAR (Bağımsız Denetç) |
| 2 | Topluluk Denetimi | 3/3 | VAR (Bağımsız Denetç) | VAR (Bağımsız Denetç) | VAR (Bağımsız Denetç) |
| 3 | İlişkili Taraflardan Ticari Alacaklar | 3/3 | VAR (İlişkili Taraf ) | VAR (İlişkili Taraf ) | VAR (İlişkili Taraf ) |
| 4 | İlişkili Taraflara Ticari Borçlar | 3/3 | VAR (İlişkili Taraf ) | VAR (İlişkili Taraf ) | VAR (İlişkili Taraf ) |
| 5 | İlişkili Taraflardan Diğer Dönen Varlıklar | 1/3 | VAR (İlişkili Taraf ) | YOK | YOK |
| 6 | İlişkili Taraflardan Alacaklar | 1/3 | VAR (İlişkili Taraf ) | YOK | YOK |
| 7 | 13 Nisan 2023 Tarihinde Yapılan Berg EuroPipe | 3/3 | VAR (İşletme Birleşm) | VAR (İşletme Birleşm) | VAR (İşletme Birleşm) |
| 8 | Bağımsız Denetçi Görüşü | 1/3 | VAR (Bağımsız Denetç) | YOK | YOK |
| 9 | Akreditifli Ticari Borçlar: 1.892.914 TL (53. | 1/3 | VAR (Borç Vade Yapıs) | YOK | YOK |
| 10 | FX Forward Türev Gelir Tahakkuku 7.517 Bin TL | 1/3 | VAR (Türev ve Hedge ) | YOK | YOK |
| 11 | Uzun Vadeli Borçlanmalarda LIBOR Bağlı Faiz O | 1/3 | VAR (Borç Vade Yapıs) | YOK | YOK |
| 12 | Kısa Vadeli Borçların Tamamen Teminatsız Olma | 2/3 | VAR (Borç Vade Yapıs) | VAR (Borç Vade Yapıs) | YOK |
| 13 | Kısa Vadeli Döviz Borçlanmalarının Kur ve Fai | 1/3 | VAR (Borç Vade Yapıs) | YOK | YOK |
| 14 | BMB Holding A.Ş. Devri ve Sermaye Artırımı | 1/3 | VAR (Faaliyet Sürekl) | YOK | YOK |
| 15 | Dipnot 38 - BMB Holding Devir Alınması ve 141 | 3/3 | VAR (İşletme Birleşm) | VAR (İşletme Birleşm) | VAR (İşletme Birleşm) |
| 16 | Dipnot 21 - Diğer 3. Kişilere ve Grup Şirketl | 3/3 | VAR (Teminat, Rehin,) | VAR (Teminat, Rehin,) | VAR (Teminat, Rehin,) |
| 17 | Dipnot 21 - Kendi Tüzel Kişiliği Adına Vermiş | 3/3 | VAR (Teminat, Rehin,) | VAR (Teminat, Rehin,) | VAR (Teminat, Rehin,) |
| 18 | Dipnot 21 - Tam Konsolidasyon Kapsamındaki Or | 3/3 | VAR (Teminat, Rehin,) | VAR (Teminat, Rehin,) | VAR (Teminat, Rehin,) |
| 19 | Teminat, Rehin, İpotek Oranı Özsermayeye | 1/3 | VAR (Teminat, Rehin,) | YOK | YOK |
| 20 | Dipnot 22 - Kıdem Tazminatı Karşılığı 219.890 | 3/3 | VAR (Koşullu Yükümlü) | VAR (Koşullu Yükümlü) | VAR (Koşullu Yükümlü) |
| 21 | İhracat Taahhütleri | 3/3 | VAR (Koşullu Yükümlü) | VAR (Borç Vade Yapıs) | VAR (Koşullu Yükümlü) |
| 22 | Dipnot 20 - Net Yabancı Para Pozisyonu (1.959 | 2/3 | VAR (Net Yabancı Par) | VAR (Net Yabancı Par) | YOK |
| 23 | Dipnot 21 - Açık Akreditif Tutarı 48.070 bin  | 3/3 | VAR (Borç Vade Yapıs) | VAR (Borç Vade Yapıs) | VAR (Koşullu Yükümlü) |
| 24 | Üst Yönetim Kadrosuna Yapılan Ödemeler | 1/3 | VAR (İlişkili Taraf ) | YOK | YOK |
| 25 | Dipnot 32 - Ertelenmiş Vergi Yükümlülüğü 2.53 | 2/3 | VAR (Vergi Tarhiyatl) | VAR (Vergi Tarhiyatl) | YOK |
| 26 | Dipnot 32 - Kullanılamamış Zararlar 3.513.255 | 1/3 | VAR (Vergi Tarhiyatl) | YOK | YOK |
| 27 | Likidite Riski – Nakit ve Kısa Vadeli Yükümlü | 1/3 | YOK | VAR (Borç Vade Yapıs) | YOK |
| 28 | Dipnot 10 - 7.517 TL Vadeli Döviz İşlemlerind | 1/3 | YOK | VAR (Türev ve Hedge ) | YOK |
| 29 | Akreditif Borçları | 1/3 | YOK | VAR (Borç Vade Yapıs) | YOK |
| 30 | Berg EuroPipe Satın Alımına İlişkin Vadeli Öd | 1/3 | YOK | VAR (İşletme Birleşm) | YOK |
| 31 | Kısa Vadeli Teminatsız Döviz Borçlanmalar | 1/3 | YOK | VAR (Borç Vade Yapıs) | YOK |
| 32 | Dipnot 34 - Üst Yönetim Kadrosuna Ödenen Ücre | 1/3 | YOK | VAR (İlişkili Taraf ) | YOK |
| 33 | Dipnot 35 - Döviz Forward ve Opsiyon Kullanım | 1/3 | YOK | VAR (Türev ve Hedge ) | YOK |
| 34 | Kilit Denetim Konuları | 1/3 | YOK | VAR (Bağımsız Denetç) | YOK |
| 35 | İç Kontrol Zafiyetleri | 1/3 | YOK | VAR (Bağımsız Denetç) | YOK |
| 36 | Faaliyet Sürekliliği | 1/3 | YOK | VAR (Faaliyet Sürekl) | YOK |
| 37 | Kısa Vadeli Borçlanmaların Döviz ve Faiz Oran | 1/3 | YOK | YOK | VAR (Net Yabancı Par) |
| 38 | Uzun Vadeli Borçlanmaların Faiz Oranları | 1/3 | YOK | YOK | VAR (Net Yabancı Par) |
| 39 | Vadeli Döviz İşlemleri Gelir Tahakkukları | 1/3 | YOK | YOK | VAR (Türev ve Hedge ) |
| 40 | Dipnot 2 - Kur Farkları ve Döviz Riski | 1/3 | YOK | YOK | VAR (Net Yabancı Par) |
| 41 | Çalışanlara Sağlanan Faydalara İlişkin Karşıl | 1/3 | YOK | YOK | VAR (Koşullu Yükümlü) |
| 42 | Net Yabancı Para Pozisyonu ve Kur Riski | 1/3 | YOK | YOK | VAR (Net Yabancı Par) |
| 43 | Hasılatın Finansal Tablolara Kaydedilmesi | 1/3 | YOK | YOK | VAR (Bağımsız Denetç) |