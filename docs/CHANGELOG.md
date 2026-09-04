# Değişiklik Günlüğü

Biçim: her giriş bir çalışma oturumunu özetler. Tarihler mutlaktır.

---

## 2026-09-04 — Model seçim ekranı: uygunluk sınıflandırması + bilinen sorunlar

Benchmark koşumunda `claude-sonnet-4-5` (32K çıktı tavanı aşıldı) ve `hf-deepseek-v3`
(HF router yalnızca 'conversational' sunuyor) hata verdi. Kullanıcı bu sınırları model
seçim ekranından görebilsin istiyor.

- **`config.json`**: modellere opsiyonel `durum` (`ok` | `riskli` | `kullanilamaz`) +
  `durum_notu` (serbest metin). `hf-deepseek-v3` → `kullanilamaz`; `claude-sonnet-4-5`
  → `riskli` + `max_tokens` 32000 → 64000, `max_input_chars` 180000.
- **`providers/anthropic_provider.MAX_OUTPUT_TOKENS`** 32000 → 64000 (Sonnet 4.5 native,
  beta başlığı gerektirmez).
- **`config.model_girdi_siniri`** + **`config.model_bdr_degerlendirmesi(cfg, bdr_krk)`**
  (yeni): seçili BDR için model başına rozet (✅/⚠️/❌), tek satır özet (girdi sınırı, bu
  BDR kaç parça, çıktı tavanı, sağlayıcı) ve uyarı listesi. ⚠️ = bilinen risk / çok düşük
  çıktı tavanı (<8k) / aşırı parçalanma (>12); normal chunk'lama badge'i bozmaz, bilgi
  satırında görünür.
- **`ui/sidebar.py`**: her model checkbox'ı `{rozet} {ad}` + altında özet + uyarılar;
  `kullanilamaz` model seçilirse analiz dışı bırakılır (kırmızı uyarı).
- **`ui/tabs.py`** (pipeline ensemble multiselect): `kullanilamaz` modeller listeden
  çıkarıldı; seçenek etiketi rozet + özet gösteriyor, seçili modellerin uyarıları altta.

Doğrulama: `py_compile` + UI import + `model_bdr_degerlendirmesi` büyük (612k) / küçük
(45k) BDR ile denendi. `hf-deepseek-v3` HF-provider routing düzeltmesi (conversational
görev zorlama) canlı test gerektirdiğinden ertelendi.

---

## 2026-09-04 — Kalite kalibrasyonu: taksonomi + tekrar-dedup + alıntı bütünlüğü

Borusan 2024 BDR altı turda gerçek API ile koşuldu (24 → 23 → 35 → 19 → 32 → 32 risk).
Mimari doğru, mock fallback yok. **Not:** `config.json`'da `pipeline` rolleri şu an
tümü `gpt-oss-120b` (task dokümanındaki `gpt-4o-mini` varsayımı güncel değil) — critic
de gpt-oss-120b, bu critic'in agresif "eksik ekleme" davranışını açıklıyor.

**6. tur (bu oturumun düzeltmeleri sonrası):** SORUN 1/1C ✅ **"Diğer" 0 kalem**, Kıdem
Tazminatı → Koşullu Yükümlülükler, yeni enum adı ("…Kur ve Faiz Oranı Riski") aktif.
SORUN 2C roll-up kalemi raporda YOK. SORUN 3 (orijinal "..." hali) ✅ kalıcı. 3 ana
sorun kapandı.

**Kalan ince ayar:** SORUN 3B (grounding sayı/boşluk format toleransı — bu oturumda
çözüldü), SORUN 2D (critic tablo satırı kazıyor + map'i 2x'liyor — açık, kullanıcı
öncelik vermedi).

### SORUN 1 — "Diğer Kalitatif Risk" %33 (8/24) — ✅ ÇÖZÜLDÜ (2. tur doğrulandı)

`schemas.RiskKategorisi` enum'ına 5 yeni kategori: `VARLIK_DEGER_DUSUKLUGU_VE_SEREFIYE`,
`MUHASEBE_TAHMINI_VE_HASILAT`, `IC_KONTROL_ZAFIYETI`, `TUREV_VE_HEDGE_ISLEMLERI`,
`ISLETME_BIRLESMESI` (hepsi `DIGER_KALITATIF_RISK`'ten önce; "Diğer" son sırada fallback).

- **`schemas.normalize_risk_kategorisi`** + **`pipeline/keyword_map.KATEGORI_ANAHTARLARI`**:
  yeni kategoriler için geri/ileri anahtar-kelime eşlemesi (şerefiye, iç kontrol,
  türev/forward/hedge, birleşme/satın alma, hasılat). `türev` kontrolü `döviz`'den ÖNCE.
  `birleşme`/`devralma` FAALIYET'ten çıkarılıp ISLETME_BIRLESMESI'ye; FAALIYET'e
  `önemli belirsizlik` eklendi.
- **`prompts/bdr_analyst_v1.md`**: kategori listesine 10-14. maddeler + madde 9 notu.

**2. tur (23 risk):** "Diğer" hiç yok. Yeni kategoriler aktif ve doğru.

### SORUN 1B — 3. turda kısmi nüks (%33 → %11, 4/35 kalem) — ✅ ÇÖZÜLDÜ (4. tur: "Diğer" 0)

3. tur çıktısında 4 kalem hâlâ yanlış kategoride (biri — Sermaye Artırımı — önceki turda
DOĞRU kategorideydi → miscategorization tutarsız).

- **`schemas.normalize_risk_kategorisi`** + **`keyword_map`**:
  - `üst yönetim` / `kilit yönetici` / `yönetim kurulu ücret` → `ILISKILI_TARAF`
    (IAS 24). Bu kontrol `kur` kontrolünden ÖNCE ("yönetim kurulu" → "kur" çakışmasını
    önlemek için).
  - `libor` / `faiz oran(ı)` / `faiz riski` → `KUR_VE_DOVIZ_RISKI`.
  - `sermaye artır` / `sermaye artış` → `FAALIYET_SUREKLILIGI_VE_SONRAKI_OLAYLAR`.
- **`prompts/bdr_analyst_v1.md`**: madde 5'e "faiz oranı/Libor buraya", madde 7'ye
  "üst yönetim ücretleri IAS 24 → İlişkili Taraf", madde 9'a "sermaye artırımı = bilanço
  sonrası olaylar, her koşumda aynı yer" notları. Yeni ilke: **"Risk ≠ Bilanço Kalemi"**
  — `etki_degerlendirmesi`'ne somut bir borç ödeme/likidite/teminat etkisi
  yazılamıyorsa kalem `tespit_edilen_riskler`'e girmez ("Diğer Dönen Varlıklar: X TL"
  türü salt rakam bildirimi risk değil).

