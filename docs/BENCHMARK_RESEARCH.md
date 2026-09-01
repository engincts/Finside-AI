# Finside AI — Açık & Kapalı Kaynak LLM Benchmark Araştırma Özet Raporu

**Konu:** Türkçe Bağımsız Denetim Raporu (BDR) Dipnot Analizi, Kredi Riski Yorumlama ve LLM Model Seçim Stratejisi (Açık & Kapalı Kaynak)  
**Tarih:** 31 Ağustos 2026  
**Doküman Sürümü:** v2.0 (Açık + Kapalı Kaynak Kapsamlı Araştırma)  

---

## 📌 1. TL;DR (Özet Bulgular)

1. **Kapalı Kaynak (Bulut) Modeller Mimarinin "Kalite Tavanını" Belirler**:
   - Kurumsal kredi risk analizi gibi karmaşık, çok adımlı muhakeme gerektiren görevlerde **Google Gemini (3.6 Flash / 3.1 Pro)**, **OpenAI (GPT-4o / o3-mini)** ve **Anthropic (Claude 3.5 Sonnet)** kapalı kaynak modelleri, %100 Strict JSON Schema uyumu, derin muhakeme (reasoning effort) ve düşük hata oranıyla kalite tavanını (benchmark gold standard) oluşturur.
2. **Açık Kaynak (On-Prem) Modeller Veri Gizliliği ve Maliyet Dengesi Sunar**:
   - Türkiye bankacılık ve BDDK düzenlemeleri gereği müşteri verisinin dışarı çıkamayacağı canlı ortamlarda **Qwen2.5-72B**, **Llama-3.3-70B**, **Qwen3-32B** ve **Gemma-3-27B** en güçlü açık kaynak adaylardır.
3. **CETVEL EACL 2026 & TR-MMLU Bulguları**:
   - Türkçe MMLU sıralaması: **Qwen2.5-72B %77.28**, Llama-3.1-70B %74.00, Qwen2.5-32B %70.93, Gemma-3-27B %70.20.
4. **Uzun Bağlam Kırılganlığı (EMNLP 2024 Gupta et al.)**:
   - Hem açık hem kapalı kaynak modellerde 32K üzeri bağlamlarda finansal muhakeme performansı ciddi oranlarda düşmektedir. Dipnotlar bölüm bazlı RAG/parçalama ile beslenmelidir.

---

## ☁️ 2. Kapalı Kaynak (Closed-Source / Bulut) LLM Analiz & Karşılaştırma

| Model Adı | Sağlayıcı | Bağlam | Muhakeme (Reasoning) Yeteneği | Strict JSON Uyumluğu | Türkçe Kalitesi | Öncelikli Kullanım Senaryosu |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Google Gemini 3.6 Flash** | Google Cloud | 1M+ | Yüksek (Ayarlanabilir) | **%100 Yerleşik Pydantic** | ⭐⭐⭐⭐⭐ (Çok Yüksek) | Hızlı & Derin Analiz POC Dengesi |
| **Google Gemini 3.1 Pro** | Google Cloud | 2M+ | **Çok Yüksek (Amiral)** | **%100 Yerleşik Pydantic** | ⭐⭐⭐⭐⭐ (Çok Yüksek) | En Karmaşık Kredi Kararları (Gold Standard) |
| **OpenAI GPT-4o** | OpenAI | 128K | Yüksek | **%100 Pydantic Parse** | ⭐⭐⭐⭐⭐ (Çok Yüksek) | Genel Raporlama ve Şema Güvenilirliği |
| **OpenAI o3-mini** | OpenAI | 200K | **Derin Sözel Muhakeme (o1/o3)** | **%100 Pydantic Parse** | ⭐⭐⭐⭐ (Yüksek) | Çoklu Dipnot Risk Çaprazlama & Covenant Üretimi |
| **Claude Sonnet 4.5** | Anthropic | 200K | Yüksek | **%100 Forced Tool-Use** | ⭐⭐⭐⭐⭐ (İhtiyatlı Bankacı Dili) | Hukuki / İhtiyatlı Analist Raporlaması |
| **DeepSeek-R1 (API)** | DeepSeek / Cloud | 128K | **Derin Muhakeme (RL)** | Orta-Yüksek | ⭐⭐⭐⭐ (Yüksek) | Düşük Maliyetli Derin Muhakeme |

### 🔍 Kapalı Kaynak Modellerin Güçlü Yanları:
- **Strict JSON Schema Zorlaması**: OpenAI `beta.chat.completions.parse` ve Gemini `response_schema` yetenekleri sayesinde Pydantic şema hataları %0'a yakındır.
- **Sözel Düşünme Bütçesi (`reasoning_effort`)**: OpenAI `o3-mini` ve Gemini `thinking_budget` parametreleriyle modelin cevabı üretmeden önce binlerce token harcayarak riskleri tartması sağlanır.
- **Hukuki ve İhtiyatlı Üslup**: Claude 3.5 Sonnet ve Gemini 3.1 Pro, Kredi Komitesi'nin beklediği muhafazakar bankacılık jargonu konusunda en olgun modellerdir.

---

## 🌐 3. Açık Kaynak (Open-Source / On-Prem) LLM Karşılaştırma

