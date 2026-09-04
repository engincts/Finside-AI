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

Ayrıntı: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** · Kurumsal Sunum: **[docs/EXECUTIVE_PRESENTATION_GUIDE.md](docs/EXECUTIVE_PRESENTATION_GUIDE.md)** · Değişiklik geçmişi: **[docs/CHANGELOG.md](docs/CHANGELOG.md)**

### 🔗 Multi-Agent Pipeline (LangGraph)

Tek-model motorunun yanında, çok sayıda BDR'yi **recall-odaklı** işleyen 10 fazlı
LangGraph pipeline: segmentasyon → triyaj → ensemble map (çoklu model) → grounding
(rapidfuzz + sayısal imza) → uzlaştırma → critic (eksik tarama, döngülü) → sanitizer (filtre ajanı) → sentez → QA → maliyet.

```bash
docker compose up -d                      # pipeline checkpoint DB (Postgres)
python run_poc.py --batch data/bdr_samples --map-models gemini-3.6-flash,claude-sonnet-4-5,gpt-oss-120b
```

Streamlit'te **"🔗 Multi-Agent Pipeline"** sekmesinden tek BDR için canlı faz takibiyle
çalıştırılabilir. Tasarım ve Teknik Detaylar: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

---

## 🚀 Max Tokens & Cloud Context Window Kapasitesi

Modellerin çıktı uzunluğu ve derin muhakeme (reasoning effort) tavanı `config.json`
üzerinden model bazında ayarlanır:

- **Google Gemini (3.6 Flash / 3.1 Pro)**: `65,536 max_tokens` (64K çıktı tavanı) + `1M-2M Token Context Window`
- **OpenAI (GPT-4o, GPT-4o-mini, o3-mini)**: `16,384 – 65,536 max_tokens` + `128K Context Window`
- **Anthropic (Claude Sonnet 4.5)**: `64,000 max_tokens` + `200K Context Window`
- **Açık Ağırlık Modeller (GPT-OSS 120B, Qwen2.5 72B, Llama 3.3 70B)**: `16,384 max_tokens`, HuggingFace serverless router üzerinden

Girdi tarafında chunking eşiği sağlayıcıya göre değişir (`Config.PROVIDER_INPUT_LIMITS`:
Gemini 3.8M karakter / ~1M token, Anthropic 760K, OpenAI 480K, HF 250K karakter); `config.json` içinde `max_input_chars` ile ezilebilir.

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
├── app.py                     # Streamlit Web Arayüzü Ana Giriş Noktası
├── run_poc.py                 # CLI Benchmark & Batch Çalıştırma Sürücüsü
├── run.ps1                    # PowerShell Tek Tıkla Kurulum ve Başlatma Betiği
├── Dockerfile                 # Production Docker Img Yapılandırması
├── .dockerignore              # Docker Build Kapsamı Dışındaki Dosyalar
├── docker-compose.yml         # Opsiyonel Postgres Pipeline Checkpoint Servisi
├── .env.example               # SADECE API Key / Gizli Bilgiler Şablonu
├── .gitignore                 # Git Kapsamı Dışındaki Dosyalar
├── config.json                # Tüm Açık & Kapalı Kaynak LLM Yapılandırmaları
├── config.py                  # Merkezi Konfigürasyon ve Eşik Değerleri (Single Source of Truth)
├── requirements.txt           # Python Bağımlılıkları Listesi
├── docs/                      # Mimari, Kurumsal Sunum ve Değişiklik Dokümanları
│   ├── ARCHITECTURE.md        # Master Teknik Mimari & Pipeline El Kitabı
│   ├── EXECUTIVE_PRESENTATION_GUIDE.md # Kurumsal Sunum & Değer Önerisi Rehberi
│   └── CHANGELOG.md           # Proje Değişiklik Günlüğü (Sistem Hafızası)
├── data/bdr_samples/          # Örnek BDR Metin Verileri
├── prompts/                   # Markdown Prompt Şablonları
└── src/finside/
    ├── models/                # Pydantic Veri Şemaları ve Dataclass Modelleri
    │   ├── __init__.py
    │   └── schemas.py         # BDRRiskAnalysisReport, BenchmarkRequest vb.
    ├── services/              # İş Mantığı & Servis Katmanı
    │   ├── __init__.py
    │   └── benchmark_service.py # Paralel Model Benchmark Orkestrasyonu
    ├── ui/                    # Modüler UI Bileşenleri
    │   ├── __init__.py
    │   ├── sidebar.py         # Yan Kontrol Paneli
    │   └── tabs.py            # Görsel Sekme Bileşenleri & Kullanım Rehberi
    ├── loaders/               # BDR ve Prompt Yükleyiciler (DIP & SRP)
    ├── providers/             # LLM Sağlayıcı Stratejileri (Gemini, OpenAI, Claude, HF, Mock)
    ├── writers/               # Rapor ve Metrik Yazıcı Modülleri
    ├── chunking.py            # Yapı-Farkında Metin Bölümleme
    ├── dedupe.py              # Risk Tekleştirme
    ├── analyzer.py            # BDR Risk Analiz Orkestratörü
    └── report_md.py           # Rapor → Markdown Dönüştürücü
```