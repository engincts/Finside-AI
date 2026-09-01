# Finside AI — Otonom Kurumsal Kredi Tahsis & Karar Destek Sistemi

Finside AI, kurumsal kredi tahsis süreçlerinde kullanılan yapılandırılmış finansal veriler (mizan, e-defter, rasyolar) ile yapılandırılmamış metinleri (Bağımsız Denetim Raporu / BDR dipnotları — dava, rehin, kefalet, koşullu yükümlülük gibi kalitatif risk unsurları) birlikte analiz edip, açıklanabilir (XAI) ve gerekçeli bir "Kredi Komitesi Raporu" üreten karar destek sistemidir.

---

## 🧠 Mimari & İşleyiş

BDR metni → seçili modeller **paralel** analiz edilir → her model yapılandırılmış bir
Kredi Komitesi Risk Raporu üretir → sonuçlar `outputs/` altına ve karşılaştırma paneline yazılır.

- **Yapılandırılmış çıktı**: Gemini `response_schema`, OpenAI `beta.chat.completions.parse`,
  Anthropic **forced tool-use**, HuggingFace prompt-gömme + kesik JSON kurtarma.
- **Büyük girdi (~600K karakter)**: yapı-farkında **map-reduce** — belge dipnot/başlık
  sınırlarında bölünür (`chunking.py`), parçalar paralel analiz edilir, tek "sentez"
  çağrısıyla birleştirilir, embedding tabanlı kapsama koruması (`dedupe.py`) düşen
  riskleri geri ekler.
- **Dayanıklılık**: mock fallback, otomatik model fallback, streaming, JSON onarımı,
  esnek enum normalizasyonu.

Ayrıntı: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** · Değişiklik geçmişi: **[docs/CHANGELOG.md](docs/CHANGELOG.md)**

### 🔗 Multi-Agent Pipeline (LangGraph)

Tek-model motorunun yanında, çok sayıda BDR'yi **recall-odaklı** işleyen 10 fazlı
LangGraph pipeline: segmentasyon → triyaj → ensemble map (çoklu model) → grounding
(rapidfuzz) → uzlaştırma → critic (eksik tarama, döngülü) → sentez → QA → maliyet.

```bash
docker compose up -d                      # pipeline checkpoint DB (Postgres)
python run_poc.py --batch data/bdr_samples --map-models gemini-3.6-flash,claude-sonnet-4-5,gpt-oss-120b
```

Streamlit'te **"🔗 Multi-Agent Pipeline"** sekmesinden tek BDR için canlı faz takibiyle
çalıştırılabilir. Tasarım: **[docs/PIPELINE_DESIGN.md](docs/PIPELINE_DESIGN.md)**

---

## 🚀 Max Tokens & Muhakeme Kapasitesi

Modellerin çıktı uzunluğu ve derin muhakeme (reasoning effort) tavanı `config.json`
üzerinden model bazında ayarlanır:

- **Google Gemini (3.6 Flash / 3.1 Pro)**: `16,384 max_tokens` + `high reasoning_effort`
- **OpenAI (GPT-4o, GPT-4o-mini, o3-mini)**: `8,192 – 16,384 max_tokens` + `high reasoning_effort`
- **Anthropic (Claude Sonnet 4.5)**: `32,000 max_tokens` (forced tool-use + streaming)
- **Açık Ağırlık Modeller (GPT-OSS 120B, Qwen2.5 72B, Llama 3.3 70B, Qwen3 32B, Gemma 3 27B, DeepSeek V3)**: `8,192 max_tokens`, HuggingFace serverless router üzerinden

Girdi tarafında chunking eşiği sağlayıcıya göre değişir (`analyzer.PROVIDER_INPUT_LIMITS`:
HF 90K, bulut 200K karakter); `config.json` içinde `max_input_chars` ile ezilebilir.

---

## 📦 Proje Bağımlılıkları (`requirements.txt`)

1. **Temel Şema & Konfigürasyon**: `pydantic>=2.0.0`, `python-dotenv>=1.0.0`
2. **Kapalı Kaynak LLM SDK'ları**: `google-genai>=0.1.0`, `google-generativeai>=0.8.0`, `openai>=1.0.0`, `anthropic>=0.20.0`
   - `openai` ayrıca `text-embedding-3-small` ile sentez sonrası kapsama koruması için kullanılır (opsiyonel; anahtar yoksa Jaccard fallback).
