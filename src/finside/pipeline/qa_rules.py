"""Faz 8 — Kural tabanlı tutarlılık kontrolü (LLM'siz son "akıl sağlığı" adımı)."""

import re
from typing import List

from finside.models import BDRRiskAnalysisReport, DenetciGorusTuru, KomiteKararEgilimi, RiskDerecesi

_DOGRULANMAMIS_ESIGI = 0.30
_BOS_RISK_SEGMENT_ESIGI = 20
# "Dipnot 25 - ...", "NOT 36 -", "Not.14 " gibi başlık önekleri — buradaki numara
# bir tutar değil dipnot referansıdır, rakam-tutarsızlığı kontrolüne girmemeli.
_DIPNOT_ONEK_RE = re.compile(r"^\s*(?:dipnot|not|note|md)\s*\.?\s*\d+\s*[-–—:.)]*\s*", re.IGNORECASE)

# "4.58 Milyar", "225,1 Bin USD" gibi ölçek kelimeli tutarlar: buradaki "." ondalık
# ayıraçtır (binlik değil) — büyük tam sayılarla (ör. detaydaki "4.575.746.000")
# yuvarlama farkı içinde (±%2) karşılaştırmak için gerçek sayısal değere çevrilir.
_OLCEK_CARPAN = {"bin": 1_000, "milyon": 1_000_000, "mn": 1_000_000, "milyar": 1_000_000_000, "mr": 1_000_000_000}
_OLCEKLI_TUTAR_RE = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*(bin|milyon|mn\.?|milyar|mr\.?)\b", re.IGNORECASE)
_TUTAR_TOLERANSI = 0.02


def _olcekli_degerler(metin: str) -> set:
    degerler: set = set()
    for m in _OLCEKLI_TUTAR_RE.finditer(metin or ""):
        sayi = float(m.group(1).replace(",", "."))
        carpan = _OLCEK_CARPAN[m.group(2).lower().rstrip(".")]
        degerler.add(round(sayi * carpan))
    return degerler


def _buyuklukce_yakin(hedef: int, kaynak_tam_sayilar: set) -> bool:
    """`hedef` (ölçek kelimesinden hesaplanan gerçek değer), kaynaktaki tam sayılardan
    biriyle (veya onun 'bin TL' cinsinden 1000 katıyla) ~%2 toleransla örtüşüyor mu."""
    for k in kaynak_tam_sayilar:
        for aday in (k, k * 1000):
            if aday and abs(hedef - aday) / max(hedef, aday) <= _TUTAR_TOLERANSI:
                return True
    return False


