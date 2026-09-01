# Finside AI — Multi-Agent BDR Analiz Pipeline Tasarımı

**Doküman Sürümü:** v0.2 (tasarım — kod yok)
**Tarih:** 1 Eylül 2026
**Durum:** Karar noktaları çözüldü (§11). Faz 0'dan başlanarak uygulanmaya hazır.

Bu doküman, "Multi-Agent BDR Analiz Pipeline" görev listesinin (LangGraph tabanlı 10 fazlı
plan) mevcut kod tabanına nasıl oturacağını tanımlar: LangGraph state şeması, node imzaları,
her fazın hangi mevcut modülü kullandığı/genişlettiği, yeni dosya yapısı, maliyet modeli ve
test stratejisi.

İlgili: [ARCHITECTURE.md](ARCHITECTURE.md) (mevcut tek-model motoru) · [CHANGELOG.md](CHANGELOG.md)

---

## 1. İlkeler

1. **Kalite > Hız > Maliyet.** Uzun süren, çok çağrılı bir pipeline kabul edilir; çıktı en iyi olmalı.
2. **Recall-odaklı.** Bir riski kaçırmak, fazladan bir riski işaretlemekten kötüdür. Ayrı bir "eksik tarama" (critic) adımı zorunlu.
3. **Mevcut SOLID mimari korunur.** `providers/` (Factory), `schemas.py` (Pydantic + normalizer), `writers/`, `loaders/` aynen kalır. Yeni modüller bunları çağıran ince katmanlardır.
4. **Segmentasyon opsiyonel değil.** Ham BDR ~593K karakter / ~148K token; 32K token üstünde uzun-bağlam kalite kaybı belgelenmiş.
5. **Mock-first geliştirme.** Topoloji, state akışı, reducer'lar, critic döngüsü, batch resume — hepsi `MockProvider` ile test edilir. Gerçek API testi yalnızca kullanıcı onayıyla, tek BDR.

---

## 2. Neden LangGraph

| İhtiyaç | LangGraph karşılığı |
|---|---|
| Batch'te bir BDR hata alırsa yalnızca o thread, yalnızca başarısız node'dan devam etsin | Checkpointer **`PostgresSaver`** (birim testlerde `MemorySaver`) + `thread_id` |
| Segment grubu × model paralel dağıtım | `Send` API |
| Paralel worker'ların ürettiği risk listelerinin elle merge kodu olmadan birleşmesi | `Annotated[List[...], operator.add]` reducer |
| Critic "eksik var → uzlaştırmaya geri dön" döngüsü | Conditional edge + döngü (max-tur koruması ile) |
| UI'da adım adım akış görselleştirme | `graph.stream(stream_mode="updates")` |

Alternatif (düz `asyncio` + mevcut `ThreadPoolExecutor`) mümkündür ama batch resume ve
otomatik merge'i elle yazmak gerekir. Batch + resume gerçek bir gereksinim olduğu için
LangGraph maliyetini hak ediyor.

---

## 3. Üst Düzey Akış

```
                 ┌────────────────────────────────────────────────┐
   BDR .txt ───► │ segmentle (Faz 1)                              │
                 │   regex → güven skoru → düşükse llm_segmenter   │
                 └───────────────┬────────────────────────────────┘
                                 ▼
                 ┌────────────────────────────────────────────────┐
                 │ triyaj_yap (Faz 2)                              │
                 │   kural filtre + şüpheli kova + ucuz LLM ikili  │
                 └───────────────┬────────────────────────────────┘
                                 ▼
                 ┌────────────────────────────────────────────────┐
                 │ gruplari_olustur (token bütçesine göre)         │
                 └───────────────┬────────────────────────────────┘
                                 │  Send( (grup, model) )  —  G×M paralel
                 ┌───────────────▼────────────────────────────────┐
                 │ map_worker (Faz 3)  →  map_ciktilari [+]        │
                 └───────────────┬────────────────────────────────┘
                                 │  Send( grup )  —  G paralel · her biri group_graph subgraph'ı
                 ┌───────────────▼────────────────────────────────┐
                 │ group_graph (subgraph, Faz 4-6)                 │
                 │   ground (rapidfuzz) → reconcile (LLM)          │
                 │        ▲                        │                │
                 │        └──eksik & tur<max───── critic (LLM)      │
                 │                                 │ yok/max        │
                 │                            grup_bitir            │
                 │   → uzlastirilmis_riskler [+] (ana state'e)      │
                 └───────────────┬────────────────────────────────┘
                                 ▼
                 ┌────────────────────────────────────────────────┐
                 │ sentezle (Faz 7)  —  ham metin YOK, sadece      │
                 │   risk listesi → özet/karar/gerekçe/şartlar     │
                 └───────────────┬────────────────────────────────┘
                                 ▼
                 ┌────────────────────────────────────────────────┐
                 │ qa_kontrol (Faz 8)  —  kural tabanlı bayraklar  │
                 └───────────────┬────────────────────────────────┘
                                 ▼
                 ┌────────────────────────────────────────────────┐
                 │ maliyet_ozetle (Faz 10)  →  END                 │
                 └────────────────────────────────────────────────┘
```

