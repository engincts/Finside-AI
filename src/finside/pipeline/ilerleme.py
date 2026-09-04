"""Pipeline ilerleme çıktısı — `graph.stream(stream_mode="updates")` akışını
insanın anlayacağı, aşama aşama, gruplu/modelli bir rapora çevirir.

Saf sunum katmanı: LLM/IO yok. `asama_ozeti` (Streamlit checklist) durumsuzdur;
`ilerleme_takipcisi` (CLI akış logu) grup sayısı/model listesi gibi bağlamı biriktirir.
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
    "sentezle": "7 · Sentez",
    "qa_kontrol": "8 · Tutarlılık QA",
    "maliyet_ozetle": "10 · Maliyet özeti",
}


def _liste(guncelleme: dict, anahtar: str) -> list:
    return guncelleme.get(anahtar) or []


def model_rolleri_satiri(map_modelleri: List[str]) -> str:
    pc = Config.get_pipeline_config()
    return (
        f"map (risk çıkarımı): {', '.join(map_modelleri) or '—'}  ·  "
        f"triyaj: {pc['triage_model']}  ·  uzlaştırma: {pc['reconciler_model']}  ·  "
        f"critic: {pc['critic_model']}  ·  sentez: {pc['synthesis_model']}"
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
    pc = Config.get_pipeline_config()
    n_model = max(len(map_modelleri), 1)
    d = {"grup": 0, "map_bitti": 0, "map_toplam": 0, "grup_bitti": 0, "ham": 0}

    def yaz_alt(metin: str) -> None:
        yaz(f"     {metin}")

    def isle(node: str, u: dict) -> None:
        if node == "segmentle":
            segs = _liste(u, "segmentler")
            yontem = u.get("segmentasyon_yontemi", "?")
            nasil = "regex ile ayrıldı (LLM'e gerek kalmadı)" if yontem == "regex" \
                else "regex güveni düşüktü → LLM ile bölündü"
            yaz(f"▶ {FAZ_ETIKETLERI['segmentle']}")
            yaz_alt(f"BDR {len(segs)} bölüme ayrıldı · {nasil} · güven %{round(100 * u.get('segmentasyon_guven', 0))}")

        elif node == "triyaj_yap":
            kararlar = _liste(u, "triaj_kararlari")
            dahil = len(_liste(u, "analiz_edilecek_sira_nolari"))
            kural = sum(1 for k in kararlar if k.get("yontem") == "kural")
            llm = sum(1 for k in kararlar if k.get("yontem") == "llm")
            bp = sum(1 for k in kararlar if k.get("yontem") == "boilerplate")
            yaz(f"▶ {FAZ_ETIKETLERI['triyaj_yap']}  (hangi bölümler kredi riski taşıyor?)")
            yaz_alt(f"{len(kararlar)} bölüm tarandı → {dahil} analize alındı, {len(kararlar) - dahil} elendi")
            yaz_alt(f"{kural} bölüm kural (anahtar kelime) · {llm} bölüm LLM ({pc['triage_model']}) · {bp} boilerplate")

        elif node == "gruplari_olustur":
            gruplar = _liste(u, "segment_gruplari")
            d["grup"] = len(gruplar)
            d["map_toplam"] = len(gruplar) * n_model
            yaz(f"▶ {FAZ_ETIKETLERI['gruplari_olustur']}")
            yaz_alt(f"analize alınan bölümler {len(gruplar)} gruba paketlendi (LLM bağlam bütçesine göre)")
            yaz(f"▶ {FAZ_ETIKETLERI['map_worker']}  —  {len(gruplar)} grup × {n_model} model = {d['map_toplam']} paralel çıkarım")

        elif node == "map_worker":
            for c in _liste(u, "map_ciktilari"):
                d["map_bitti"] += 1
                risk_n = len(c.get("riskler") or [])
                d["ham"] += risk_n
                gid = c.get("grup_id", 0) + 1
                if c.get("hata_durumu"):
                    yaz_alt(f"✗ grup {gid}/{d['grup']} · {c.get('model_id')} · HATA: {str(c['hata_durumu'])[:70]}")
                else:
                    yaz_alt(f"✓ grup {gid}/{d['grup']} · {c.get('model_id')} → {risk_n} ham risk ({c.get('sure_sn', 0):.1f}s)")
            if d["map_toplam"] and d["map_bitti"] >= d["map_toplam"]:
                yaz_alt(f"= toplam {d['ham']} ham risk çıkarıldı")

        elif node == "map_topla":
            yaz(f"▶ {FAZ_ETIKETLERI['map_topla']}")
            yaz_alt("ham riskler tek havuzda toplandı, iz kaydı yazıldı")
            yaz(f"▶ {FAZ_ETIKETLERI['grup_isle']}  —  {d['grup']} grup ayrı ayrı işleniyor")
            yaz_alt("her grup: alıntı doğrulama → modelleri uzlaştırma → eksik tarama (critic)")

        elif node == "grup_isle":
            riskler = _liste(u, "uzlastirilmis_riskler")
            celiskiler = len(_liste(u, "celiskiler"))
            for t in _liste(u, "critic_turlari"):
                d["grup_bitti"] += 1
                gid = t.get("grup_id", 0) + 1
                yaz_alt(
                    f"✓ grup {gid}/{d['grup']} → {len(riskler)} uzlaştırılmış risk · "
                    f"critic +{t.get('son_eklenen', 0)} (tur {t.get('tur', 0)}) · {celiskiler} çelişki"
                )

        elif node == "sentezle":
            nr = u.get("nihai_rapor") or {}
            yaz(f"▶ {FAZ_ETIKETLERI['sentezle']}  (dedup + roll-up ele + kategori kurtar → nihai rapor)")
            yaz_alt(f"{len(nr.get('tespit_edilen_riskler', []))} nihai risk kalemi")
            yaz_alt(f"firma: {nr.get('firma_adi') or '—'} · dönem: {nr.get('rapor_donemi') or '—'} · görüş: {nr.get('denetci_gorusu') or '—'}")

        elif node == "qa_kontrol":
            b = _liste(u, "qa_bayraklari")
            yaz(f"▶ {FAZ_ETIKETLERI['qa_kontrol']}")
            yaz_alt("✓ temiz — hiçbir tutarsızlık bayrağı yok" if not b
                    else f"⚠ {len(b)} bayrak → " + "  ||  ".join(b))

        elif node == "maliyet_ozetle":
            m = u.get("maliyet_ozeti") or {}
            kir = m.get("asama_kirilimi") or {}
            yaz(f"▶ {FAZ_ETIKETLERI['maliyet_ozetle']}")
            yaz_alt(
                f"{m.get('toplam_llm_cagrisi', 0)} LLM çağrısı · {m.get('basarisiz_cagri', 0)} başarısız · "
                f"{m.get('toplam_sure_sn', 0)}s · ~${m.get('tahmini_usd', 0)}"
            )
            if kir:
                yaz_alt("aşama kırılımı: " + " · ".join(f"{k}={v}" for k, v in kir.items()))

    return isle


__all__ = ["FAZ_ETIKETLERI", "asama_ozeti", "model_rolleri_satiri", "ilerleme_takipcisi"]
