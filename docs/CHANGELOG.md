# Değişiklik Günlüğü

Biçim: her giriş bir çalışma oturumunu özetler. Tarihler mutlaktır.

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