Batch (Faz 9): her BDR ayrı `thread_id` ile bu grafiği çalıştırır.

---

## 4. LangGraph State Şeması

`src/finside/pipeline/state.py`

```python
class Segment(TypedDict):
    sira_no: int
    baslik: str
    ham_metin: str
    karakter_sayisi: int
    baslangic_offset: int
    bitis_offset: int

class TriajKarari(TypedDict):
    segment_sira_no: int
    dahil: bool
    yontem: Literal["kural", "boilerplate", "llm"]
    gerekce: str

class SegmentGrubu(TypedDict):
    grup_id: int
    segment_sira_nolari: list[int]
    birlesik_metin: str
    tahmini_token: int

class MapCiktisi(TypedDict):
    grup_id: int
    model_id: str
    riskler: list[dict]          # BDRRiskItem.model_dump()
    hata_durumu: Optional[str]
    sure_sn: float

class TraceKaydi(TypedDict):
    asama: str
    model_id: Optional[str]
    girdi_karakter: int
    cikti_ozet: str
    sure_sn: float
    basari: bool
    hata: Optional[str]

class PipelineState(TypedDict):
    # --- girdi ---
    bdr_id: str
    bdr_adi: str
    ham_metin: str
    session_dir: str
    secili_map_modelleri: list[str]   # UI'dan seçilir; boşsa config.pipeline.map_models

    # --- Faz 1 ---
    segmentler: list[Segment]
    segmentasyon_guven: float
    segmentasyon_yontemi: Literal["regex", "llm_fallback"]

    # --- Faz 2 ---
    triaj_kararlari: list[TriajKarari]
    analiz_edilecek_sira_nolari: list[int]

    # --- Faz 3 ---
    segment_gruplari: list[SegmentGrubu]
    map_ciktilari: Annotated[list[MapCiktisi], operator.add]

    # --- Faz 4-6 (grup başına) ---
    uzlastirilmis_riskler: Annotated[list[dict], operator.add]
    celiskiler: Annotated[list[dict], operator.add]
    critic_turlari: Annotated[list[dict], operator.add]   # {grup_id, tur, eklenen}

    # --- Faz 7 ---
    nihai_rapor: dict            # BDRRiskAnalysisReport.model_dump()

    # --- Faz 8 ---
    qa_bayraklari: list[str]

    # --- Faz 10 / trace ---
    trace: Annotated[list[TraceKaydi], operator.add]
    maliyet_ozeti: dict
```

**Not:** Pydantic nesneleri state'te `dict` olarak taşınır (LangGraph serileştirme +
checkpoint uyumu için). Node sınırlarında `BDRRiskItem.model_validate(d)` /
`.model_dump()` ile çevrilir. Şema doğrulaması (enum normalizasyonu dahil) bu çevrimlerde
otomatik çalışır.

---

## 5. Modül Yapısı

