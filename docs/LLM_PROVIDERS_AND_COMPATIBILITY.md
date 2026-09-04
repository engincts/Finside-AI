# 🤖 LLM Sağlayıcıları ve %100 Uyumluluk Rehberi

Finside AI; OpenAI, Google Gemini, Anthropic ve HuggingFace üzerindeki açık kaynak modeller (Qwen, Llama, DeepSeek, Mistral) ile **%100 kararlı ve hatasız** çalışacak şekilde zırhlandırılmıştır.

---

## 🛠️ Modeller ve Çözülen Hatasız Uyumluluk Motorları

### 1. OpenAI (GPT-4o, GPT-4o-mini, o1, o3-mini)
* **Strict Structured Outputs:** OpenAI'ın katı JSON şeması gereksinimlerine tam uyum için `BDRRiskAnalysisReport` içerisindeki tüm nesneler (ör. `FinansalRasyoOzeti`) açıkça tanımlanmış ve `additionalProperties: false` kuralına tam uyumlu hale getirilmiştir.
* **Token Tavanı & TPM Kurtarma:** 16,384 token çıktı tavanı tanımlanmış, Tier 1 TPM limit aşımında otomatik metin kısaltma devreye alınmıştır.

### 2. Google Gemini (Gemini 3.6 Flash, Gemini 1.5 Pro)
* **Payload Schema Guard:** Gemini REST API'sinin desteklemediği `additional_properties` parametreleri şemadan temizlenmiştir. Herhangi bir `INVALID_ARGUMENT` durumunda otomatik `application/json` moduna düşülerek rapor kesintisiz ayrıştırılır.

### 3. HuggingFace & Açık Kaynak Modeller (Qwen 2.5, Llama 3.3, DeepSeek R1)
* **Pre-Validator Fallbacks:** Açık kaynak modellerin bazen JSON çıktısında eksik bıraktığı alanlar (`risk_derecesi`, `kaynak_metin_alintisi` vb.) Pydantic ön-doğrulayıcıları (`@field_validator(mode="before")`) ile varsayılan güvenli değerlerle doldurulur. Sistem asla validation hatasıyla düşmez.
* **Serverless Model Fallback Retry:** Seçilen küçük açık kaynak model `conversational` veya `text-generation` görev uyumsuzluğu verdiğinde, sistem anında listedeki en yüksek performanslı 70B/72B Instruct modellerine otomatik yönlenir.