| Model | Model Tipi | Bağlam | TR-MMLU Skoru | CETVEL Derecesi | Lisans | On-Prem Donanım Gereksinimi |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Qwen2.5-72B-Instruct** | Açık Kaynak | 128K | **%77.28 (#1)** | Üst Segment | Qwen License | 2× A100 (80GB) / 48GB+ VRAM |
| **Llama-3.3-70B-Instruct** | Açık Ağırlık | 128K | %74.00 | **Genel #1** | Llama Community | 2× A100 (80GB) / 40GB+ VRAM |
| **Qwen3-32B-Instruct** | Açık Kaynak | 128K | High (Est.) | Yüksek | **Apache 2.0** | Tek A100 80GB / 2×24GB GPU |
| **Gemma-3-27B-IT** | Açık Ağırlık | 128K | **%70.20** | Yüksek | Gemma License | Tek 24–48GB GPU |
| **Gemma-3-12B-IT** | Açık Ağırlık | 128K | %63.92 | Orta | Gemma License | Tek 24GB RTX 4090 |
| **Mistral-Small-24B** | Açık Kaynak | 128K | - | Orta-Üst | **Apache 2.0** | Tek 24GB RTX 4090 |
| **Fin-R1-7B** | Açık Kaynak (RL) | 32K | - | Fin-QA #2 | **MIT** | Tek 16GB GPU |
| **Mihenk-LLM-v2-35B** | Açık Ağırlık | 32K | Yayınlanmadı | - | MIT | Test / Deneysel |
| **Commencis-LLM** | Açık Ağırlık | 32K | Yayınlanmadı | - | Apache 2.0 | Test / Deneysel |

---

## 🧠 4. Finansal LLM'ler ve Türkçe Fine-Tune Analizi

- **FinGPT & FinMA (NeurIPS 2023/2024)**:
  - Sınıflandırma ve haber duygu analizinde (sentiment) başarılıdır ancak Kredi Komitesi Raporu gibi uzun serbest rapor üretiminde genel modellerin gerisindedir.
- **Fin-R1 (SUFE - Mart 2025)**:
  - Qwen2.5-7B tabanlı, RL (GRPO) ile eğitilmiş modeldir. FinQA benchmark'ında DeepSeek-R1-Distill-Llama-70B'yi geride bırakmıştır ancak İngilizce/Çince ve dar sayısal Soru-Cevap odaklıdır.
- **Türkçe Finansal Fine-Tune'lar (Mihenk 35B, WiroAI)**:
  - Açık lisanslıdır ancak bağımsız/yayınlanmış akademik benchmark'ları (TR-MMLU/CETVEL) yoktur. Tek başlarına üretim kararlarına referans alınmamalı, yanlarında Qwen2.5-72B veya Gemma-3-27B gibi doğrulanmış modellerle kıyaslanmalıdır.

---

## ⚠️ 5. Uzun Bağlam (Long-Context) Kırılganlık Uyarısı

- EMNLP 2024'te Gupta ve arkadaşlarının yayınladığı araştırmaya göre:
  - Finansal metinlerin boyutu uzadıkça (özellikle **32K token üzerinde**), hem açık hem kapalı kaynak modellerin çok adımlı finansal konsept birleştirme yeteneği düşmektedir.
  - GPT-4-Turbo dahi 128K bağlamda en zorlu finansal görevlerde %42 oranında tekrarlı/bozuk çıktı üretmiştir.
- **Mimari Çözüm**: BDR dipnotlarının tamamını devasa tek bir prompt'a koymak yerine; *Dava/Hukuki İhtilaflar*, *TRİ/Rehin/İpotek*, *Net Yabancı Para Açık Pozisyonu*, *Vergi Tarhiyatları* şeklinde bölüm bazlı **RAG + Bölümlendirilmiş Yapılandırılmış Prompt** mimarisi kullanılmalıdır.
- ✅ **Uygulandı (2026-09-01):** yapı-farkında map-reduce chunking + sentez + embedding kapsama koruması — bkz. [ARCHITECTURE.md §4](ARCHITECTURE.md#4-büyük-girdi-yapı-farkında-map-reduce).

---

## 🎯 6. Hibrit Model & Mimari Yol Haritası (Cloud + On-Prem)

```
                       ┌─────────────────────────────────────────┐
                       │           Finside AI Motoru             │
                       └──────────────────┬──────────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
     【 POC & Kalite Referansı 】                      【 Canlı BDDK / KVKK On-Prem 】
   Kapalı Kaynak Bulut Modelleri                    Açık Kaynak Self-Hosted Modeller
 (Gemini 3.6 Flash / GPT-4o / Claude)             (Qwen3-32B / Gemma-3-27B / Qwen2.5-72B)
                  │                                               │
                  └───────────────────────┬───────────────────────┘
                                          ▼
                         【 In-House LoRA Adaptasyonu 】
                  (Banka Verisi İle Özelleştirilmiş Model)
```

1. **Faz 1 (POC - Kalite Referansı)**:
   - `gemini-3.6-flash` ve `gpt-4o` kullanılarak kalite tavanı (gold standard) belirlenir.
2. **Faz 2 (Canlı On-Premises Kurulum)**:
   - Müşteri verisi banka içinde kalacak şekilde **Qwen3-32B** veya **Gemma-3-27B** local GPU sunucularına dağıtılır.
3. **Faz 3 (In-House Fine-Tuning)**:
   - Bankanın geçmiş Kredi Komitesi Raporları ve anonimleştirilmiş BDR veri seti ile Qwen3-32B modeli LoRA/QLoRA yöntemiyle kuruma özel fine-tune edilir.

---

## ⚖️ 7. Yasal, Regülatör & XAI Çerçevesi

- **BDDK & KVKK Uyumluğu**:
  - Kredi kararlarında yapay zeka kullanımı doğrudan "otomatik karar" olarak konumlandırılamaz; sistem **Karar Destek Sistemi (Decision Support System)** olarak çalışmalıdır.
- **Açıklanabilir AI (XAI)**:
  - Üretilen her risk kalemi BDR metninden **doğrudan alıntı (`kaynak_metin_alintisi`)** ve **dipnot referansı (`dipnot_referansi`)** içermek zorundadır.