```
src/finside/
├── chunking.py                 # KORUNUR — saf regex bölümleme (split_sections, pack_sections)
├── dedupe.py                   # KORUNUR — critic'in mekanik ön-filtresi olarak yeniden kullanılır
├── analyzer.py                 # KORUNUR — tek-model "hızlı analiz" servisi (UI/CLI legacy yolu)
├── providers/                  # KORUNUR — hiç değişmez (yalnızca Faz 0: hata alanı doldurma)
├── loaders/
│   ├── bdr_loader.py           # KORUNUR
│   ├── prompt_loader.py        # KORUNUR
│   └── bdr_segmenter.py        # YENİ — Faz 1 orkestrasyonu (chunking.py + güven + LLM fallback)
├── pipeline/                   # YENİ PAKET — LangGraph katmanı
│   ├── state.py                # PipelineState + GrupState + TypedDict'ler
│   ├── graph.py                # Ana StateGraph — segment→triage→map(Send)→grup(Send)→sentez→qa→cost
│   ├── group_graph.py          # Alt-graf (subgraph) — ground → reconcile ⇄ critic (cycle) → bitir
│   ├── nodes/
│   │   ├── segment.py          # segmentle
│   │   ├── triage.py           # triyaj_yap + gruplari_olustur
│   │   ├── map_extract.py      # map_worker (Send hedefi)
│   │   ├── synthesis.py        # sentezle
│   │   ├── qa.py               # qa_kontrol
│   │   └── cost.py             # maliyet_ozetle
│   ├── grounding.py            # YENİ — rapidfuzz alıntı doğrulama (LLM YOK)
│   ├── reconciler.py           # YENİ — çoklu model çıktısını tek listeye indirger (LLM)
│   ├── critic.py               # YENİ — eksik tarama (LLM) + dedupe.py ön-filtresi
│   ├── qa_rules.py             # YENİ — kural tabanlı tutarlılık kontrolleri (LLM YOK)
│   ├── llm_call.py             # YENİ — trace'li tek LLM çağrı sarmalayıcı (ProviderFactory üstüne)
│   └── batch.py                # YENİ — Faz 9 batch runner
├── writers/
│   └── report_writer.py        # GENİŞLETİLİR — trace.jsonl, segments.json, triage_log.json, portföy özeti
└── config.py                   # GENİŞLETİLİR — "pipeline" bloğu okuma

prompts/
├── bdr_analyst_v1.md           # KORUNUR — map (çıkarım) promptu
├── segmenter_v1.md             # YENİ — LLM segmenter fallback
├── triage_v1.md                # YENİ — ucuz ikili sınıflandırma
├── reconciler_v1.md            # YENİ
├── critic_v1.md                # YENİ
├── synthesis_v1.md             # YENİ — risk listesi → nihai rapor (ham metin görmez)
├── few_shot_examples/          # YENİ (Faz 9.5)
└── schemas.py                  # GENİŞLETİLİR — küçük eklemeler (aşağıda)
```

---

## 6. Faz Faz Tasarım

### Faz 0 — Altyapı

| İş | Detay | Mevcut kod |
|---|---|---|
| LangGraph kurulumu | `requirements.txt`'e `langgraph`, `langgraph-checkpoint-postgres`, `psycopg[binary]`, `rapidfuzz` (sürümler Faz 0'da pinlenir). Postgres bağlantısı `.env`'de `PIPELINE_DB_URL`. Yerel Postgres yoksa Docker tek satır (`docker run postgres`) — kurulum + paket ekleme onayı ayrıca istenir. | — |
| Hata şeffaflığı | Şemada `is_mock_fallback` + `fallback_reason` **zaten var**; `save_summary_metrics`'te "Fallback Durumu" sütunu **zaten var**. Ek `hata_durumu` alanı **gereksiz** — mevcut alanlar kullanılır. Sadece: her provider `except`'i `fallback_reason`'ı dolduruyor mu diye denetlenir (Anthropic/HF/Gemini/OpenAI → evet). | `schemas.py`, `report_writer.py` |
| Trace mekanizması | `pipeline/llm_call.py`: her LLM çağrısını `{asama, model_id, girdi_karakter, sure_sn, basari, hata}` olarak `state.trace`'e ekler; `ReportWriter` bunu `outputs/.../trace.jsonl`'e yazar. | yeni + `report_writer.py` |
| `reasoning_effort` → `max_tokens` | `BaseProvider.EFFORT_TOKEN_MAP` **zaten var** ama sadece token tavanına etki ediyor. Gemini `thinking_config`, OpenAI `o1/o3 reasoning_effort` uyguluyor; Anthropic/HF'de sözel etki yok (model desteklemiyor). Yapılacak: davranışı doküman + tabloya net yaz, kod tutarlılığı zaten mevcut. | `providers/base.py` |
| `BDRAnalyzer` konumu | `analyzer.py` "tek model, kendi içinde chunk'layan hızlı analiz" servisi olarak **kalır** (mevcut `app.py`/`run_poc.py` bunu kullanmaya devam eder). Pipeline onu **kullanmaz** — pipeline kendi segmentasyonunu yaptığı için `map_worker` doğrudan `ProviderFactory` + `BaseProvider.analyze` çağırır. İki yol paralel yaşar. | `analyzer.py` değişmez |

