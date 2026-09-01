# Finside AI — Mimari & Teknoloji Dokümanı

**Doküman Sürümü:** v1.1
**Son Güncelleme:** 1 Eylül 2026
**Kapsam:** BDR analiz motorunun uçtan uca işleyişi, kullanılan teknolojiler ve tasarım kararları.

---

## 0. İki Mod — hangisi ne zaman çalışır

Uygulamada **iki bağımsız analiz yolu** var. Karışmazlar; ayrı butonlarla tetiklenir.

| | **📊 Model Seçimi / Karşılaştırma** | **🔗 Multi-Agent Pipeline** |
| :--- | :--- | :--- |
| Amaç | "Hangi model bu iş için iyi?" — hızlı kıyas | Üretim kalitesinde nihai analiz |
| Tetik | Sidebar **🚀 ANALİZİ BAŞLAT** | Pipeline sekmesi **🔗 PIPELINE BAŞLAT** |
| Kod | `BDRAnalyzer` (`analyzer.py`) | `pipeline/` paketi (LangGraph) |
| Model | Seçtiğin her model **ayrı ayrı**, paralel | Ensemble: aynı görevi 2-3 model birlikte |
| Büyük girdi | Yapı-farkında chunking + **basit sentez** | Chunking + **grounding + uzlaştırma + critic** + sentez |
| Doğrulama | Yok (ham model çıktısı) | rapidfuzz grounding, çelişki tespiti, eksik-tarama döngüsü |
| LLM çağrısı / BDR | Model başına ~3-12 (chunk + sentez) | ~20-45 (ensemble × grup + reconcile + critic + sentez) |
| Süre | Model başına ~10-660 sn (modele göre) | ~4-12 dk |
| Çıktı | `<model_id>_report.md/json` + `summary_metrics` | `nihai_rapor.json` + `segments/triage/map_raw/trace` + `pipeline_izi` |
| Sidebar ayarları (mod/model/parametre) | ✅ geçerli | ❌ geçerli değil (pipeline kendi ensemble seçimini kullanır) |

