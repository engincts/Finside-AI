# Değişiklik Günlüğü

Biçim: her giriş bir çalışma oturumunu özetler. Tarihler mutlaktır.

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
