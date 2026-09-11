"""Pipeline ilerleme çıktısı — `graph.stream(stream_mode="updates")` akışını
insanın anlayacağı, aşama aşama, gruplu/modelli bir rapora çevirir.

Saf sunum katmanı: LLM/IO yok. `asama_ozeti` (Streamlit checklist) durumsuzdur;
`ilerleme_takipcisi` (CLI akış logu) faz başına tek satır özet yazar.
"""

from typing import Callable, List

from config import Config

FAZ_ETIKETLERI = {
    "segmentle": "1 · Segmentasyon",
    "triyaj_yap": "2 · Triyaj",
    "gruplari_olustur": "2 · Gruplama",
    "map_worker": "3 · Ensemble Map çıkarımı",
    "map_topla": "3 · Map birleştirme",
    "grup_isle": "4-6 · Grounding + Uzlaştırma + Critic",
    "sentezle": "6.5-7 · Sanitizer + Sentez",
    "qa_kontrol": "8 · Tutarlılık QA",
    "maliyet_ozetle": "10 · Maliyet özeti",
}


def _liste(guncelleme: dict, anahtar: str) -> list:
    return guncelleme.get(anahtar) or []


def _ad(model_id: str) -> str:
    """Ham config id'si ("or-gpt-oss-120b") yerine config.json'daki okunabilir
    "name" alanını ("GPT-OSS-120B (OpenRouter)") döndürür."""
    cfg = Config.get_model_config_by_id(model_id)
    return cfg.get("name", model_id) if cfg else model_id


def model_rolleri_satiri(map_modelleri: List[str]) -> str:
    pc = Config.get_pipeline_config()
    san_m = pc.get("sanitizer_model", pc.get("critic_model", "—"))
    return (
        f"map (risk çıkarımı): {', '.join(_ad(m) for m in map_modelleri) or '—'}  ·  "
        f"triyaj: {_ad(pc['triage_model'])}  ·  uzlaştırma: {_ad(pc['reconciler_model'])}  ·  "
        f"critic: {_ad(pc['critic_model'])}  ·  sanitizer: {_ad(san_m)}  ·  sentez: {_ad(pc['synthesis_model'])}"
    )


def asama_ozeti(node: str, guncelleme: dict) -> str:
    """Bir node güncellemesinden tek satırlık özet (Streamlit checklist için). Boş → ''."""
    if not guncelleme:
        return ""

    if node == "segmentle":
        return (
            f"{len(_liste(guncelleme, 'segmentler'))} bölüm · "
            f"{guncelleme.get('segmentasyon_yontemi', '?')} · "
            f"güven %{round(100 * guncelleme.get('segmentasyon_guven', 0))}"
        )
    if node == "triyaj_yap":
        kararlar = _liste(guncelleme, "triaj_kararlari")
        dahil = len(_liste(guncelleme, "analiz_edilecek_sira_nolari"))
        kural = sum(1 for k in kararlar if k.get("yontem") == "kural")
        llm = sum(1 for k in kararlar if k.get("yontem") == "llm")
        return f"{dahil}/{len(kararlar)} bölüm analize alındı ({kural} kural + {llm} LLM)"
    if node == "gruplari_olustur":
        return f"{len(_liste(guncelleme, 'segment_gruplari'))} gruba paketlendi"
    if node == "map_worker":
        ciktilar = _liste(guncelleme, "map_ciktilari")
        ham = sum(len(c.get("riskler", [])) for c in ciktilar)
        hatali = sum(1 for c in ciktilar if c.get("hata_durumu"))
        s = f"{len(ciktilar)} (grup×model) tamam · {ham} ham risk"
        return s + (f" · {hatali} hata" if hatali else "")
    if node == "map_topla":
        return "ham riskler tek havuzda"
    if node == "grup_isle":
        riskler = _liste(guncelleme, "uzlastirilmis_riskler")
        turlar = _liste(guncelleme, "critic_turlari")
        eklenen = sum(t.get("son_eklenen", 0) for t in turlar)
        return f"{len(riskler)} uzlaştırılmış risk · critic +{eklenen}"
    if node == "sentezle":
        nihai = guncelleme.get("nihai_rapor") or {}
        return (
            f"{len(nihai.get('tespit_edilen_riskler', []))} nihai risk · "
            f"{nihai.get('firma_adi') or '—'}"
        )
    if node == "qa_kontrol":
        bayraklar = _liste(guncelleme, "qa_bayraklari")
        return "temiz (0 bayrak)" if not bayraklar else f"{len(bayraklar)} bayrak: " + " | ".join(bayraklar)
    if node == "maliyet_ozetle":
        m = guncelleme.get("maliyet_ozeti") or {}
        return (
            f"{m.get('toplam_llm_cagrisi', 0)} LLM çağrısı · "
            f"{m.get('toplam_sure_sn', 0)}s · ${m.get('tahmini_usd', 0)}"
        )
    return ""


