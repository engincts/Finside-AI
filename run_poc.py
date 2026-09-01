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
from finside.analyzer import BDRAnalyzer


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
        target = Config.get_model_by_id(args.model_id)
        if not target:
            print(f"❌ Model ID bulunamadı: {args.model_id}")
            sys.exit(1)
        models_to_run = [target]
    else:
        models_to_run = Config.get_enabled_models()
        if not models_to_run:
            print("⚠️ 'enabled: true' model bulunamadı, Mock mod çalıştırılıyor...")
            models_to_run = [{"id": "mock", "name": "Mock Test Modeli", "provider": "mock", "model_name": "mock-v1"}]

    summary_results = []

    # 4. Modelleri Çalıştır (BDRAnalyzer) & Raporları Kaydet (writers.ReportWriter)
    for model_cfg in models_to_run:
        model_id = model_cfg.get("id")
        model_name = model_cfg.get("name")
        print(f"\n🔄 Model Çalıştırılıyor: [{model_id}] {model_name}...")

        if args.mock:
            model_cfg["provider"] = "mock"

        analyzer = BDRAnalyzer(model_config=model_cfg)
        report = analyzer.analyze(bdr_info["content"])
        md_content = analyzer.format_report_as_markdown(report)

        ReportWriter.save_model_report(session_dir, model_id, report, md_content)

        summary_results.append({
            "model_id": model_id,
            "model_name": model_name,
            "provider": model_cfg.get("provider"),
            "duration_sec": report.analiz_suresi_saniye,
            "is_mock_fallback": report.is_mock_fallback,
            "fallback_reason": report.fallback_reason,
            "risk_count": len(report.tespit_edilen_riskler),
            "karar_egilimi": report.karar_egilimi.value,
            "denetci_gorusu": report.denetci_gorusu.value if report.denetci_gorusu else None
        })

        status_str = "⚠️ Fallback (Mock)" if report.is_mock_fallback else "✅ Gerçek API"
        print(f"  {status_str} — Rapor Oluşturuldu: {relative_session_path}/{model_id}_report.md (Süre: {report.analiz_suresi_saniye:.2f}s)")

    # 5. Özet Performans Metriklerini Kaydet (writers.ReportWriter)
    ReportWriter.save_summary_metrics(session_dir, input_stem, summary_results)

    # 6. Terminal Özet Görünümü
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
