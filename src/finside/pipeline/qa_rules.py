"""Faz 8 — Kural tabanlı tutarlılık kontrolü (LLM'siz son "akıl sağlığı" adımı)."""

from typing import List

from finside.models import BDRRiskAnalysisReport, DenetciGorusTuru, KomiteKararEgilimi, RiskDerecesi

_DOGRULANMAMIS_ESIGI = 0.30
_BOS_RISK_SEGMENT_ESIGI = 20


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
                if len(r) >= 2 and int(r) not in _YIL_ARALIGI:
                    bul.add(r)
            return bul

        for r in riskler:
            baslik_sayilar = _tum_sayilar(r.baslik or "")
            if baslik_sayilar:
                detay_sayilar = _tum_sayilar(f"{r.detay or ''} {r.tutar_bilgisi or ''}")
                if detay_sayilar and not baslik_sayilar.intersection(detay_sayilar):
                    # Başlıkta sayı var ama detayda/tutar_bilgisi'nde bu sayı HİÇ geçmiyor ve başka sayılar var
                    bayraklar.append(
                        f"RAKAM-TUTARSIZLIĞI: '{r.baslik[:45]}' kaleminde başlıkta geçen sayı ({', '.join(sorted(baslik_sayilar))}) "
                        f"detay metninde ({', '.join(sorted(detay_sayilar))}) doğrulanamadı veya çelişiyor."
                    )

    return bayraklar