def ilerleme_takipcisi(yaz: Callable[[str], None], map_modelleri: List[str]) -> Callable[[str, dict], None]:
    """Node güncellemelerini biriktirip zengin, çok satırlı CLI logu üreten geri-çağırım.

    `yaz` tek bir satır yazar (örn. `print`). Dönen fonksiyon `(node, guncelleme)` alır.
    """
    n_model = max(len(map_modelleri), 1)
    d = {"grup": 0, "map_bitti": 0, "map_toplam": 0, "ham": 0}

    def isle(node: str, u: dict) -> None:
        if node == "segmentle":
            segs = _liste(u, "segmentler")
            yaz(f"1 · Segmentasyon → {len(segs)} bölüm ({u.get('segmentasyon_yontemi', '?')}, "
                f"güven %{round(100 * u.get('segmentasyon_guven', 0))})")

        elif node == "triyaj_yap":
            kararlar = _liste(u, "triaj_kararlari")
            dahil = len(_liste(u, "analiz_edilecek_sira_nolari"))
            yaz(f"2 · Triyaj → {dahil}/{len(kararlar)} bölüm analize alındı")

        elif node == "gruplari_olustur":
            gruplar = _liste(u, "segment_gruplari")
            d["grup"] = len(gruplar)
            d["map_toplam"] = len(gruplar) * n_model
            yaz(f"3 · Map → {len(gruplar)} grup × {n_model} model = {d['map_toplam']} çıkarım")

        elif node == "map_worker":
            for c in _liste(u, "map_ciktilari"):
                d["map_bitti"] += 1
                risk_n = len(c.get("riskler") or [])
                d["ham"] += risk_n
                gid = c.get("grup_id", 0) + 1
                if c.get("hata_durumu"):
                    yaz(f"  ✗ grup {gid}/{d['grup']} · {c.get('model_id')} · {str(c['hata_durumu'])[:70]}")
                else:
                    yaz(f"  ✓ grup {gid}/{d['grup']} · {c.get('model_id')} → {risk_n} risk ({c.get('sure_sn', 0):.1f}s)")
            if d["map_toplam"] and d["map_bitti"] >= d["map_toplam"]:
                yaz(f"  = {d['ham']} ham risk")

        elif node == "grup_isle":
            riskler = _liste(u, "uzlastirilmis_riskler")
            eklenen = sum(t.get("son_eklenen", 0) for t in _liste(u, "critic_turlari"))
            yaz(f"4-6 · Grounding + Uzlaştırma + Critic → {len(riskler)} risk (critic +{eklenen})")

        elif node == "sentezle":
            nr = u.get("nihai_rapor") or {}
            yaz(f"6.5-7 · Sentez → {len(nr.get('tespit_edilen_riskler', []))} nihai risk · "
                f"{nr.get('firma_adi') or '—'}")

        elif node == "qa_kontrol":
            b = _liste(u, "qa_bayraklari")
            yaz("8 · QA → temiz" if not b else f"8 · QA → {len(b)} bayrak: " + " | ".join(b))

        elif node == "maliyet_ozetle":
            m = u.get("maliyet_ozeti") or {}
            yaz(f"10 · Maliyet → {m.get('toplam_llm_cagrisi', 0)} çağrı · "
                f"{m.get('toplam_sure_sn', 0)}s · ~${m.get('tahmini_usd', 0)}")

    return isle


__all__ = ["FAZ_ETIKETLERI", "asama_ozeti", "model_rolleri_satiri", "ilerleme_takipcisi"]