3. **Açık Kaynak & Serverless Inference**: `huggingface-hub>=0.20.0`
4. **Web UI & Dashboard**: `streamlit>=1.30.0`, `pandas>=2.0.0`
5. **HTTP & Ağ Katmanı**: `requests>=2.28.0`, `httpx>=0.25.0`
6. **Paralellik**: `concurrent.futures` (standart kütüphane) — model ve chunk düzeyi

---

## 🚀 Başlatma Yöntemleri

### 1. PowerShell Tek Tıkla Başlatma (Tavsiye Edilen)
```powershell
.\run.ps1
```

### 2. Manuel Web Arayüzü Başlatma
```bash
pip install -r requirements.txt
streamlit run app.py
```
Arayüz tarayıcınızda otomatik olarak **`http://localhost:8501`** adresinde açılacaktır.

---

## 📂 Dizin Yapısı

```
Finside-AI/
├── README.md                  # Proje dokümantasyonu (Canlı Referans)
├── app.py                     # Web Kullanıcı Arayüzü & Dinamik Prompt Düzenleyici
├── run.ps1                    # PowerShell Tek Tıkla Kurulum ve Başlatma Betiği
├── .env.example               # SADECE API Key / Gizli Bilgiler Şablonu
├── .gitignore                 # Git kapsamı dışındaki dosyalar (.venv, outputs vb.)
├── config.json                # Tüm Açık & Kapalı Kaynak LLM Konfigürasyonu
├── config.py                  # Konfigürasyon ve Env okuyucu
├── requirements.txt           # Tüm Python Bağımlılıkları Listesi
├── docs/
│   ├── ARCHITECTURE.md        # Mevcut tek-model motoru: uçtan uca işleyiş & teknolojiler
│   ├── PIPELINE_DESIGN.md     # Multi-agent LangGraph pipeline tasarımı (v0.2, uygulama bekliyor)
│   ├── CHANGELOG.md           # Sürüm / değişiklik günlüğü
│   └── BENCHMARK_RESEARCH.md  # Açık & Kapalı Kaynak LLM Benchmark Özet Raporu
├── data/
│   └── bdr_samples/           # BDR txt test verileri (Borusan 2024 BDR örneği dahil)
├── prompts/
│   ├── bdr_analyst_v1.md      # Dinamik Dipnot İçeren İyileştirilmiş BDR Prompt Şablonu
│   └── schemas.py             # Pydantic Rapor Şemaları ve Esnek Enum Validator'ları
├── src/
│   └── finside/
│       ├── loaders/           # Veri & Prompt Yükleyici Modülleri (SRP & DIP)
│       │   ├── __init__.py
│       │   ├── base_loader.py # BaseLoader Soyut Sınıfı
│       │   ├── bdr_loader.py  # BDR Metin Yükleyici
│       │   └── prompt_loader.py # Prompt Şablon Yükleyici
│       ├── providers/         # SOLID Strategy & Factory LLM Sağlayıcı Modülleri
│       │   ├── __init__.py
│       │   ├── base.py        # BaseProvider — token bütçesi, JSON çıkarma & kesik JSON onarımı
│       │   ├── gemini_provider.py       # response_schema + thinking_config
│       │   ├── openai_provider.py       # beta.chat.completions.parse + TPM kurtarma
│       │   ├── anthropic_provider.py    # forced tool-use + streaming + model fallback
│       │   ├── huggingface_provider.py  # serverless router + streaming + model fallback
│       │   ├── mock_provider.py         # deterministik simülasyon / fallback
│       │   └── factory.py     # ProviderFactory Fabrika Sınıfı
│       ├── writers/           # Dosya I/O & Rapor Yazıcı Modülleri
│       │   ├── __init__.py
│       │   └── report_writer.py
│       ├── chunking.py        # Yapı-farkında bölümleme (dipnot/başlık sınırları)
│       ├── dedupe.py          # Sentez sonrası embedding tabanlı kapsama koruması
│       ├── analyzer.py        # SOLID Orchestrator — tek-çağrı / map-reduce kararı
│       └── __init__.py
├── outputs/                   # Tarih ve saat bazlı hiyerarşik klasörler
└── run_poc.py                 # CLI orkestratör betiği
```