def qa_bayraklari(report: BDRRiskAnalysisReport, segment_sayisi: int) -> List[str]:
    bayraklar: List[str] = []
    riskler = report.tespit_edilen_riskler

    if report.is_mock_fallback:
        bayraklar.append(
            "Sentez adımı API hatası/kota nedeniyle mock çıktıya düştü — genel özet, "
            f"karar eğilimi ve gerekçe güvenilir DEĞİL. ({report.fallback_reason})"
        )

    kritik_var = any(r.risk_derecesi == RiskDerecesi.KRITIK for r in riskler)
    if kritik_var and report.karar_egilimi == KomiteKararEgilimi.OLUMLU:
        bayraklar.append("KRİTİK dereceli risk varken karar eğilimi 'Olumlu' — gözden geçirilmeli.")

    olumsuz_gorusler = {DenetciGorusTuru.OLUMSUZ, DenetciGorusTuru.GORUS_BILDIRMEKTEN_KACINMA}
    if report.denetci_gorusu in olumsuz_gorusler and report.karar_egilimi == KomiteKararEgilimi.OLUMLU:
        bayraklar.append(
            f"Denetçi görüşü '{report.denetci_gorusu.value}' iken karar eğilimi 'Olumlu' — çelişkili."
        )

    if riskler:
        dogrulanmamis = sum(1 for r in riskler if r.dogrulanmadi)
        if dogrulanmamis / len(riskler) > _DOGRULANMAMIS_ESIGI:
            bayraklar.append(
                f"Risklerin %{round(100 * dogrulanmamis / len(riskler))}'i kaynak metinde doğrulanamadı."
            )

    if not riskler and segment_sayisi > _BOS_RISK_SEGMENT_ESIGI:
        bayraklar.append(
            f"{segment_sayisi} segment işlendi ama hiç risk bulunamadı — olası pipeline hatası."
        )

    # Jenerik Şablon Etki Cümlesi Tekrarı Kontrolü (Regex + Somutluk Süzgeci + Dinamik Yapısal N-Gram)
    from finside.dedupe import _is_jenerik_etki, _onemli_sayilar
    if riskler:
        jenerik_etki_sayisi = sum(
            1 for r in riskler
            if _is_jenerik_etki(r.etki_degerlendirmesi or "")
        )
        if jenerik_etki_sayisi >= 3:
            bayraklar.append(
                f"Tespit edilen risklerin {jenerik_etki_sayisi} tanesinde jenerik/şablon etki cümlesi "
                "(somut gerekçesi olmayan 'Borç ödeme kapasitesi' / 'nakit akışı, ödeme dengesi' vb.) tespit edildi."
            )

        # Dinamik Yapısal Şablon Cümle Tekrarı Kontrolü (Suffix / N-gram Tekrarı)
        etki_sonlari = [
            (r.etki_degerlendirmesi or "").strip().lower()[-60:]
            for r in riskler
            if len((r.etki_degerlendirmesi or "").strip()) >= 30
        ]
        if etki_sonlari:
            from collections import Counter
            son_sayac = Counter(etki_sonlari)
            tekrarlayan_sonlar = [son for son, cnt in son_sayac.items() if cnt >= 3]
            if tekrarlayan_sonlar:
                toplam_tekrarlayan = sum(son_sayac[s] for s in tekrarlayan_sonlar)
                bayraklar.append(
                    f"Tespit edilen risklerin {toplam_tekrarlayan} tanesinde birebir aynı bitiş kalıbına sahip "
                    "yapısal şablon etki cümlesi bulundu. ('... " + tekrarlayan_sonlar[0][-35:] + "')"
                )

        # İç Rakam Tutarsızlığı Kontrolü (Başlık Tutarı vs Detay Tutarı)
        def _tum_sayilar(m: str) -> set:
            from finside.dedupe import _SAYI_RE, _YIL_ARALIGI
            bul: set = set()
            for e in _SAYI_RE.findall(m or ""):
                r = e.replace(".", "").replace(",", "")
                if len(r) >= 3 and int(r) not in _YIL_ARALIGI:
                    bul.add(r)
            return bul

        def _yaklasik_var(hedef: str, kaynak: set) -> bool:
            # "33.34 Milyar" (başlıkta yuvarlanmış → "3334") ile "33.341.512" (detayda
            # tam → "33341512") aynı büyüklüktür: biri diğerinin ilk hanelerinden oluşuyorsa eşleşmiş say.
            return any(s == hedef or s.startswith(hedef) or hedef.startswith(s) for s in kaynak)

        for r in riskler:
            baslik_temiz = _DIPNOT_ONEK_RE.sub("", r.baslik or "")
            baslik_sayilar = _tum_sayilar(baslik_temiz)
            if baslik_sayilar:
                detay_sayilar = _tum_sayilar(f"{r.detay or ''} {r.tutar_bilgisi or ''}")
                eslesmeyen = {b for b in baslik_sayilar if not _yaklasik_var(b, detay_sayilar)}
                if eslesmeyen:
                    olcekli = _olcekli_degerler(baslik_temiz)
                    detay_tam = {int(s) for s in detay_sayilar}
                    eslesmeyen = {
                        b for b in eslesmeyen
                        if not any(_buyuklukce_yakin(o, detay_tam) for o in olcekli)
                    }
                if detay_sayilar and eslesmeyen == baslik_sayilar:
                    bayraklar.append(
                        f"RAKAM-TUTARSIZLIĞI: '{r.baslik[:45]}' kaleminde başlıkta geçen sayı ({', '.join(sorted(baslik_sayilar))}) "
                        f"detay metninde ({', '.join(sorted(detay_sayilar))}) doğrulanamadı veya çelişiyor."
                    )

    return bayraklar
