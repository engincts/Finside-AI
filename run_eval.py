"""Finside AI — Eval CLI.

Örnekler:
  python run_eval.py --klasor outputs/2026-09-08/09-13-49 --config pipeline-v1
  python run_eval.py --rapor outputs/.../final_report.json --bdr data/bdr_samples/x.txt --config gemini-tek
  python run_eval.py --klasor outputs/... --config pipeline-v1 --hakem gemini-3.6-flash,gpt-4o
  python run_eval.py --karsilastir eval/pipeline-v1 eval/gemini-tek
"""

import argparse
import json
import os
import sys
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from finside.eval.runner import EvalSonucu, degerlendir, degerlendir_klasor  # noqa: E402


def _yaz(satir: str) -> None:
    print(satir, flush=True)


def _karsilastir(klasorler: list[str]) -> None:
    from dataclasses import fields

    from finside.eval.karsilastir import ozet_tablo

    gecerli = {f.name for f in fields(EvalSonucu)}
    sonuclar = []
    for klasor in klasorler:
        for dosya in sorted(Path(klasor).glob("*.json")):
            veri = json.loads(dosya.read_text(encoding="utf-8"))
            sonuclar.append(EvalSonucu(**{k: v for k, v in veri.items() if k in gecerli}))
    print(ozet_tablo(sonuclar))


def main() -> None:
    parser = argparse.ArgumentParser(description="Finside AI — Eval CLI")
    parser.add_argument("--klasor", type=str, help="outputs/ altında rapor klasörü (rglob final_report.json)")
    parser.add_argument("--rapor", type=str, help="Tek final_report.json / nihai_rapor.json yolu")
    parser.add_argument("--bdr", type=str, help="--rapor ile: kaynak BDR .txt yolu")
    parser.add_argument("--config", type=str, default="varsayilan", help="Bu koşumun etiketi (eval/<config>/ altına yazılır)")
    parser.add_argument("--hakem", type=str, default=None, help="Katman 2 hakem model id'leri (virgülle). Verilmezse atlanır.")
    parser.add_argument("--gold-yok", action="store_true", help="Katman 3 gold skorlamasını atla")
    parser.add_argument("--karsilastir", nargs="+", metavar="EVAL_KLASORU", help="Verilen eval/<config> klasörlerini tek tabloda kıyasla")
    args = parser.parse_args()

    if args.karsilastir:
        _karsilastir(args.karsilastir)
        return

    hakemler = [m.strip() for m in args.hakem.split(",")] if args.hakem else None
    gold_kullan = not args.gold_yok

    if args.klasor:
        sonuclar = degerlendir_klasor(
            Path(args.klasor), config_adi=args.config,
            hakem_modelleri=hakemler, gold_kullan=gold_kullan, yaz=_yaz,
        )
        print(f"\n{len(sonuclar)} rapor değerlendirildi → eval/{args.config}/ozet.md")
        return

    if args.rapor and args.bdr:
        degerlendir(
            Path(args.rapor), Path(args.bdr), config_adi=args.config,
            hakem_modelleri=hakemler, gold_kullan=gold_kullan, yaz=_yaz,
        )
        print(f"\n→ eval/{args.config}/")
        return

    parser.error("--klasor VEYA (--rapor + --bdr) VEYA --karsilastir gerekli")


if __name__ == "__main__":
    main()
