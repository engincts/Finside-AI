# Finside AI — Otonom Kurumsal Kredi Tahsis & Karar Destek Sistemi

Finside AI, kurumsal kredi tahsis süreçlerinde kullanılan yapılandırılmış finansal veriler (mizan, e-defter, rasyolar) ile yapılandırılmamış metinleri (Bağımsız Denetim Raporu / BDR dipnotları — dava, rehin, kefalet, koşullu yükümlülük gibi kalitatif risk unsurları) birlikte analiz edip, açıklanabilir (XAI) ve gerekçeli bir "Kredi Komitesi Raporu" üreten karar destek sistemidir.

---

## 🚀 FAZ 1 — POC (Mevcut Aşama)

POC fazının ana hedefi; BDR metinlerini okuyup kıdemli bir kurumsal kredi risk analisti gözüyle riskleri tespit eden, süre/latans metriklerini ölçen ve kredi komitesi diliyle değerlendiren LLM tabanlı **"Finansal Analiz Uzmanı"** motorunu geliştirmektir.

### ✨ Türkçe Finansal Modeller & Gelişmiş Parametre Desteği

- **Açık Kaynak Türkçe LLM Entegrasyonu**:
  - `Commencis/Commencis-LLM` (Türkçe Genel/Finansal LLM)
  - `AlicanKiraz0/Mihenk-LLM-v2-35B-A3B-Turkish-Financial-Model` (Özel Türkçe Finansal LLM)
  - `Qwen/Qwen2.5-7B-Instruct`
- **Gelişmiş Çıkarım (Inference) Parametre Ezme Desteği**:
  - `temperature` (Örn: Commencis için `0.5`, Mihenk için `0.3`)
  - `top_p` (Örn: `0.9` nucleus sampling)
  - `repetition_penalty` (Örn: `1.0` - `1.05` tekrar önleme cezası)
  - `reasoning_effort` (`"high"`, `"medium"`, `"low"`, `"auto"`)
- **Net Sorumluluk Ayrımı (.env vs. config.json)**:
  - **`.env`**: **Sadece gizli anahtarlar ve API Key'ler** tutulur (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `HF_TOKEN`).
  - **`config.json`**: Tüm operasyonel model parametreleri yönetilir.
- **Saf Markdown Prompt Mimarisi (`prompts/*.md`)**: Prompt'lar `prompts/bdr_analyst_v1.md` dosyasında `## SYSTEM_PROMPT` ve `## USER_PROMPT` standartlarında tutulur.
- **Hiyerarşik Çıktı Düzenlemesi (`outputs/Tarih/Saat/BDR_Adi/`)**: `outputs/YYYY-MM-DD/HH-MM-SS/{bdr_adi}/` yapısında oturum klasörleri ve `summary_metrics.md` özet raporları üretilir.

---

## 📂 Dizin Yapısı

```
Finside-AI/
├── README.md                  # Proje dokümantasyonu (Canlı Referans)
├── .env.example               # SADECE API Key / Gizli Bilgiler Şablonu
├── .gitignore                 # Git kapsamı dışındaki dosyalar (.venv, outputs vb.)
├── config.json                # Dinamik model, parametre (top_p, repetition_penalty) ve prompt konfigürasyonu
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

## ⚙️ `config.json` Yapılandırma Örneği

```json
{
  "app_name": "Finside-AI POC Motoru",
  "default_temperature": 0.1,
  "default_max_tokens": 4096,
  "default_top_p": 0.9,
  "default_repetition_penalty": 1.0,
  "default_reasoning_effort": "medium",
  "default_strict_schema": true,
  "default_prompt_file": "bdr_analyst_v1.md",
  "models": [
    {
      "id": "hf-commencis-llm",
      "name": "HuggingFace Commencis-LLM (Türkçe LLM)",
      "provider": "huggingface",
      "model_name": "Commencis/Commencis-LLM",
      "api_key_env": "HF_TOKEN",
      "temperature": 0.5,
      "repetition_penalty": 1.0,
      "top_p": 0.9,
      "enabled": true
    },
    {
      "id": "hf-mihenk-financial-35b",
      "name": "HuggingFace Mihenk-LLM-v2-35B (Türkçe Finansal Model)",
      "provider": "huggingface",
      "model_name": "AlicanKiraz0/Mihenk-LLM-v2-35B-A3B-Turkish-Financial-Model",
      "api_key_env": "HF_TOKEN",
      "temperature": 0.3,
      "repetition_penalty": 1.05,
      "top_p": 0.9,
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