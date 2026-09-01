# Değişiklik Günlüğü

Biçim: her giriş bir çalışma oturumunu özetler. Tarihler mutlaktır.

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
