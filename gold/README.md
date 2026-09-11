# Altın (Gold) Set — Katman 3

Her dosya bir BDR için **insan-doğrulamalı beklenen çıktı**. Dosya adı BDR'nin stem'i:
`data/bdr_samples/0f7b….txt` → `gold/0f7b….json`.

## Nasıl hazırlanır (sıfırdan yazma, düzelt)

1. Bir BDR'yi pipeline **ve** güçlü bir modelle (Gemini 3 Pro) çalıştır.
2. `run_eval.py --hakem gemini-3.6-flash,claude-sonnet-4-5` ile hakem çıktısını al.
3. Hakemin `kacirilan_riskler` + raporun mevcut riskleri = aday liste.
4. Bu adayları **elle gözden geçir**, gerçek olanları `beklenen_riskler`'e taşı, `onem` ver.
5. `beklenen_denetci_gorusu` ve `beklenen_karar_araligi`'nı BDR'nin "Görüş" bölümünden doğrula.

5-8 BDR yeterli. Bu set senin **regresyon testin** olur: model/prompt değişince `gold recall` düşerse fark edersin.

## Alan şeması

| alan | açıklama |
| :-- | :-- |
| `kisa_baslik` | riskin özü (fuzzy başlık eşleşmesi için) |
| `anahtar_tutar` | ayırt edici tutar — "6.897.006 bin TL" gibi (sayısal eşleşme için) |
| `kaynak_ipucu` | dipnot no / bölüm — "Dipnot 21" (referans eşleşmesi için) |
| `onem` | `kritik` (2x) / `yuksek` (1.5x) / `orta` (1x) / `dusuk` (0.5x) — recall ağırlığı |

Eşleşme bu üç yoldan **herhangi biri** tutunca sağlanır.