**Neden ikisi ayrı:** Karşılaştırma tek modelin ham gücünü ölçer (blind spot'ları dahil).
Pipeline bu blind spot'ları ensemble + critic ile telafi eder — ama BDR başına 20-45 çağrı
maliyeti var, o yüzden önce karşılaştırmadan model kararı verilir.

---

## 1. Genel Bakış

Finside AI, bir Bağımsız Denetim Raporu (BDR) metnini alıp birden fazla LLM ile paralel
analiz eden, her modelin çıktısını yapılandırılmış (Pydantic) bir **Kredi Komitesi Risk
Raporu**'na dönüştüren ve modelleri karşılaştıran bir karar destek / benchmark motorudur.

```
                     ┌──────────────────────────────────────────────┐
   BDR .txt  ──────► │  app.py (Streamlit)  /  run_poc.py (CLI)      │
                     └───────────────┬──────────────────────────────┘
                                     │  seçili model id listesi
                     ┌───────────────▼──────────────────────────────┐
                     │  ThreadPoolExecutor — modeller PARALEL         │
                     └───────────────┬──────────────────────────────┘
                                     │  her model için 1 adet
                     ┌───────────────▼──────────────────────────────┐
                     │  BDRAnalyzer (Orchestrator)                    │
                     │   • girdi ≤ limit  → tek çağrı                 │
                     │   • girdi > limit  → yapısal chunking map-reduce│
                     └───────────────┬──────────────────────────────┘
                                     │  Strategy + Factory
                     ┌───────────────▼──────────────────────────────┐
                     │  Provider (gemini / openai / anthropic /       │
                     │            huggingface / mock)                 │
                     │   → yapılandırılmış JSON → BDRRiskAnalysisReport│
                     └───────────────┬──────────────────────────────┘
                                     │
                     ┌───────────────▼──────────────────────────────┐
                     │  ReportWriter → outputs/<tarih>/<saat>/<dosya>/│
                     │   *_report.md · *_report.json · summary_metrics│
                     └──────────────────────────────────────────────┘
```

---

## 2. Katmanlar (SOLID)

| Katman | Dosya | Sorumluluk | İlke |
| :--- | :--- | :--- | :--- |
| Konfigürasyon | `config.py`, `config.json` | Model tanımları, env okuma, varsayılan birleştirme | SRP |
| Yükleyiciler | `src/finside/loaders/` | BDR metni ve markdown prompt şablonu yükleme + önbellek | SRP, DIP |
| Şema | `prompts/schemas.py` | Pydantic rapor modelleri + esnek enum `field_validator`'ları | SRP |
| Sağlayıcılar | `src/finside/providers/` | Her LLM API'si için `analyze()` stratejisi | Strategy, Factory, OCP, DIP |
| Chunking | `src/finside/chunking.py` | Yapı-farkında bölümleme (saf fonksiyonlar) | SRP, pure functions |
| Dedupe | `src/finside/dedupe.py` | Sentez sonrası embedding tabanlı kapsama koruması | SRP |
| Orkestratör | `src/finside/analyzer.py` | Girdi boyutuna göre tek-çağrı / map-reduce kararı, birleştirme | SRP |
| Yazıcılar | `src/finside/writers/` | Markdown + JSON + özet metrik dosyaları | SRP |
| Arayüz | `app.py`, `run_poc.py` | Streamlit UI / CLI, model seçimi, paralel çalıştırma | — |

Bağımlılıklar fonksiyon parametreleriyle enjekte edilir (global state yok). Yeni bir LLM
eklemek `ProviderFactory._providers` sözlüğüne bir satır + yeni bir `BaseProvider` alt
sınıfıdır; mevcut kod değişmez (Open/Closed).

---

## 3. Yapılandırılmış Çıktı Stratejisi

Hedef: her model, `BDRRiskAnalysisReport` Pydantic şemasına %100 uyan bir JSON üretmeli.
Her sağlayıcı bunu kendi en güvenilir mekanizmasıyla yapar:

| Sağlayıcı | Mekanizma | Not |
| :--- | :--- | :--- |
| **Gemini** | `GenerateContentConfig(response_mime_type="application/json", response_schema=BDRRiskAnalysisReport)` + `thinking_config` | `client.chats.create` → başarısızsa `client.models.generate_content` fallback |
| **OpenAI** | `client.beta.chat.completions.parse(response_format=BDRRiskAnalysisReport)` | `o1/o3` için `reasoning_effort` + `max_completion_tokens`; TPM (rate limit) kurtarma ile metin kırpma |
| **Anthropic** | **Forced tool-use**: şema `input_schema` olarak verilir, `tool_choice={"type":"tool"}` ile JSON zorlanır | `messages.stream()` (10 dk+ istekler zorunlu); `stop_reason == "max_tokens"` → kesme hatası; eski model isimleri için otomatik model fallback listesi |
| **HuggingFace** | Prompt içine şema gömülür + `chat.completions.create(stream=True)` | Sohbet modeli değilse `text_generation`; birden çok serverless model fallback |
| **Mock** | Deterministik sabit rapor (Borusan / genel) | API anahtarı yok / test modu / diğer sağlayıcı hatası |

### Kesik JSON kurtarma (`BaseProvider._parse_report`)

Küçük açık kaynak modeller çıktıyı yarıda kesebilir ("EOF while parsing a list").
`_repair_json()` açık `{ [ "` yapılarını sayıp kapatır; `_parse_report()` önce normal,
başarısızsa onarılmış JSON ile `model_validate_json` dener.

### Esnek enum normalizasyonu (`prompts/schemas.py`)

`field_validator(mode="before")` ile model çıktısındaki serbest metin kanonik enum
değerine eşlenir:
- Tanınmayan `risk_kategorisi` → **"Diğer Kalitatif Risk Unsuarları"** (tek uydurma kategori tüm raporu çökertmez)
- Tanınmayan `risk_derecesi` → **"Orta"**
- `karar_egilimi` / `denetci_gorusu` → anahtar kelime eşleşmesi ("şartlı", "olumsuz", "reddedil" …)

---

## 4. Büyük Girdi: Yapı-Farkında Map-Reduce

BDR örnekleri ~600K karakter (~150K token) olabilir. Bu boyut çoğu modelin bağlam
penceresini aşar, çağrıları çok yavaşlatır ve maliyeti katlar. Çözüm **düz karakter
bölme değil**, belgenin kendi yapısını kullanan map-reduce'tur.

### 4.1 Girdi limiti (`analyzer.PROVIDER_INPUT_LIMITS`)

| Sağlayıcı | Limit (karakter) |
| :--- | :--- |
| huggingface | 90.000 |
| openai / anthropic / gemini | 200.000 |
| mock | 5.000.000 |
| (varsayılan) | 150.000 |

`config.json` içinde model bazında `max_input_chars` ile ezilebilir. Girdi limitin
altındaysa tek çağrı yapılır, chunking devreye girmez.

### 4.2 Split — `chunking.split_sections`

Satır bazında bölüm sınırı regex'leri:
- `NOT 21` / `DİPNOT 35` gibi numaralı dipnot başlıkları
- `1) Görüş`, `3) Kilit Denetim Konuları` gibi numaralı başlıklar
- BÜYÜK HARF başlık satırları
- "KİLİT DENETİM KONULARI", "GÖRÜŞÜN DAYANAĞI", "FİNANSAL RİSK YÖNETİMİ" gibi bilinen ibareler

Her dipnot kendi içinde bütün bir anlam birimi olduğu için sınırlar %100 kesinlikle
işaretlidir — embedding ile yeniden keşfetmeye gerek yoktur.

### 4.3 Pack — `chunking.pack_sections`

Ardışık bölümler, sağlayıcı limitini aşmadan aç gözlü şekilde tek parçalarda toplanır.
Tek başına limiti aşan bir bölüm son çare olarak karakter bazlı bölünür. İlk parça
dışındaki her parçaya belgenin ilk ~1200 karakteri (firma / dönem / denetçi künyesi)
eklenir — böylece her parça kimlik bilgisini görür.

### 4.4 Map — `BDRAnalyzer._analyze_chunked`

Her parça, "bu daha büyük bir BDR'nin sadece bir bölümüdür, yalnızca burada açıkça
geçen riskleri çıkar, yoksa boş liste döndür" talimatıyla sarılır ve
`ThreadPoolExecutor` (en çok 4 worker) ile **paralel** analiz edilir. Mock fallback'e
düşen parçalar elenir.

### 4.5 Reduce — `BDRAnalyzer._synthesize`

Geçerli kısmi raporların JSON'ları tek bir "sentez" çağrısında birleştirilir. Model
tüm riskleri birlikte görerek **genel risk özetini, karar eğilimini ve analist gerekçe
metnini yeniden yazar** — analitik derinlik burada üretilir.

### 4.6 Kapsama koruması — `dedupe.uncovered_risks`

Sentez modelinin konsolide risk listesi **ana liste** kabul edilir (en iyi semantic
dedupe modelin kendisidir; bağlamı anlar, bağlı-ortaklık kefaletiyle 3.-şahıs
kefaletini birleştirmez). Ardından:

1. Mekanik olarak birleştirilmiş (başlık bazlı dedupe) risk listesindeki her kalem için,
2. `text-embedding-3-small` ile sentez listesindeki en yakın kaleme kosinüs benzerliği hesaplanır,
3. Benzerlik < **0.80** ise → sentez modeli o riski düşürmüş demektir → **geri eklenir**.

Farklı `dipnot_referansi`'na sahip kalemler asla kapsanmış sayılmaz. `OPENAI_API_KEY`
yoksa kelime kümesi (Jaccard ≥ 0.6) fallback'i kullanılır. Bu adım **hiçbir riski
silmez veya birleştirmez** — sadece kaybolanı geri getirir, dolayısıyla recall garanti.

> **Neden embedding ile chunk sınırı değil de sadece dedupe?** BDR yapısal bir belge;
> boilerplate yoğunluğu embedding tabanlı sınır tespitini yanıltır, non-deterministiklik
> benchmark tekrarlanabilirliğini bozar, retrieval tabanlı yaklaşım risk kaçırır.
> Embedding'in güvenli ve faydalı olduğu tek yer reduce sonrası kapsama denetimidir.

---

## 5. Dayanıklılık Katmanları

| Sorun | Çözüm | Konum |
| :--- | :--- | :--- |
| API anahtarı yok / paket yok / API hatası | Deterministik mock rapor + `is_mock_fallback` + `fallback_reason` | tüm provider'lar |
| Eski/kaldırılmış model adı (404) | Sağlayıcı içi otomatik model fallback listesi | anthropic, huggingface |
| 10 dk+ süren istek | `messages.stream()` | anthropic |
| 504 Gateway Timeout | `chat.completions.create(stream=True)` | huggingface |
| Çıktı token limitinde kesilme | `stop_reason` kontrolü → açık hata mesajı | anthropic |
| Yarım/bozuk JSON | `_repair_json` + `_parse_report` | base provider |
| Uydurma enum değeri | `field_validator` normalizasyonu | schemas |
| Tek parçanın çökmesi | Map aşamasında o parça elenir, kalanlar birleşir | analyzer |

---

## 6. Paralellik

- **Model düzeyi** — `app.py` / `run_model_analysis`: seçili tüm modeller
  `ThreadPoolExecutor(max_workers=min(N, 8))` ile aynı anda çalışır. Toplam süre en
  yavaş modele eşittir, toplamları değil. Sonuç ve metrik listeleri seçim sırasında
  korunur (tablo sırası bozulmaz).
- **Chunk düzeyi** — `analyzer._analyze_chunked`: bir modelin parçaları
  `ThreadPoolExecutor(max_workers=min(chunk, 4))` ile paralel. İç içe thread havuzları
  I/O-bound olduğu için GIL sorun değildir.

---

## 7. Teknoloji Envanteri

| Teknoloji | Sürüm (kurulu) | Rol |
| :--- | :--- | :--- |
| Python | 3.13 | Çalışma ortamı |
| pydantic | 2.13.5 | Rapor şeması, doğrulama, enum normalizasyonu |
| python-dotenv | 1.2.3 | `.env` → API anahtarları |
| google-genai | 2.20.0 | Gemini — `response_schema`, `thinking_config`, chat SDK |
| openai | 3.6.0 | OpenAI — `beta.chat.completions.parse`; ayrıca `text-embedding-3-small` (dedupe) |
| anthropic | 1.2.0 | Claude — forced tool-use, streaming |
| huggingface-hub | 1.29.0 | `InferenceClient` — serverless router, streaming chat |
| streamlit | 1.62.0 | Web arayüzü, canlı prompt düzenleyici, karşılaştırma paneli |
| pandas | 3.0.5 | Tablo/veri gösterimi |
| httpx / requests | — | HTTP taşıma katmanı (SDK'lar üzerinden) |
| concurrent.futures | stdlib | Model ve chunk düzeyi paralellik |

**Yapılandırılmış çıktı:** Gemini `response_schema` · OpenAI `beta.parse` · Anthropic
tool-use · HF prompt-gömme + `_repair_json`.
**Chunking:** saf Python + regex (harici bağımlılık yok).
**Semantic dedupe koruması:** OpenAI embeddings API (opsiyonel; yoksa Jaccard).

---

## 8. Önemli Konfigürasyon Parametreleri

`config.json` (üst düzey ve model bazında):

| Anahtar | Açıklama |
| :--- | :--- |
| `default_temperature`, `default_max_tokens`, `default_top_p`, `default_repetition_penalty` | Model bazında ezilmezse kullanılan varsayılanlar |
| `default_reasoning_effort` | `low` / `medium` / `high` / `auto` → `BaseProvider.EFFORT_TOKEN_MAP` üzerinden token bütçesi |
| `models[].provider` | `gemini` / `openai` / `anthropic` / `huggingface` / `mock` |
| `models[].model_name` | Sağlayıcıya gönderilen gerçek model kimliği |
| `models[].api_key_env` | İlgili API anahtarının env değişkeni adı |
| `models[].max_input_chars` | (opsiyonel) chunking eşiğini model bazında ezer |
| `models[].enabled` | UI'da varsayılan seçili gelir |

`analyzer.py` sabitleri: `PROVIDER_INPUT_LIMITS`, `CHUNK_UTILIZATION` (0.9),
`MAX_CHUNK_WORKERS` (4), `EMBED_API_KEY_ENV`.
`dedupe.py` sabitleri: `EMBED_MODEL`, `COVERAGE_THRESHOLD` (0.80), `JACCARD_THRESHOLD` (0.6).
`app.py`: `MAX_PARALLEL_MODELS` (8).