### Faz 1 — Segmentasyon (`loaders/bdr_segmenter.py`)

- **Girdi:** `ham_metin`. **Çıktı:** `segmentler`, `segmentasyon_guven`, `segmentasyon_yontemi`.
- Birincil: `chunking.split_sections` (mevcut regex — `NOT \d+`, `DİPNOT \d+`, numaralı başlık, BÜYÜK HARF) genişletilir: Romen rakamı (`^[IVXLC]+\.`), "Ek 1", alt-dipnot (`21.a`).
- Her segment: `{sira_no, baslik, ham_metin, karakter_sayisi, baslangic_offset, bitis_offset}` (offset'ler `str.find` ile).
- **Güven skoru** `segmentation_confidence(segmentler)`: (a) segment sayısı beklenen aralıkta mı (BDR tipik 25-60 dipnot), (b) numaralandırma monoton artan mı, (c) ortalama segment boyu makul mü (>200 & <60K karakter), (d) "İÇİNDEKİLER"/"NOT 1" çapa başlıkları bulundu mu. 0.0-1.0.
- Güven `< PIPELINE.segmenter_guven_esigi` (öneri 0.6) ise **LLM segmenter fallback**: `prompts/segmenter_v1.md` + `PIPELINE.segmenter_fallback_model` → JSON `[{baslik, baslangic_ipucu}]`; ipuçları ham metinde `rapidfuzz` ile konumlanır.
- `writers`: `segments.json` yazılır.
- **LLM çağrısı:** 0 (güven yüksekse) veya 1.

### Faz 2 — Triyaj (`pipeline/nodes/triage.py`)

- **Girdi:** `segmentler`. **Çıktı:** `triaj_kararlari`, `analiz_edilecek_sira_nolari`, `segment_gruplari`.
- **Kural filtre:** `RiskKategorisi` enum'ının anahtar-kelime haritası (`schemas.normalize_risk_kategorisi` içindeki mantık **tersine** — bir yardımcı fonksiyona çıkarılır, tek kaynak) segment `baslik` + ilk ~400 karaktere uygulanır. Eşleşen → `dahil=True, yontem="kural"`.
- **Boilerplate elemesi:** bilinen standart başlıklar ("Sunum esasları", "Yeni standartlar", "Muhasebe politikaları" özet paragrafları) → `dahil=False, yontem="boilerplate"`.
- **Şüpheli kova:** ne kurala ne boilerplate'e uyan → ucuz model (`PIPELINE.triage_model`, düşük `reasoning_effort`, `max_tokens≈256`), `prompts/triage_v1.md`: *"Bu metin kredi riski açısından önemli bir unsur içeriyor mu? evet/hayır + tek cümle gerekçe"* → `dahil`, `yontem="llm"`.
- `writers`: `triage_log.json` (her segment: dahil/hariç + gerekçe + yöntem).
- **Gruplama:** `chunking.pack_sections` (mevcut) — dahil edilen segmentlerin `ham_metin`'leri `PIPELINE.segment_grup_karakter_butcesi` (öneri ~88K karakter ≈ 22K token) ile paketlenir. Token tahmini karakter/4 heuristiği (tiktoken bağımlılığı eklenmez).
- **LLM çağrısı:** şüpheli segment sayısı kadar (tipik 3-8, ucuz model).

### Faz 3 — Map / Ensemble Çıkarım (`pipeline/nodes/map_extract.py`)

- Kullanılacak modeller: `state.secili_map_modelleri` (UI'dan) — boşsa `config.pipeline.map_models` (varsayılan ensemble). UI paneli config'deki listeyi ön-seçili gösterir, kullanıcı ekleyip çıkarabilir.
- Orkestratör `gruplari_olustur` sonrası: `[Send("map_worker", {"grup": g, "model_id": m}) for g in gruplar for m in modeller]`.
- `map_worker(payload)` → `ProviderFactory.create_provider(...)` + `BaseProvider.analyze(prompt)`; prompt = `analyzer.CHUNK_INSTRUCTION` benzeri sarım + grup birleşik metni. Çıktı `BDRRiskAnalysisReport` → yalnızca `tespit_edilen_riskler` alınır, her kaleme `kaynak_modeller=[model_id]` yazılır.
- Sonuç `MapCiktisi` olarak `map_ciktilari`'ne (`operator.add`) yazılır. Hata → `hata_durumu` dolu, `riskler=[]` (grup bu model için boş, diğer modeller devam).
- Varsayılan ensemble = 2-3 model (öneri: 1 güçlü kapalı + 1 güçlü açık + 1 Türkçe fine-tune).
- **LLM çağrısı:** `G × M` (paralel), tipik 9-18 (M = seçili model sayısı).

### Faz 4-6 — Grup Alt-Grafı (`pipeline/group_graph.py`)

Ana graf her grup için `Send("group_graph", GrupState(...))` yapar. `group_graph` ayrı
derlenmiş bir `StateGraph`'tır: `ground → reconcile → critic → route_critic` (conditional:
`reconcile`'e dön veya `grup_bitir`). `GrupState` = `{grup_id, birlesik_metin, ham_riskler,
taslak_riskler, celiskiler, critic_tur}`. `grup_bitir` sonucu ana state'in
`uzlastirilmis_riskler` / `celiskiler` / `critic_turlari` alanlarına (`operator.add`) yazar.

### Faz 4 — Grounding (`pipeline/grounding.py`) — LLM YOK

- `group_graph`'ın ilk node'u (`ground`). Her `BDRRiskItem.kaynak_metin_alintisi`, grubun `birlesik_metin`'inde `rapidfuzz.fuzz.partial_ratio` ile aranır.
- `< PIPELINE.grounding_esigi` (öneri 85) → risk `dogrulanmadi=True` işaretlenir (yeni opsiyonel şema alanı, bkz. §7).
- Nihai raporda `dogrulanmadi=True` kalemler "⚠️ kaynak doğrulanamadı" notuyla gösterilir (katı mod: `PIPELINE.grounding_katimod=True` ise elenir).
- **LLM çağrısı:** 0.

### Faz 5 — Uzlaştırma (`pipeline/reconciler.py`)

- `group_graph`'ın `reconcile` node'u. Bir grup için `M` modelden gelen risk listeleri:
  1. **Mekanik ön-birleştirme:** `analyzer._dedupe_risks` (başlık) + `dedupe.uncovered_risks` mantığı (embedding/Jaccard) ile yakın kalemler kümelenir.
  2. **Reconciler LLM çağrısı:** `prompts/reconciler_v1.md` + kümelenmiş ham çıktılar → tek, en eksiksiz `List[BDRRiskItem]`. Çelişkiler (`risk_derecesi` farkı vb.) `celiskiler`'e not düşülür; **en ihtiyatlı değer** seçilir (Yüksek > Orta > Düşük; Kritik en üstte).
- **LLM çağrısı:** grup başına 1.

### Faz 6 — Critic / Eksik Tarama (`pipeline/critic.py`)

- `group_graph`'ın `critic` node'u. **Girdi:** uzlaştırılmış taslak + grubun **orijinal tam metni**.
- Ön-filtre: `dedupe.uncovered_risks(map_ham_riskleri, taslak)` — hangi ham riskler taslakta yok? Bu liste critic prompt'una "özellikle şunlara bak" ipucu olarak verilir (LLM'i yönlendirir, kör aramadan iyi).
- **Critic LLM çağrısı:** `prompts/critic_v1.md`: *"Taslakta eksik/gözden kaçmış risk unsuru var mı? Varsa `BDRRiskItem` olarak ekle."*
- **LangGraph graph cycle:** `critic` node'undan `route_critic` conditional edge → eksik bulundu **ve** `critic_tur < PIPELINE.max_critic_turu` (öneri 2) ise `reconcile` node'una dön; yoksa `grup_bitir`. Her tur checkpoint'lenir (resume bir critic turunun ortasından devam edebilir).
- `critic_turlari`'ne `{grup_id, tur, eklenen_sayi}` yazılır.
- `route_critic` conditional edge: `eksik_var and critic_tur < max_critic_turu` → `reconcile` (cycle); değilse → `grup_bitir` → ana state'e `operator.add`.
- **LLM çağrısı:** grup başına 1 + (döngü sayısı × 1 reconcile + 1 critic), tipik grup başına 2-3.

### Faz 7 — Sentez (`pipeline/nodes/synthesis.py`)

- **Girdi:** tüm grupların `uzlastirilmis_riskler`'i (birleşik). **Ham BDR metni YOK.**
- Global dedup (`_dedupe_risks` + embedding kapsama) → nihai risk listesi.
- **Sentez LLM çağrısı:** `prompts/synthesis_v1.md` (segment metni değil, yapılandırılmış risk listesi alır) → `genel_kredi_risk_ozeti`, `karar_egilimi`, `analist_gerekce_metni`, `komite_tavsiyesi_ve_sartlar`. Firma künyesi Faz 1 segment 0'dan / triyajdan alınır.
- Faz 9.5: ilgili kategoriye en yakın 1-2 few-shot örneği prompt'a eklenir (anahtar kelime eşleşmesi).
- **LLM çağrısı:** 1.

### Faz 8 — Tutarlılık QA (`pipeline/qa_rules.py`) — LLM YOK

- `KRİTİK` risk var **&** `karar_egilimi == OLUMLU` → bayrak.
- `denetci_gorusu ∈ {OLUMSUZ, GÖRÜŞ BİLDİRMEKTEN KAÇINMA}` **&** `karar_egilimi == OLUMLU` → bayrak.
- `dogrulanmadi=True` risk oranı > %30 → bayrak.
- Hiç risk yok **&** segment sayısı > 20 → bayrak (muhtemel pipeline hatası).
- `qa_bayraklari` nihai rapora ve `summary_metrics`'e yazılır.
- **LLM çağrısı:** 0.

### Faz 9 — Batch (`pipeline/batch.py`, `run_poc.py --batch`)

- `run_poc.py --batch <klasör>`: klasördeki her `.txt` için `graph.invoke(state, config={"configurable": {"thread_id": bdr_id}})`.
- Checkpointer: **`PostgresSaver`** (`PIPELINE_DB_URL`, `.env`). Birim testlerde `MemorySaver`. Yerel Postgres Docker ile (`docker compose` girişi Faz 0'da eklenir).
- Hata → o `thread_id` başarısız node'dan devam edebilir (`graph.invoke` tekrar çağrısı). Graph cycle sayesinde bir critic turunun ortasından bile devam edilebilir.
- `outputs/<tarih>/<saat>/<bdr_adi>/` hiyerarşisi korunur.
- **Portföy özeti:** `outputs/<tarih>/<saat>/portfoy_ozeti.md` — firma, karar eğilimi, risk sayısı, QA bayrakları, kullanılan model ensemble'ı, maliyet.

### Faz 9.5 — Few-Shot Bankası

- `prompts/few_shot_examples/<kategori>/<ornek>.json` — `{bdr_parcasi, beklenen_cikti}`.
- Sentez (ve isteğe bağlı map) promptuna kategori anahtar kelimesiyle en yakın 1-2 örnek eklenir. Embedding yok.

### Faz 9.6 — UI Pipeline Akışı (`app.py`)

- Yeni "Pipeline Akışı" sekmesi: §3 diyagramı HTML/CSS kutularıyla; `graph.stream(stream_mode="updates")` çıktısı canlı okunur, aktif aşama vurgulanır.
- Bitince: aşama süreleri, paralel model sayısı, bulunan risk sayısı, QA bayrakları.
- **Engelleyici değil** — Faz 0-8 sonrası.

### Faz 10 — Maliyet/Süre Şeffaflığı

- `maliyet_ozetle` node'u `state.trace`'ten toplar: toplam çağrı (aşama kırılımı), toplam token (heuristik), toplam süre, tahmini USD (config'de model başına `usd_per_1k_in`/`usd_per_1k_out`).
- `summary_metrics.md`'ye eklenir. Amaç görünürlük, optimizasyon değil.

---

## 7. Şema Eklemeleri (`prompts/schemas.py`)

Minimal — mevcut alanlar bozulmaz, hepsi primitive/liste (strict schema sağlayıcılarını —
OpenAI `parse`, Gemini `response_schema`, Anthropic tool-use — bozmaz):

```python
class BDRRiskItem(BaseModel):
    ...
    dogrulanmadi: bool = Field(False, description="Faz 4: kaynak alıntısı ham metinde bulunamadı.")
    kaynak_modeller: List[str] = Field(default_factory=list, description="Faz 3: bu kalemi üreten map modelleri.")

class BDRRiskAnalysisReport(BaseModel):
    ...
    qa_bayraklari: List[str] = Field(default_factory=list, description="Faz 8 kural tabanlı uyarılar.")
```

- `pipeline_izi` (Faz 10 faz/çağrı/maliyet özeti) **Pydantic modele eklenmez** — serbest `dict`
  strict schema'yı bozar. Bunun yerine dosyaya yazılırken `{**report.model_dump(), "pipeline_izi": {...}}`
  olarak eklenir; ayrıca `trace.jsonl` ve `summary_metrics.md`'de tutulur.
- `hata_durumu` **eklenmez** — mevcut `is_mock_fallback` + `fallback_reason` yeterli.
- `dogrulanmadi` / `kaynak_modeller` map/sentez LLM'i tarafından da doldurulur ama Faz 3/4
  bunları deterministik olarak ezer; legacy `BDRAnalyzer` yolunda zararsız (varsayılan kalır).

---

## 8. Konfigürasyon (`config.json` — yeni `pipeline` bloğu)

```json
"pipeline": {
  "map_models": ["gemini-3.6-flash", "claude-sonnet-4-5", "hf-qwen-2.5-72b"],
  "triage_model": "gpt-4o-mini",
  "reconciler_model": "claude-sonnet-4-5",
  "critic_model": "gemini-3.6-flash",
  "synthesis_model": "claude-sonnet-4-5",
  "segmenter_fallback_model": "gemini-3.6-flash",
  "segmenter_guven_esigi": 0.6,
  "segment_grup_karakter_butcesi": 88000,
  "grounding_esigi": 85,
  "grounding_katimod": false,
  "max_critic_turu": 2
}
```

- `map_models` = **varsayılan** ensemble. UI'daki "Pipeline" panelinde bu liste ön-seçili gelir; kullanıcı çalıştırma başına ekleyip çıkarabilir → `state.secili_map_modelleri`. `run_poc.py --batch` varsayılanı kullanır (`--map-models a,b,c` ile ezilebilir).
- Diğer roller (triage/reconciler/critic/synthesis) config'de sabit — benchmark tutarlılığı için UI'dan değiştirilmez.
- `config.py`: `Config.get_pipeline_config()` — blok + varsayılanlar.
- `.env`: `PIPELINE_DB_URL=postgresql://finside:finside@localhost:5432/finside_pipeline`

---

## 9. Maliyet Modeli (BDR başına)

| Aşama | Çağrı (tipik) | Model sınıfı |
|---|---|---|
| Segmentasyon fallback | 0-1 | orta |
| Triyaj (şüpheli segment) | 3-8 | ucuz |
| Map (G grup × M model) | 9-18 | karışık |
| Grounding | 0 | — |
| Reconcile (grup başına) | 3-6 | güçlü |
| Critic (grup başına + döngü) | 5-12 | orta |
| Sentez | 1 | güçlü |
| QA | 0 | — |
| **Toplam** | **~21-46 LLM çağrısı** | |

Token: map çağrıları baskın (~22K girdi + ~4K çıktı). BDR başına kaba tahmin **500K-900K token**.
Batch ×50 BDR → **25-45M token**. → Geliştirme `MockProvider` ile; gerçek test tek BDR, `map_models` tek elemana indirilmiş halde, kullanıcı onayıyla.

---

## 10. Test Stratejisi

| Katman | Yöntem |
|---|---|
| Graph topolojisi, edge'ler, reducer'lar | `MockProvider` tüm rollerde; `graph.invoke` + state assert |
| Critic döngüsü + max-tur koruması | Mock critic "hep eksik var" döndürür → döngünün `max_critic_turu`'da durduğu doğrulanır |
| Batch resume | Mock node ortada `raise` → `thread_id` ile yeniden `invoke` → sadece kalan node'lar çalışır |
| Segmentasyon | Gerçek BDR, LLM yok — `segments.json` + güven skoru birim testi |
| Grounding | Gerçek metin + `rapidfuzz` — birim test |
| QA kuralları | Sentetik `BDRRiskAnalysisReport` — birim test |
| Uçtan uca duman | 1 gerçek BDR, `map_models=[tek model]`, kısa segment aralığı — **kullanıcı onayıyla** |

---

## 11. Kararlar (çözüldü — 1 Eylül 2026)

| # | Konu | Karar |
|---|---|---|
| 1 | Ensemble map modelleri | **UI'dan seçilebilir.** config `pipeline.map_models` varsayılan; `state.secili_map_modelleri` ezer. Diğer roller config'de sabit. |
| 2 | Critic döngüsü | **LangGraph graph cycle.** `group_graph` subgraph'ında `reconcile ⇄ critic`, `route_critic` conditional + `max_critic_turu` koruması. |
| 3 | Legacy `BDRAnalyzer` | **İki yol paralel yaşar.** `analyzer.py` mevcut UI/CLI "hızlı tek model" analizi için kalır; pipeline ayrı `pipeline/` paketi. |
| 4 | Checkpointer | **`PostgresSaver` baştan.** `PIPELINE_DB_URL` (.env), yerel Postgres Docker ile. Birim testlerde `MemorySaver`. |
| 5 | `app.py` entegrasyonu | Pipeline Streamlit'te ayrı thread'de (`ThreadPoolExecutor`), `graph.stream(stream_mode="updates")` kuyruğa yazar, UI kuyruğu okur — UI donmaz. |
| 6 | Bağımlılık sürümleri | Faz 0'da `requirements.txt`'e pinlenir; paket kurulumu + Postgres kurulumu ayrı onayla. |

---

## 12. Uygulama Sırası

| Adım | Fazlar | Çıktı | Durum |
|---|---|---|---|
| 1 | Faz 0 | LangGraph + trace + `llm_call.py` + şema eklemeleri | ✅ |
| 2 | Faz 1-2 | `bdr_segmenter.py`, triage node, `segments.json` / `triage_log.json`, `graph.py` | ✅ |
| 3 | Faz 3 | `map_extract.py` + `Send` fan-out + `MockProvider` E2E | ✅ |
| 4 | Faz 4-6 | `grounding.py`, `reconciler.py`, `critic.py`, `group_graph.py` + critic döngüsü | ✅ |
| 5 | Faz 7-8 | `synthesis.py`, `qa_rules.py` + `synthesis_v1.md` | ✅ |
| 6 | Faz 9-10 | `batch.py`, `run_poc.py --batch`, portföy özeti, maliyet | — |
| 7 | Faz 9.5-9.6 | few-shot bankası, UI akış paneli | — |
