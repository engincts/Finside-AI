import os
import sys
import argparse
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from config import Config
from finside.loaders import BDRLoader
from finside.writers import ReportWriter
from finside.services.benchmark_service import BenchmarkService


def main():
    default_txt_files = list(Config.DATA_DIR.glob("*.txt"))
    default_input = str(default_txt_files[0]) if default_txt_files else str(Config.DATA_DIR / "sample_bdr.txt")

    parser = argparse.ArgumentParser(description="Finside AI — BDR Analiz & Model Performans Motoru")
    parser.add_argument("--input", "-i", type=str, default=default_input)
    parser.add_argument("--model_id", "-m", type=str, default=None)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--batch", type=str, default=None,
                        help="Klasördeki tüm .txt BDR'leri multi-agent pipeline ile işle")
    parser.add_argument("--map-models", type=str, default=None,
                        help="Pipeline ensemble modelleri (virgülle): a,b,c")
    args = parser.parse_args()

    if args.batch:
        from finside.pipeline.batch import calistir_batch

        modeller = [m.strip() for m in args.map_models.split(",")] if args.map_models else None
        ozet = calistir_batch(
            args.batch,
            secili_modeller=modeller,
            yaz=lambda satir: print(satir, flush=True),
        )
        print(f"\nPipeline batch tamamlandı — {len(ozet)} BDR")
        for s in ozet:
            print(f"  {s['dosya']:<40} {s['karar'] or '-':<45} {s['risk_sayisi']} risk · {s['qa_bayrak']} QA")
        print(f"Portföy özeti: {Config.OUTPUT_DIR}/.../portfoy_ozeti.md")
        return

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Dosya bulunamadı: {input_path}")
        sys.exit(1)

    # 1. BDR Metnini Yükle (loaders.BDRLoader)
    loader = BDRLoader(input_path)
    bdr_info = loader.get_processed_bdr()

    # 2. Oturum Klasörü Oluştur (writers.ReportWriter) -> outputs/YYYY-MM-DD/HH-MM-SS/{input_name}/
    session_dir, input_stem = ReportWriter.create_session_directory(input_path)

    relative_session_path = session_dir.relative_to(Config.BASE_DIR)

    print(f"Finside AI — {input_path.name} ({bdr_info['character_count']} karakter) → {relative_session_path}/")

    # 3. Model Listesini Belirle
    if args.model_id:
        selected_model_ids = [args.model_id]
    else:
        enabled_models = Config.get_enabled_models()
        if enabled_models:
            selected_model_ids = [m["id"] for m in enabled_models]
        else:
            print("⚠️ 'enabled: true' model bulunamadı, Mock mod çalıştırılıyor...")
            selected_model_ids = ["mock"]

    from finside.models import BenchmarkRequest

    req = BenchmarkRequest(
        selected_model_ids=selected_model_ids,
        bdr_content=bdr_info["content"],
        bdr_name=input_path.name,
        is_mock_mode=args.mock,
    )

    # 4. Modelleri BenchmarkService İle Çalıştır
    results_list, summary_results, timeouts, session_dir = BenchmarkService.run_benchmark_suite(req)

    relative_session_path = session_dir.relative_to(Config.BASE_DIR)

    # 5. Terminal Özet Görünümü
    print(f"\n{'Model':<20} {'Süre':<9} {'Durum':<10} {'Risk':<7} Karar")
    for r in summary_results:
        st = "fallback" if r['is_mock_fallback'] else "api"
        print(f"{r['model_id']:<20} {r['duration_sec']:.2f}s{'':<3} {st:<10} {r['risk_count']:<7} {r['karar_egilimi']}")
    print(f"Rapor: {relative_session_path}/summary_metrics.md\n")


if __name__ == "__main__":
    main()
