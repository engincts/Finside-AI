"""Faz 9.5 — Few-shot örnek bankası (fine-tuning yerine ucuz stil/format tutarlılığı).

`prompts/few_shot_examples/<kategori>/<ornek>.json` dosyalarından, risk listesindeki
baskın kategorilere göre 1-2 örnek seçip sentez promptuna eklenecek metin bloğu üretir.
Embedding kullanmaz; kategori eşleşmesi yeterli. Banka boşsa `''` döner.
"""

import json
from pathlib import Path
from typing import List

from config import Config
from prompts.schemas import RiskKategorisi

ORNEK_KOKU = Config.BASE_DIR / "prompts" / "few_shot_examples"
MAKS_ORNEK = 2


def _kategori_coz(deger) -> RiskKategorisi | None:
    return next((k for k in RiskKategorisi if k.value == deger or k.name == deger), None)


def _ornek_dosyalari(kategori: RiskKategorisi) -> List[Path]:
    dizin = ORNEK_KOKU / kategori.name.lower()
    if not dizin.is_dir():
        return []
    return sorted(p for p in dizin.glob("*.json") if not p.name.startswith("_"))


def ilgili_ornekler(riskler: List[dict], maks: int = MAKS_ORNEK) -> str:
    kategoriler: List[RiskKategorisi] = []
    for risk in riskler:
        kategori = _kategori_coz(risk.get("risk_kategorisi"))
        if kategori and kategori not in kategoriler:
            kategoriler.append(kategori)

    secilenler: List[dict] = []
    for kategori in kategoriler:
        for dosya in _ornek_dosyalari(kategori):
            try:
                secilenler.append(json.loads(dosya.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                continue
            if len(secilenler) >= maks:
                break
        if len(secilenler) >= maks:
            break

    if not secilenler:
        return ""

    bloklar = ["## ÖRNEK ANALİZLER (yalnızca üslup/format referansı)"]
    for i, ornek in enumerate(secilenler, 1):
        bloklar.append(
            f"### Örnek {i}\n"
            f"Girdi:\n{ornek.get('bdr_parcasi', '')}\n\n"
            f"Beklenen çıktı:\n"
            f"{json.dumps(ornek.get('beklenen_cikti', {}), ensure_ascii=False, indent=2)}"
        )
    return "\n\n".join(bloklar) + "\n\n---\n\n"
