# Finside AI — Otonom Kurumsal Kredi Tahsis & Karar Destek Sistemi

Finside AI, kurumsal kredi tahsis süreçlerinde kullanılan yapılandırılmış finansal veriler (mizan, e-defter, rasyolar) ile yapılandırılmamış metinleri (Bağımsız Denetim Raporu / BDR dipnotları — dava, rehin, kefalet, koşullu yükümlülük gibi kalitatif risk unsurları) birlikte analiz edip, açıklanabilir (XAI) ve gerekçeli bir "Kredi Komitesi Raporu" üreten karar destek sistemidir.

---

## 🚀 Max Tokens & Muhakeme Kapasitesi (8192 - 16384 Tokens)

Modellerin çıktı uzunluğu ve derin muhakeme (reasoning effort) tavanı maksimum seviyeye yükseltilmiştir:

- **Google Gemini (3.6 Flash / 3.1 Pro)**: `16,384 max_tokens` + `high reasoning_effort`
- **OpenAI (GPT-4o, o3-mini)**: `16,384 max_tokens` + `high reasoning_effort`
- **Anthropic (Claude 3.5 Sonnet)**: `8,192 max_tokens`
- **Açık Kaynak Lider Modeller (Qwen 72B, Llama 3.3 70B, Qwen3 32B, Gemma 3 27B, DeepSeek V3)**: `8,192 max_tokens`

---

## 📦 Proje Bağımlılıkları (`requirements.txt`)

1. **Temel Şema & Konfigürasyon**: `pydantic>=2.0.0`, `python-dotenv>=1.0.0`
2. **Kapalı Kaynak LLM SDK'ları**: `google-genai>=0.1.0`, `google-generativeai>=0.8.0`, `openai>=1.0.0`, `anthropic>=0.20.0`
3. **Açık Kaynak & Serverless Inference**: `huggingface-hub>=0.20.0`
4. **Web UI & Dashboard**: `streamlit>=1.30.0`, `pandas>=2.0.0`
5. **HTTP & Ağ Katmanı**: `requests>=2.28.0`, `httpx>=0.25.0`

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
│       │   ├── base.py        # BaseProvider Soyut Sınıfı (8192-16384 Max Tokens)
│       │   ├── gemini_provider.py
│       │   ├── openai_provider.py
│       │   ├── anthropic_provider.py
│       │   ├── huggingface_provider.py
│       │   ├── mock_provider.py
│       │   └── factory.py     # ProviderFactory Fabrika Sınıfı
│       ├── writers/           # Dosya I/O & Rapor Yazıcı Modülleri
│       │   ├── __init__.py
│       │   └── report_writer.py
│       ├── analyzer.py        # SOLID Orchestrator
│       └── __init__.py
├── outputs/                   # Tarih ve saat bazlı hiyerarşik klasörler
└── run_poc.py                 # CLI orkestratör betiği
```