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
from finside.loaders import BDRLoader, PromptLoader
from finside.writers import ReportWriter
from finside.analyzer import BDRAnalyzer
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
        ozet = calistir_batch(args.batch, secili_modeller=modeller)
        print("=" * 80)
        print(f"📦 Pipeline Batch Tamamlandı — {len(ozet)} BDR")
        for s in ozet:
            print(f"  {s['dosya']:<40} | {s['karar'] or '-':<45} | {s['risk_sayisi']} risk | {s['qa_bayrak']} QA")
        print(f"📁 Portföy özeti: {Config.OUTPUT_DIR}/.../portfoy_ozeti.md")
        print("=" * 80)
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

    print("=" * 80)
    print("🚀 Finside AI — BDR Risk Analizi & Model Performans Motoru")
    print(f"📄 Dosya: {input_path.name} ({bdr_info['character_count']} karakter, {bdr_info['word_count']} kelime)")
    print(f"📂 Klasör: {relative_session_path}/")
    print("=" * 80)

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
    print("\n" + "=" * 80)
    print("📊 MODEL KARŞILAŞTIRMA & PERFORMANS METRİKLERİ ÖZETİ")
    print("=" * 80)
    print(f"{'Model ID':<20} | {'Süre':<8} | {'Durum':<18} | {'Risk Sayısı':<12} | {'Karar Eğilimi'}")
    print("-" * 80)
    for r in summary_results:
        st = "⚠️ Fallback (Mock)" if r['is_mock_fallback'] else "✅ Gerçek API"
        print(f"{r['model_id']:<20} | {r['duration_sec']:.2f}s   | {st:<18} | {r['risk_count']} Kalem    | {r['karar_egilimi']}")
    print("=" * 80)
    print(f"📁 Genel Performans Raporu: {relative_session_path}/summary_metrics.md")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
