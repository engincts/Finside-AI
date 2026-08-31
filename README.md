# Finside AI — Otonom Kurumsal Kredi Tahsis & Karar Destek Sistemi

Finside AI, kurumsal kredi tahsis süreçlerinde kullanılan yapılandırılmış finansal veriler (mizan, e-defter, rasyolar) ile yapılandırılmamış metinleri (Bağımsız Denetim Raporu / BDR dipnotları — dava, rehin, kefalet, koşullu yükümlülük gibi kalitatif risk unsurları) birlikte analiz edip, açıklanabilir (XAI) ve gerekçeli bir "Kredi Komitesi Raporu" üreten karar destek sistemidir.

---

## 🚀 FAZ 1 — POC (Mevcut Aşama)

POC fazının ana hedefi; BDR metinlerini okuyup kıdemli bir kurumsal kredi risk analisti gözüyle riskleri tespit eden, süre/latans metriklerini ölçen ve kredi komitesi diliyle değerlendiren LLM tabanlı **"Finansal Analiz Uzmanı"** motorunu geliştirmektir.

### ✨ Öne Çıkan Özellikler & Sorumluluk Ayrımı

- **Net Sorumluluk Ayrımı (.env vs. config.json)**:
  - **`.env`**: **Sadece gizli anahtarlar ve API Key'ler** tutulur (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `HF_TOKEN`).
  - **`config.json`**: Tüm operasyonel parametreler (`temperature`, `max_tokens`, `reasoning_effort`, `prompt_file`, `strict_schema`) yönetilir. Böylece parametre çakışmaları engellenir.
- **Saf Markdown Prompt Mimarisi (`prompts/*.md`)**: Prompt'lar `prompts/bdr_analyst_v1.md` gibi bağımsız `.md` dosyalarında tutulur.
- **Standart LLM Jargonu (`SYSTEM_PROMPT` ve `USER_PROMPT`)**: `## SYSTEM_PROMPT` ve `## USER_PROMPT` bölümleriyle ayrıştırılır.
- **SOLID Mimarisi**:
  - `PromptLoader`: Markdown prompt yükleme.
  - `ReportWriter`: Hiyerarşik klasörleme ve dosya I/O.
  - `BDRLoader`: BDR metin yükleme.
  - `BDRAnalyzer`: Multi-API analiz ve süre ölçümü.
- **Hiyerarşik Çıktı Düzenlemesi (`outputs/Tarih/Saat/BDR_Adi/`)**: `outputs/YYYY-MM-DD/HH-MM-SS/{bdr_adi}/` yapısında oturum klasörleri.

---

## 📂 Dizin Yapısı

```
Finside-AI/
├── README.md                  # Proje dokümantasyonu (Canlı Referans)
├── .env.example               # SADECE API Key / Gizli Bilgiler Şablonu
├── .gitignore                 # Git kapsamı dışındaki dosyalar (.venv, outputs vb.)
├── config.json                # Tüm Model, Parametre ve Prompt Konfigürasyonu
├── config.py                  # Konfigürasyon ve Env okuyucu
├── requirements.txt           # Python bağımlılıkları
├── data/
│   └── bdr_samples/           # BDR txt test verileri (Borusan 2024 BDR örneği dahil)
├── prompts/
│   ├── bdr_analyst_v1.md      # SYSTEM_PROMPT ve USER_PROMPT İçeren Markdown Şablonu
│   └── schemas.py             # Türkiye BDR Standartlarında Pydantic Rapor Şemaları
├── src/
│   └── finside/
│       ├── prompt_loader.py   # Markdown prompt şablon yükleyici (.md)
│       ├── bdr_loader.py      # BDR metin yükleyici
│       ├── analyzer.py        # Multi-API analiz ve süre ölçüm motoru
│       └── report_writer.py   # Dosya I/O ve metrik rapor yazıcı
├── outputs/                   # Tarih ve saat bazlı hiyerarşik klasörler
└── run_poc.py                 # CLI orkestratör betiği
```

---

## 🔑 `.env` Yapısı (Sadece Gizli Veriler)

```env
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
HF_TOKEN=your_huggingface_token_here
```

---

## ⚙️ `config.json` Yapılandırma Örneği

```json
{
  "app_name": "Finside-AI POC Motoru",
  "default_temperature": 0.1,
  "default_max_tokens": 4096,
  "default_reasoning_effort": "medium",
  "default_strict_schema": true,
  "default_prompt_file": "bdr_analyst_v1.md",
  "models": [
    {
      "id": "gemini-2.5-pro",
      "name": "Google Gemini 2.5 Pro",
      "provider": "gemini",
      "model_name": "gemini-2.5-pro",
      "api_key_env": "GEMINI_API_KEY",
      "reasoning_effort": "high",
      "prompt_file": "bdr_analyst_v1.md",
      "enabled": true
    }
  ]
}
```

---

## 🛠️ Kurulum & Kullanım

1. **Gereksinimlerin Yüklenmesi**:
   ```bash
   pip install -r requirements.txt
   ```

2. **BDR Analizini Çalıştırma**:
   ```bash
   python run_poc.py --input data/bdr_samples/borusan_bdr_2024.txt
   ```

   *Mock modda test etmek için:*
   ```bash
   python run_poc.py --input data/bdr_samples/borusan_bdr_2024.txt --mock
   ```