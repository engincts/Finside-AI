# Finside AI — Değerlendirme (Eval) Sistemi

Amaç: "Bu çıktı doğru mu? Hangi model/pipeline konfigürasyonu daha iyi?" sorusunu
**sayısal** cevaplamak. `src/finside/eval/` + `run_eval.py`.

## 3 Katman

| Katman | Dosya | API? | Ne ölçer |
| :-- | :-- | :-- | :-- |
| **1 — Otomatik** | `eval/metrics.py` | Hayır | Grounding oranı, sayısal tutarlılık, kategori kapsamı, jenerik etki oranı, QA bayrağı → `taban_puan` (0-100) |
| **2 — LLM Hakem** | `eval/judge.py` | Evet | Frontier model raporu ham BDR'ye karşı puanlar (recall/precision/derinlik/karar 1-5) + kaçırılan/hatalı risk listesi |
| **3 — Gold Set** | `eval/gold.py` | Hayır | `gold/<stem>.json` beklenen risklere karşı ağırlıklı recall, karar/görüş isabeti |

Katman 1 her zaman çalışır. Katman 2 `--hakem` verilince. Katman 3 `gold/<stem>.json` varsa.

## Kullanım

```bash
# Bir pipeline koşumunun tüm raporlarını değerlendir (offline)
python run_eval.py --klasor outputs/2026-09-08/09-13-49 --config pipeline-v1

# Tek rapor
python run_eval.py --rapor outputs/.../final_report.json \
                   --bdr data/bdr_samples/xxx.txt --config gemini-tek

# + LLM hakem (canlı API — maliyetli)
python run_eval.py --klasor outputs/... --config pipeline-v1 \
                   --hakem gemini-3.6-flash,claude-sonnet-4-5

# İki konfigürasyonu tek tabloda kıyasla
python run_eval.py --karsilastir eval/pipeline-v1 eval/gemini-tek
```

Çıktı: `eval/<config>/<bdr_stem>.json` (tam detay) + `eval/<config>/ozet.md` (kıyas tablosu).
`eval/` git'e girmez.

## Önerilen iş akışı (model seçimi)

1. **Hat A:** Gemini 3 Pro tek-geçiş → `--config gemini-tek`
2. **Hat B:** Mevcut pipeline → `--config pipeline-v1`
3. **Hat C:** Open-source pipeline → `--config oss-v1`
4. `python run_eval.py --karsilastir eval/gemini-tek eval/pipeline-v1 eval/oss-v1`
5. Gold set (5-8 BDR) hazırla (`gold/README.md`) → her değişiklikte regresyon kontrolü.

## `taban_puan` ağırlıkları (`metrics.taban_puan`)

grounding %40 · sayısal tutarlılık %20 · somut etki (1−jenerik) %15 · kategori kapsamı %10 · QA temizliği %15.
Ağırlıklar `metrics.py` içinde tek yerde; göreve göre ayarlanabilir.

## Hakem modeli notu

Büyük BDR'ler (600-900 KB ≈ 200K+ token) yalnızca Gemini'nin (1M+ context) tamamını görür.
`gpt-4o` / `claude-sonnet-4-5` hakem olarak kullanılınca metin sağlayıcı limitine kırpılır
(`bdr_kirpildi: true` işaretlenir). Tam-bağlam hakemlik için Gemini önerilir.