### SORUN 2 — Reconciler/dedup birebir-tekrarı kaçırıyor — 🔴 KÖK NEDEN DÜZELTİLDİ

1. tur: alt-küme tekrarı (#7 ⊇ #14). 3. tur daha temel kanıt: *"İlişkili Taraflardan
Ticari Alacaklar" (4.156 TL)* vs *"İlişkili taraflardan ticari alacak" (4.156 bin TL)* —
aynı gerçek, aynı rakam, iki ayrı kalem. Aynısı ticari borçlarda (116.737).
Kök neden: `reconciler._anahtar` (ve `dedupe.dedup_risk_dicts`) **birebir string**
eşleşmesi arıyordu; Türkçe çoğul eki (-lar/-ler) + birim yazımı ("TL" vs "bin TL")
string'i eşitlemiyor → mekanik ön-birleştirme kaçırıyor.

- **`config.BASLIK_BENZERLIK_ESIGI = 90`** (yeni sabit). Ölçüm: "alacaklar"↔"alacak"
  ≈96, "borçlar"↔"borç" ≈92 (birleşmeli); "alacaklar"↔"borçlar" ≈86 (ayrı kalmalı).
  90 bu ikisini ayırıyor.
- **`dedupe.ayni_baslik_index`** (yeni, public): rapidfuzz `token_sort_ratio ≥ eşik`
  ile ilk eşleşen aday indeksi. reconciler + critic + `dedup_risk_dicts` üçü de bunu
  kullanıyor (tek kaynak).
- **`pipeline/reconciler.py`**: `_anahtar` (birebir dict-anahtar) → `mekanik_birlestir`
  eşik-bazlı liste kümelemesi; `uzlastir` içindeki `kaynak_modeller` haritası ve
  `geri_eklenen` de fuzzy.
- **`pipeline/critic.py`**: `_kapsanmayan` (ipucu üretimi) ve critic'in kendi eklediği
  kalemi taslakla karşılaştırması artık fuzzy — near-dup'ı hiç eklememesi için
  (re-add döngüsünün kaynağı buydu).
- **`dedupe.dedup_risk_dicts`**: aynı fuzzy kümeleme (global sentez dedup'ı da aynı
  hatayı taşıyordu; 3. tur çiftleri buradan da geçmişti).
- **`prompts/reconciler_v1.md`**: somut örnek ("... 4.156 TL" ≡ "... 4.156 bin TL").
- Alt-küme prompt maddeleri (1. tur) `reconciler_v1.md` + `critic_v1.md`'de duruyor.
  Deterministik `dedupe.is_subset()` hâlâ Faz 11.5.

**4. tur:** "birebir ikiz başlık" deseni YOK (5 İlişkili Taraf kaleminden 4'ü gerçekten
ayrı bilanço satırı — 4.156 / 116.737 / 720 / 1.499 bin TL, meşru). Fuzzy dedup tuttu.

### SORUN 2C — "roll-up/özet" kalemi — 🟢 DETERMİNİSTİK ÇÖZÜM (prompt yetmedi, 3 kez nüksetti)

*"İlişkili taraflardan ticari alacak ve borç bakiyeleri"* (4.156 + 116.737 bin TL) =
listedeki 1. ve 2. kalemin rakamları birlikte. **4., 5. VE 7. turda tekrar etti** →
prompt talimatı bu spesifik deseni güvenilir bastıramıyor.

- **Prompt (4. turda eklendi):** `reconciler_v1.md` + `critic_v1.md` "roll-up sayma/
  ekleme" maddesi + somut örnek; `synthesis_v1.md` "konsolidasyonu özet metnine yaz"
  notu. Bunlar duruyor ama tek başına yetmiyor.
- **`dedupe.is_rollup_of(aday, digerleri) -> bool`** (deterministik predikat) +
  **`dedupe.rollup_ele(riskler)`** (onun üstünde liste filtresi). `synthesis.sentezle`
  içinde `dedup_risk_dicts` sonrası çağrılıyor. `tutar_bilgisi`+`detay`+`baslik`'ten 4+
  haneli sayıları (yıl hariç, ayıraç temizlenir) çıkarır: bir kalemin **HER** sayısı,
  aynı kategorideki başka ≥2 kalemde de geçiyorsa (kendine özgü hiç tutar getirmiyor)
  → roll-up. Tekil kalemler ham tablo satırından fazladan sayı taşısa bile çalışır
  (aday ⊆ diğer DEĞİL, aday'ın her sayısı ≥1 diğerinde aranır).
- "Azami Kredi Riski" gibi kendine özgü tutarı (2.356.131) olan kalemler korunur.
- Birim test (`check_rollup.py`, 4/4): kanonik roll-up (tekiller fazla sayılı) 4→3;
  regresyon — Azami Kredi Riski korunur, tek kapsayan elenmez, farklı kategori kapsamaz.
- **Not — `is_rollup_of()` = task dokümanındaki isim.** 5. turda "yapılacak" diye
  işaretlenmişti; 6. turda `rollup_ele` olarak eklendi, bu turda predikat ismi ayrıldı.

### SORUN 1C — 2 yeni "Diğer" boşluğu (5. tur) — ✅ ÇÖZÜLDÜ

*Faiz Oranı Riski* (Libor'dan bağımsız) ve *Kıdem Tazminatı Karşılığı* → "Diğer".
Kök neden: strict-şema model `risk_kategorisi`'ni doğrudan "Diğer" seçince
`normalize_risk_kategorisi` (yalnızca enum-dışı serbest metinde çalışır) baypas oluyor.

- **Enum:** `KUR_VE_DOVIZ_RISKI` değeri → *"Net Yabancı Para Pozisyonu, Kur ve Faiz
  Oranı Riski"*. Artık "Faiz Oranı Riski" ilk-döngü substring eşleşmesiyle doğru gidiyor.
- **`normalize_risk_kategorisi` + `keyword_map`:** `kıdem tazminatı` / `çalışan hakları`
  / `emeklilik yükümlülü` → `KOSULLU_YUKUMLULUK`. keyword_map'te DAVA'dan ÖNCE
  ("kıdem tazminatı" hem "tazminat" hem "karşılık" içerdiğinden aksi halde DAVA'ya kaçar).
- **`synthesis._kategori_kurtar`** (yeni): kategori "Diğer" ise `baslik`+`detay`'ı
  `keyword_map.kategori_eslesmesi`'nden geçirip kurtarmayı dener. `rollup_ele` sonrası
  çağrılıyor.
- **`prompts/bdr_analyst_v1.md`:** madde 3'e kıdem tazminatı notu, madde 5 başlığı
  "…Kur ve Faiz Oranı Riski".
- **Doyum noktası:** "Diğer" oranı %33→%11→%6 yakınsıyor. Bundan sonra tekil kalem için
  YENİ kategori açılmayacak; %5-10 "kabul edilebilir" eşik. SORUN 1 hattı kapandı.

### SORUN 2D — critic map çıktısını 2x şişiriyor + finansal tablo satırı kazıyor — 🔴 AÇIK

6. tur kanıtı: 32 kalemin **16'sı `Tespit Eden Modeller: critic`**. Critic'in eklediği
ilk 7 kalemin `kaynak_metin_alintisi`'i düz ham finansal tablo satırı:
- #1 `"Hasılat 25  55.065.658  42.175.476  1.689.466  1.741.173"`
- #4 `"Türev Araçlar 10  7.517  13.637  213  463"`
- #7 `"Net Dönem Karı (226.612)"`

Bunlar denetim RİSK açıklaması değil, bilançonun kendisi. Ayrıca critic map kalemlerini
farklı kelimelerle tekrar yazıyor (Türev 7.517: #4 critic + #11 gpt-oss + #27 gpt-oss)
— fuzzy başlık-dedup @90 ("Türev Araçların Pozisyonları" vs "Vadeli döviz forward
işlemleri") ve `rollup_ele` (tek sayı, roll-up değil) yakalamıyor.

**Önerilen (henüz uygulanmadı):**
- `critic_v1.md`: "verilen metin finansal tablo satırları içerebilir — ham sayı satırını
  ('Hasılat 25 55.065.658 …') EKLEME; yalnızca düz cümleyle yazılmış dipnot açıklaması";
  "bölüm başına EN FAZLA 1-2".
- `config.max_critic_turu` 2 → 1.
- Deterministik "tablo-satırı alıntısı" filtresi (alıntı >%55 rakam/boşluk & cümle yok →
  ele) — critic çıktısına uygula.

### Ek düzeltme — Türkçe "İ" küçük harf quirk'i (SORUN 1/1B'nin ortak kökü)

Python'da `"İ".lower()` araya `U+0307` combining nokta koyuyor → `"ilişkili"`,
`"işletme"`, `"ipotek"` gibi i-başlı anahtar kelimeler büyük-İ ile başlayan
başlık/etiketlere eşleşmiyordu, kalem sessizce "Diğer"e / triyajda LLM'e düşüyordu.
`schemas.sadelestir_tr` (yeni) bu noktayı arındırıyor; `normalize_risk_kategorisi`
(iki taraf) ve `keyword_map.kategori_eslesmesi` / `boilerplate_mi` bunu kullanıyor.

### SORUN 3 — Alıntılar "..." ile birleştirilmiş özetler — ✅ KAPANDI (3. + 4. tur stabil)

2. tur: QA "Risklerin %52'si doğrulanamadı" bayrağı. Model metnin uzak noktalarını "..."
ile birleştirip tek "birebir alıntı" sunuyor → `partial_ratio` ardışık bulamıyor.

- **`prompts/bdr_analyst_v1.md` + `critic_v1.md` + `reconciler_v1.md`**: "Tek Ardışık
  Alıntı" maddesi — "..." ile birleştirme YASAK; temsili tek parça, kalan rakamlar
  `detay`'a.
- **`pipeline/grounding.py`**: `ground_riskler` artık "..."/"…" farkında. `_AYIRAC`
  regex'i ile parçalanır, her parça ayrı `partial_ratio`; TÜM parçalar eşik üstündeyse
  `dogrulanmadi=False`. Ayraç yoksa / >6 parça / hepsi <12 karakterse alıntı bütün
  kontrol edilir.

**3.-6. tur:** her turda ≤%9 doğrulanamayan (%52 → 0-9). Orijinal "..." deseni kalıcı
çözüldü — bu bölüme dokunulmadı.

### SORUN 3B — sayı/tablo format uyuşmazlığı (yanlış-pozitif ret) — ✅ ÇÖZÜLDÜ (7.+8. tur 0 doğrulanamayan)

6.-7. tur: 2-3/32 kalem doğrulanamadı, "..." YOK. İki alt-sebep, iki çözüm:
1. **Roll-up kalemi = 3B kurbanı da** (Not 34'ün iki satırını birleştiriyor → hem tekrar
   hem format uyuşmazlığı). `rollup_ele` bu kalemi eleyince 3B belirtisi de gidiyor.
2. **Saf format farkı:** aşağıdaki `_sadelestir_metin`.

6. tur: 3/32 kalem doğrulanamadı ama "..." YOK — sebep format farkı:
- *"(155,737) (49,115) 7 (1,959,702)"* — model **virgül** binlik ayracı kullanmış,
  kaynak Türkçe konvansiyonla **nokta** (155.737).
- TRİ alt kalemleri: çok satırlı tablo, boşluk/hizalama kaynakla birebir uyuşmuyor.
  İçerik gerçek (dokümanda manuel bulunmuştu) — halüsinasyon değil, `rapidfuzz` karakter
  farkına takılıyor.

- **`pipeline/grounding._sadelestir_metin`** (yeni): karşılaştırmadan önce (a) rakam-arası
  `.`/`,` kaldırılır (`155.737`/`155,737` → `155737`), (b) tüm boşluk/tab/satır sonu tek
  boşluğa iner. Hem alıntı parçası hem kaynak metin bundan geçer; `kaynak_metin` bir kez
  normalize edilir (`ground_riskler` başında). "..." bölme mantığı korunuyor.
- Birim test: virgül-ayraçlı alıntı + çok satırlı tablo alıntısı artık doğrulanıyor;
  "..." eski davranışı + uydurma-parça yakalama bozulmadı.

### Ek — CLI'da aşama aşama ilerleme çıktısı (zenginleştirildi)

- **`pipeline/ilerleme.py`** (yeni, saf sunum): `FAZ_ETIKETLERI` (tabs.py'den taşındı) +
  `asama_ozeti` (durumsuz, Streamlit checklist) + `model_rolleri_satiri` +
  `ilerleme_takipcisi(yaz, map_modelleri)` — grup sayısı/model listesini biriktirip
  çok satırlı, açıklamalı CLI logu üreten geri-çağırım fabrikası.
- **`pipeline/batch.py`**: `calistir_batch(..., yaz=<satır yazıcı>)`. Verilince her BDR
  için künye (dosya · karakter · **hangi rol hangi model**) + `graph.stream(
  stream_mode=["updates","values"])` ile aşama aşama log:
  ```
  ▶ 2 · Triyaj  (hangi bölümler kredi riski taşıyor?)
       49 bölüm tarandı → 29 analize alındı, 20 elendi
       23 bölüm kural (anahtar kelime) · 6 bölüm LLM (gpt-oss-120b) · 0 boilerplate
  ▶ 3 · Ensemble Map çıkarımı  —  3 grup × 1 model = 3 paralel çıkarım
       ✓ grup 1/3 · gpt-oss-120b → 2 ham risk (1.9s)
       ✓ grup 2/3 · gpt-oss-120b → 5 ham risk (2.6s)
       ✓ grup 3/3 · gpt-oss-120b → 8 ham risk (4.7s)
       = toplam 15 ham risk çıkarıldı
  ```
  `yaz` verilmezse eski `graph.invoke` yolu (davranış değişmez).
- **`run_poc.py --batch`**: `yaz=lambda s: print(s, flush=True)`.
- **`ui/tabs.py`**: aynı `ilerleme_takipcisi` Streamlit'te de — checklist'in altında
  `st.code` ile canlı, açıklamalı akış logu + künyede model rolleri satırı.

### Doğrulama

Offline: `py_compile` (tüm dokunulan dosyalar) + tam pipeline import + birim kontrolleri
geçti — kategori normalizasyonu (1C dahil), `rollup_ele` (5→4), `_kategori_kurtar`,
fuzzy dedup, grounding "…" farkındalığı. Mock batch koşumu zengin ilerleme çıktısını
doğruladı.

6.-8. tur: "Diğer" 0 (3 kez üst üste), doğrulanamayan 0 (7.+8. tur — SORUN 3B de
efektif kapandı). **8. tur 24 risk, roll-up YOK.** SORUN 2C 4 koşumdan 2'sinde çıktı
→ prompt güvenilmez; `is_rollup_of` deterministik garanti artık devrede.
SORUN 2D (critic şişmesi) açık, kullanıcı öncelik vermedi.

⚠️ **Streamlit'ten koşuyorsan:** dosya değişikliği sonrası Python modülleri önbelleğe
alındığı için **sunucuyu yeniden başlat** (Ctrl+C → tekrar `streamlit run`), yoksa
yeni kod (`is_rollup_of`, grounding normalizasyonu) devreye girmez.

9. tur bekliyor: restart sonrası aynı BDR ile 2-3 kez — roll-up gerçekten elendi mi.

**Bilinen limit:** `partial_ratio@85` uzun cümlede tek rakam-grubu değişimini (ör.
`513.245`→`999.111`) yakalamıyor — deterministik sayı-çıkarımlı kontrol (Faz 11.5).

---

## 2026-09-03 — İlk TAM TEMİZ gerçek pipeline koşumu (6. deneme)

**Konfig (Gemini'siz "ekonomi"):** `map=gpt-oss-120b`, `triage/reconciler/critic/
synthesis/segmenter_fallback = gpt-4o-mini`.

**Sonuç:** 108 sn wall / 310 sn LLM, 75 çağrı, **0 başarısız**, **$0.078**, 48 risk,
`qa_bayraklari: []`. Hiçbir mock fallback yok.

- Künye ✅ (Borusan Birleşik Boru Fabrikaları San. ve Tic. A.Ş. / 31 Aralık 2024)
- `denetci_gorusu` ✅ "Olumlu Görüş" (`_gorus_tara` deterministik tarama)
- `kaynak_modeller` ✅ tümü doğru (`gpt-oss-120b` / `critic` / birleşik), halüsinasyon yok
- Dipnot kapsamı ✅ TRİ, akreditif, ihracat taahhütleri, ertelenmiş vergi, kıdem
  tazminatı, ilişkili taraf, kur/faiz/fiyat riski, vergi tarhiyatları hepsi var
- Özet gerçek rakamlarla ("teminatsız kısa vadeli borçlar 8.413.164 TL, döviz borçları
  13.166.541 TL, nakit 2.356.166 TL")

**Öncesindeki 8 bug** (6 gerçek koşumda bulundu): künye kaybı · kaynak_modeller
halüsinasyonu · Gemini 429 retry · sentez mock fallback'in sessizce yutulması ·
tüm dipnotların analizden düşmesi (segmentasyon + boilerplate) · muhasebe standardı
gürültüsü · denetçi görüşü çıkarımı · OpenAI 4096 çıktı token tavanı.

**Ekonomi maliyet referansı:** ~$0.08/BDR, ~5 dk. Premium (Claude-ağırlıklı) ~$2-4;
tam açık-kaynak-dostu yol maliyetin ~%5'i.

**Kalan (bug değil, ince ayar):** 48 risk biraz fazla — daha güçlü bir reconciler
modeli düşük değerli KDK alt-kalemlerini daha iyi birleştirebilir.

---

## 2026-09-01 — İlk gerçek uçtan uca pipeline testi + 3 bug fix

**Konfig:** `map_models=["gpt-oss-120b"]`, `reconciler/critic/synthesis/segmenter_fallback
= gemini-3.6-flash`, `triage = gpt-4o-mini` (ucuz senaryo, `docs/ARCHITECTURE.md` §0'daki
tahmine yakın). Borusan BDR'si (593K karakter), gerçek API.

**Sonuç:** 372 sn, 19 LLM çağrısı, 1 başarısız (Gemini free-tier 429), $0.0315,
10 risk, `qa_bayraklari: []`. Fonksiyonel olarak uçtan uca çalıştı.

**Bulunan ve düzeltilen 3 bug** (bkz. commit `aabdbb4`):

1. **Künye kaybı** — segment grupları firma/dönem/denetçi bilgisini taşımıyordu,
   çoğu grup şema varsayımı ("Belirtilmemiş Şirket") döndürüyordu ve bu değer oy
   çoğunluğuna karışıyordu → nihai raporda firma adı boş çıktı. `gruplari_olustur`
   artık her gruba BDR'nin ilk 1200 karakterini (künye) ekliyor; `synthesis.py` ayrıca
   şema varsayılanlarını oy sayımından hariç tutuyor.
2. **`kaynak_modeller` halüsinasyonu** — bu izlenebilirlik alanı LLM'in serbestçe
   dolduracağı bir şema alanıydı; gemini "claude-3-5-sonnet", "audit-agent-v1",
   "audit_model" gibi **hiç var olmayan model adları** üretti. `reconciler.py` /
   `critic.py` artık bu alanı LLM'den hiç almıyor, deterministik atıyor.
3. **Gemini 429** tek denemede mock fallback'e düşürüyordu → `GeminiProvider`'a
   429'a özel 1 tekrar + 8 sn bekleme eklendi.

**Ders:** free-tier Gemini kotası (dk başına 5 istek) reconciler+critic+synthesis+
segmenter_fallback'in hepsini aynı modele yüklemek için yetersiz; gerçek/daha büyük
koşumlarda ücretli tier veya rolleri farklı sağlayıcılara dağıtmak gerekir.

**Doğrulama koşumu (`85f6e11`):** aynı ucuz konfigle tekrar çalıştırıldı. Künye (✅
Borusan Birleşik Boru Fabrikaları San. ve Tic. A.Ş., 31 Aralık 2024) ve `kaynak_modeller`
(✅ 35 riskin tamamı doğru `['gpt-oss-120b']`, halüsinasyon yok) düzeldi. Ama bu kez
Gemini'nin **günlük** ücretsiz kota limiti (20 istek/gün) bu oturumdaki yoğun testle
tükenmişti → 30 çağrının 15'i mock fallback'e düştü, sentez de düştü. Bu ortaya 4.
bir bug çıkardı: **sentez mock fallback'e düşünce `nihai_rapor.is_mock_fallback` hiç
işaretlenmiyordu** — kanıtlı mock metni sessizce gerçek özet gibi görünüyordu.
`synthesis.py` artık `is_mock_fallback`/`fallback_reason`'ı sentez çağrısından taşıyor;
`qa_rules.py` bunu açık bir bayrakla işaretliyor ("özet/karar/gerekçe güvenilir DEĞİL").

---

## 2026-09-01 — Model fiyatları (`config.json`)

- Tüm 20 modele `usd_1k_in` / `usd_1k_out` (1K token başına USD) eklendi. Artık
  `pipeline/nodes/cost.py` `maliyet_ozetle` gerçek `tahmini_usd` hesaplayabiliyor
  (önceden hep 0 idi, fiyat alanı yoktu).
- **Rakamlar kamuya açık liste fiyatlarından yaklaşık tahmindir** — gerçek fatura ile
  karşılaştırıp güncellenmeli, özellikle HF serverless açık kaynak modeller (barındıran
  sağlayıcıya göre değişir) ve Gemini 3.x / Claude Sonnet 4.5 gibi yeni sürümler.

---

## 2026-09-01 — Benchmark hızı + iki mod dokümantasyonu

- **`app.py`:** kıyas panelinde `truncate` denemesi geri alındı — tam yapı-farkında
  chunking geri geldi (`bd9599c` → `7ec946f`). Sorun chunking değildi; Mihenk-35B'nin
  HF serverless'te çağrı başına ~110 sn olması. `futures.wait(timeout=600)` eklendi:
  bu süreyi aşan modeller "⏱️ zaman aşımı" ile atlanır, tamamlananlar gösterilir.
- **`BDRAnalyzer.buyuk_girdi_stratejisi`** param'ı kaldı ("map_reduce" varsayılan;
  "truncate" opsiyonel, UI'da kullanılmıyor).
- **`docs/ARCHITECTURE.md` §0** (yeni): "İki Mod" — Model Seçimi/Karşılaştırma vs
  Multi-Agent Pipeline karşılaştırma tablosu (amaç, tetik, kod, LLM çağrısı, süre,
  çıktı, sidebar ayarları geçerli mi).
- **`docs/PIPELINE_DESIGN.md` §8:** tek modelli pipeline çalıştırma notu (ör. sadece
  gpt-oss-120b) — çalışır ama ensemble amacı kaybolur; reconciler/critic farklı model
  kalmalı.

---

## 2026-09-01 — Zayıf model kısmi çıktı toleransı + UI

- **`schemas.py`:** zayıf modeller (ör. Mihenk-LLM-35B) geçerli JSON üretip
  `genel_kredi_risk_ozeti` / `karar_egilimi` / `analist_gerekce_metni` alanlarını
  boş bırakınca tüm rapor doğrulama hatasıyla çöküyordu → bu üç alana varsayılan
  verildi (`_ALAN_URETILMEDI` metni + yeni `KomiteKararEgilimi.BELIRSIZ`).
  `normalize_karar_egilimi` bilinmeyen/None değeri → `BELIRSIZ`. Strict schema
  sağlayıcıları (OpenAI/Gemini/Anthropic) etkilenmez; benchmark'ta zayıf model artık
  "13 risk + Belirsiz karar" olarak görünür, mock fallback'e düşmez.
- **`app.py`:** BDR Metin Görünümü `st.container(height=560)` kaydırmalı kutuda; Model
  Çıktı Raporları yeniden `st.tabs` (üstten yatay geçiş), her rapor
  `st.container(height=600)` içinde; pipeline sekmesi benchmark'tan net ayrıldı
  (uyarı + "maliyeti anladım" onayı).

---

## 2026-09-01 — Multi-agent pipeline: tasarım + Faz 0

### Tasarım

- **`docs/PIPELINE_DESIGN.md`** (v0.2) — 10 fazlı LangGraph pipeline'ın mevcut koda
  eşlenmesi. Kararlar: iki yol paralel (`BDRAnalyzer` + `pipeline/`), critic = graph
  cycle, `PostgresSaver` baştan, ensemble map modelleri UI'dan seçilebilir.

### Faz 0 — Altyapı

- **Bağımlılıklar:** `langgraph`, `langgraph-checkpoint-postgres`, `psycopg[binary]`,
  `rapidfuzz` — venv'e kuruldu, `requirements.txt`'e eklendi (`pip check` temiz).
- **`docker-compose.yml`** — pipeline checkpoint için `postgres:17-alpine` servisi;
  `.env` / `.env.example`'a `PIPELINE_DB_URL`.
- **`config.json`:** `pipeline` bloğu (model rolleri + eşikler) + `mock` model id
  (mock-first geliştirme için).
- **`config.py`:** `get_model_config_by_id` (enabled bakmadan), `get_pipeline_config`,
  `get_pipeline_db_url`, `PIPELINE_DEFAULTS`.
- **`prompts/schemas.py`:** `BDRRiskItem.dogrulanmadi` / `.kaynak_modeller`,
  `BDRRiskAnalysisReport.qa_bayraklari` (hepsi primitive/liste — strict schema'yı
  bozmaz). `pipeline_izi` modele eklenmedi (serbest dict strict schema'yı bozar);
  dosyaya yazılırken eklenecek.
- **`src/finside/pipeline/`** (yeni paket): `state.py` (`PipelineState`, `GrupState`,
  `Segment`/`TriajKarari`/`SegmentGrubu`/`MapCiktisi`/`TraceKaydi` TypedDict'leri,
  `operator.add` reducer'ları), `llm_call.py` (`rapor_cagrisi` — trace'li tek model
  çağrısı, `ProviderFactory` üstünde).
- **`report_writer.py`:** `append_trace` → `outputs/.../trace.jsonl`.

Doğrulama: tüm dosyalar derleniyor; `rapor_cagrisi('mock', …)` + `append_trace` mock
ile uçtan uca çalıştı. Canlı API çağrısı yapılmadı.

### Faz 1-2 — Segmentasyon + Triyaj

- **`providers/`:** `BaseProvider.raw_generate(user_prompt, *, json_mode)` — şemasız ham
  metin üretimi; 5 provider'da (gemini/openai/anthropic/huggingface/mock) uygulandı.
- **`pipeline/llm_call.py`:** `ham_cagri` — trace'li ham metin çağrısı (hata → `basari=False`).
- **`chunking.py`:** başlık regex'leri genişletildi (Romen rakamı, "Ek N", alt-dipnot);
  `_is_heading` sayısal tablo satırlarını (bilanço kalemleri) artık başlık saymıyor.
- **`loaders/bdr_segmenter.py`** (yeni): `regex_segmentle` (offset'li `Segment` üretimi +
  küçük parça birleştirme), `segmentation_confidence` (5 boyut, dev segment → LLM
  fallback zorlaması), `segment_bdr` (güven < eşik → `segmenter_v1.md` LLM fallback,
  ipuçları `rapidfuzz` ile konumlanır).
- **`pipeline/keyword_map.py`** (yeni): `RiskKategorisi` → anahtar kelime ileri eşlemesi
  + boilerplate ibareleri (kural-tabanlı triyaj ön-filtresi).
- **`pipeline/nodes/segment.py`:** `segmentle` node → `segments.json`.
- **`pipeline/nodes/triage.py`:** `triyaj_yap` (kural + boilerplate + şüpheli → ucuz
  LLM ikili sınıflandırma, recall-güvenli), `gruplari_olustur` (karakter bütçesine göre
  paketleme + dev segment hard-split) → `triage_log.json`.
- **`pipeline/graph.py`** (yeni): `segmentle → triyaj_yap → gruplari_olustur → END`.
- **`prompts/`:** `segmenter_v1.md`, `triage_v1.md`.
- **`report_writer.py`:** `save_json` (ara çıktı dosyaları).

Doğrulama (mock, 593K karakterlik Borusan BDR'si): 53 segment / güven 0.82, triyaj
kural=12 / llm=41, 8 segment grubu (hepsi ≤ 88K karakter). **Batch resume testi:**
`triyaj_yap`'ta simüle hata → `invoke(None)` ile checkpoint'ten devam, `segmentle`
yeniden çalışmadı. Canlı API çağrısı yapılmadı.

### Faz 3 — Map / Ensemble Çıkarım

- **`pipeline/nodes/map_extract.py`** (yeni):
  - `map_dagit` — `gruplari_olustur` sonrası fan-out: her (grup × model) çifti için `Send("map_worker", …)`.
  - `map_worker` — `rapor_cagrisi` ile grup metnini analiz eder, yalnızca
    `tespit_edilen_riskler`'i alır, her kaleme `kaynak_modeller=[model_id]` yazar.
    `model_dump(mode="json")` ile enum→string (checkpoint-güvenli). Bir modelin çökmesi
    izole edilir (`hata_durumu` dolu, `riskler=[]`), diğerleri devam eder.
  - `map_topla` — join node: `map_raw.json` + tüm birikmiş trace'i `trace.jsonl`'e yazar.
- **Modeller:** `state.secili_map_modelleri` (UI) → yoksa `config.pipeline.map_models`.
- **`graph.py`:** `… → gruplari_olustur ─(Send: grup×model)→ map_worker → map_topla → END`.
- **`report_writer.py`:** `save_trace` (üzerine yazan, tekrarsız); trace artık node
  başına değil `map_topla`'da tek seferde yazılıyor.

Doğrulama (mock): 8 grup × 1 model = 8 map çıktısı, 24 ham risk; 8 grup × 2 model (biri
geçersiz id) = 16 çıktı, 8 başarılı + 8 izole hata, graph tamamlandı; checkpoint
serileştirme uyarısız.

### Faz 4-6 — Grounding + Uzlaştırma + Critic (grup alt-grafı)

- **`pipeline/grounding.py`** (yeni, LLM'siz): `ground_riskler` — her riskin
  `kaynak_metin_alintisi`'ni `rapidfuzz.partial_ratio` ile ham metinde arar;
  eşik altı → `dogrulanmadi=True` (katı modda eler).
- **`pipeline/reconciler.py`** (yeni): `mekanik_birlestir` (başlık kümeleme, en ihtiyatlı
  `risk_derecesi`, `kaynak_modeller` birleşimi, çelişki notu) + `uzlastir` (Reconciler
  LLM çağrısı; LLM'in düşürdüğü kalemler recall için geri eklenir, `kaynak_modeller`
  başlık eşleşmesiyle korunur).
- **`pipeline/critic.py`** (yeni): `eksik_tara` — taslakta olmayan ham risk başlıkları
  critic'e ipucu; Critic LLM yalnızca yeni/eksik riskleri döndürür.
- **`pipeline/group_graph.py`** (yeni): `ground → reconcile ⇄ critic → grup_bitir` alt-grafı.
  `_route_critic`: `son_critic_eklenen > 0 and critic_tur < max_critic_turu` → `reconcile`.
  Çıktı ana `PipelineState`'e (`uzlastirilmis_riskler` / `celiskiler` / `critic_turlari`
  / `trace`, hepsi `operator.add`) taşınır.
- **`pipeline/nodes/group.py`** (yeni): `grup_dagit` — `map_topla` sonrası her grup için
  `Send("grup_isle", …)`.
- **`state.py`:** `GrupState` genişletildi (çalışma + ana state'e taşınan alanlar).
- **`graph.py`:** `… map_topla ─(Send: grup)→ grup_isle (alt-graf) → END`.
- **`prompts/`:** `reconciler_v1.md`, `critic_v1.md`.

Doğrulama (mock, tam pipeline): 8 grup → 32 uzlaştırılmış risk, critic turu=1
(döngü tetiklenmedi — mock critic yeni risk üretmiyor), 66 trace kaydı, uyarısız.
**Critic döngü birim testi:** sahte critic her turda yeni risk döndürüyor →
`max_critic_turu=2`'de durdu (2 reconcile + 2 critic).

### Faz 7-8 — Sentez + QA

- **`dedupe.py`:** `dedup_risk_dicts` — dict tabanlı global dedup (başlık + opsiyonel
  embedding yakın-tekrar; `kaynak_modeller` birleşir, içerik kaybı yok).
- **`pipeline/qa_rules.py`** (yeni, LLM'siz): `qa_bayraklari` — KRİTİK risk + Olumlu karar,
  olumsuz denetçi görüşü + Olumlu karar, doğrulanmamış risk oranı > %30, boş risk +
  çok segment.
- **`pipeline/nodes/synthesis.py`** (yeni):
  - `sentezle` — `uzlastirilmis_riskler` global dedup → künye çoğunluk oylaması
    (`map_ciktilari[].kunye`) → Sentez LLM çağrısı (ham metin YOK, sadece risk listesi
    + künye) → üst düzey alanlar LLM'den, `tespit_edilen_riskler` deterministik dedup
    listesinden. `nihai_rapor` (dict).
  - `qa_kontrol` — `qa_bayraklari` hesaplar, `nihai_rapor.json` + `trace.jsonl` yazar.
- **`map_extract.py`:** `map_worker` artık `kunye` (firma/dönem/denetçi) da döndürüyor.
- **`state.py`:** `MapCiktisi.kunye`.
- **`graph.py`:** `… grup_isle → sentezle → qa_kontrol → END`.
- **`prompts/synthesis_v1.md`.**

Doğrulama (mock, tam pipeline, embedding kapalı): `nihai_rapor.json` üretildi, künye
oylaması doğru (Borusan / 31 Aralık 2024 / Olumlu Görüş), 4 risk (32→dedup), QA bayrağı
doğru tetiklendi ("risklerin %75'i doğrulanamadı" — mock alıntılar gerçek metinle
eşleşmiyor), 67 trace kaydı, graph tamamlandı.

### Faz 9-10 — Batch + Maliyet/Süre Şeffaflığı

- **`pipeline/nodes/cost.py`** (yeni): `maliyet_ozetle` node — `state.trace`'ten toplam
  çağrı, aşama kırılımı, tahmini token (karakter/4), toplam süre, tahmini USD (model
  bazında opsiyonel `usd_1k_in`/`usd_1k_out`). `nihai_rapor.pipeline_izi` +
  `pipeline_izi.json`.
- **`pipeline/batch.py`** (yeni): `calistir_batch(klasor, secili_modeller)` — her `.txt`
  ayrı `thread_id`; `_checkpointer` Postgres'i dener, erişilemezse (Docker kapalı vb.)
  `MemorySaver`'a düşer (uyarı ile, hang yok — `connect_timeout=5`).
  `outputs/<tarih>/<saat>/<bdr>/` + kökte `portfoy_ozeti.md`/`.json`.
- **`report_writer.py`:** `save_portfolio_summary`.
- **`run_poc.py`:** `--batch <klasör>` + `--map-models a,b,c`.
- **`graph.py`:** `… qa_kontrol → maliyet_ozetle → END`.

Doğrulama (mock, `--batch data/bdr_samples`, Postgres kapalı): `portfoy_ozeti.md`
üretildi, her BDR kendi klasöründe tüm ara çıktılarla; `pipeline_izi.json` — 43 çağrı,
aşama kırılımı, ~129K girdi token. Batch resume için `PostgresSaver` yolu (Docker'lı)
kullanıcı testine hazır.

### Faz 9.5-9.6 — Few-shot bankası + UI akış paneli

- **`pipeline/few_shot.py`** (yeni): `ilgili_ornekler` — risk listesindeki baskın
  kategorilere göre `prompts/few_shot_examples/<kategori>/*.json`'dan en çok 2 örnek
  seçip sentez promptuna ekler (embedding yok). Banka boşken `''` döner.
- **`prompts/few_shot_examples/`** — `README.md` (format) + `_SABLON.json`.
- **`synthesis.py`:** `sentezle` few-shot bloğunu user prompt başına ekliyor.
- **`app.py`:** yeni "🔗 Multi-Agent Pipeline" sekmesi — ensemble model çoklu seçim,
  `graph.stream(stream_mode="updates")` ile canlı faz göstergesi (✅/⏳), bitince
  firma/görüş/karar kartları + `pipeline_izi` metrikleri + risk özeti + JSON.

Doğrulama (mock): `few_shot.ilgili_ornekler` boş bankada `''`; `graph.stream` node akışı
UI faz göstergesi için doğru (`map_worker`×8, `grup_isle`×8, diğerleri ×1). Gerçek API
testi yapılmadı.

---

## 2026-09-01 — Model kataloğu temizliği + GPT-OSS 120B

### Değişen

- **`config.json` model adları sadeleştirildi.** Benchmark skoru / pazarlama ifadeleri
  (`(TR-MMLU Lideri %77.28)`, `(CETVEL 2026 Türkçe #1)`, `(Amiral Gemisi)`,
  `(10K TPM Yüksek Kapasite)` vb.) kaldırıldı; net model adları bırakıldı
  (`Qwen2.5 72B Instruct`, `Llama 3.3 70B Instruct`, `OpenAI GPT-4o` …).
- `claude-3-5-sonnet` id'si → `claude-sonnet-4-5` (önceki oturumdan).

### Eklenen

- **`gpt-oss-120b`** modeli — OpenAI'nin açık ağırlıklı MoE modeli, HuggingFace
  serverless router üzerinden (`openai/gpt-oss-120b`, `provider: huggingface`).
  `max_input_chars: 200000`, `enabled: true`.

---

## 2026-09-01 — Provider dayanıklılığı, yapısal chunking, paralel çalıştırma

**Commit:** `c7ba3af` (dal: `Development`)

### Eklenen

- **`src/finside/chunking.py`** — yapı-farkında bölümleme (saf fonksiyonlar):
  `split_sections` (dipnot/başlık regex sınırları), `pack_sections` (limit-aşmayan aç
  gözlü paketleme), `build_chunks` (parçalara firma künyesi ekleme). Harici bağımlılık yok.
- **`src/finside/dedupe.py`** — `uncovered_risks`: sentez (reduce) çıktısını ana risk
  listesi kabul eder, `text-embedding-3-small` ile **kapsama kontrolü** yapar; sentez
  modelinin düşürdüğü riskleri geri ekler. Hiçbir riski silmez/birleştirmez. Farklı
  `dipnot_referansi` olan kalemler asla kapsanmış sayılmaz. `OPENAI_API_KEY` yoksa
  Jaccard (kelime kümesi) fallback'i.
- **`BDRAnalyzer` map-reduce** (`analyzer.py`): girdi `PROVIDER_INPUT_LIMITS` eşiğini
  aşarsa → `build_chunks` → parçaları `ThreadPoolExecutor` ile paralel analiz (map) →
  tek "sentez" çağrısıyla birleştirme (reduce) → embedding kapsama koruması. Girdi
  eşik altındaysa davranış değişmez (tek çağrı).
- **`BaseProvider._repair_json` / `_parse_report`** (`providers/base.py`): kesik JSON
  çıktısını açık `{ [ "` yapılarını kapatarak kurtarır. Gemini, HuggingFace ve
  Anthropic (text yolu) bu yolu kullanır.
- **`app.py` paralel model çalıştırma**: `run_model_analysis` bağımsız fonksiyonu +
  `ThreadPoolExecutor(max_workers=min(N, MAX_PARALLEL_MODELS=8))`. Modeller artık sıra
  sıra değil aynı anda çalışır; sonuç/metrik sırası korunur.

### Değişen

- **Anthropic sağlayıcı** tamamen yenilendi:
  - Markdown/serbest metin yerine **forced tool-use** (`tool_choice={"type":"tool"}`,
    şema `input_schema` olarak) → %100 şema uyumlu JSON.
  - `client.messages.stream()` — 10 dakikayı aşabilen büyük girdili istekler için zorunlu.
  - `stop_reason == "max_tokens"` tespiti → sessiz yarım rapor yerine açık hata.
  - `MAX_OUTPUT_TOKENS = 32000`; güncel `FALLBACK_CLAUDE_MODELS` listesi.
- **HuggingFace sağlayıcı**: `chat.completions.create(stream=True)` — 504 Gateway
  Timeout'ları azaltır (hata mesajının önerisi).
- **`prompts/schemas.py`**:
  - Tanınmayan `risk_kategorisi` → "Diğer Kalitatif Risk Unsuarları" (eskiden tüm rapor
    doğrulama hatasıyla çöküyordu).
  - Tanınmayan `risk_derecesi` → "Orta".
  - **Bug fix:** `normalize_karar_egilimi` içindeki `"red" in v_clean` kontrolü, geçerli
    "Olumlu (K**red**i Tahsis Edilebilir)" cevabını yanlışlıkla "Olumsuz"a çeviriyordu →
    `"reddedil"` / `"rejected"` ile değiştirildi.
- **`config.json`**:
  - Anthropic modeli `claude-3-5-sonnet-latest` → **`claude-sonnet-4-5`** (eski 3.x
    model isimleri API'den kaldırılmış, hepsi 404 dönüyordu); id ve ad güncellendi.
  - Bu modelin `max_tokens` değeri `8192` → `32000`.
- **`app.py`**: `use_container_width=True` → `width="stretch"` (Streamlit 2025-12-31
  deprecation'ı); try/except sırası eski sürüm uyumluluğu için ters çevrildi.

### Doğrulama

- Tüm dosyalar `py_compile` ile derleniyor.
- `_repair_json`, `uncovered_risks` (embedding) ve `karar_egilimi` normalizasyonu birim
  testlerle doğrulandı.
- Chunking yolu `provider="mock"` ile uçtan uca çalıştı (593K karakter → 9 bölüm).
- Canlı API testleri (kredi tüketimi nedeniyle sınırlı): Gemini 3.6 Flash tam BDR'de
  4 bölüm / ~93 sn / 18 risk, künye ve rakamlar doğru; HuggingFace Qwen-7B 9 bölüm /
  25 risk. Anthropic forced tool-use + streaming ile çalışıyor.

### Bilinen sınırlar

- Zayıf açık kaynak modeller (7B) sentez aşamasında sığ özet/gerekçe üretebilir — model
  kapasitesi, mimari değil.
- HuggingFace serverless bazı chunk çağrılarında hâlâ transient 429/504 dönebilir;
  başarısız parçalar elenir, kalanlar birleştirilir.
- `gemini-3.1-pro-preview` ücretsiz katmanda kota=0 → 429; faturalandırma gerektirir
  (kod sorunu değil).
