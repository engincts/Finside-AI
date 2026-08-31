import argparse
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from config import Config
from finside.bdr_loader import BDRLoader
from finside.analyzer import BDRAnalyzer
from finside.report_writer import ReportWriter


def main():
    parser = argparse.ArgumentParser(description="Finside AI — BDR Analiz & Model Performans Motoru")
    parser.add_argument("--input", "-i", type=str, default=str(Config.DATA_DIR / "0f7bfcfebe7f422aa56aba17a28c610c.txt"))
    parser.add_argument("--model_id", "-m", type=str, default=None)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Dosya bulunamadı: {input_path}")
        sys.exit(1)

    # 1. BDR Metnini Yükle (BDRLoader)
    loader = BDRLoader(input_path)
    bdr_info = loader.get_processed_bdr()

    # 2. Oturum Klasörü Oluştur (ReportWriter) -> outputs/YYYY-MM-DD/HH-MM-SS/{input_name}/
    session_dir, date_str, time_str = ReportWriter.create_session_directory(input_path)

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

    # 4. Modelleri Çalıştır (BDRAnalyzer) & Raporları Kaydet (ReportWriter)
    for model_cfg in models_to_run:
        model_id = model_cfg.get("id")
        model_name = model_cfg.get("name")
        print(f"\n🔄 Model Çalıştırılıyor: [{model_id}] {model_name}...")

        if args.mock:
            model_cfg["provider"] = "mock"

        analyzer = BDRAnalyzer(model_config=model_cfg)
        report = analyzer.analyze(bdr_info["content"])
        md_content = analyzer.format_report_as_markdown(report)

        json_path, md_path = ReportWriter.save_model_report(session_dir, model_id, report, md_content)

        summary_results.append({
            "model_id": model_id,
            "name": model_name,
            "provider": model_cfg.get("provider"),
            "reasoning_effort": analyzer.reasoning_effort,
            "analiz_suresi_saniye": report.analiz_suresi_saniye,
            "risk_sayisi": len(report.tespit_edilen_riskler),
            "karar_egilimi": report.karar_egilimi.value,
            "denetci_gorusu": report.denetci_gorusu.value if report.denetci_gorusu else None,
            "report_md": md_path.name,
            "report_json": json_path.name
        })

        print(f"  ✅ Rapor Oluşturuldu: {relative_session_path}/{md_path.name} (Süre: {report.analiz_suresi_saniye:.2f}s)")

    # 5. Özet Performans Metriklerini Kaydet (ReportWriter)
    _, metrics_md_path = ReportWriter.save_summary_metrics(
        session_dir, input_path, bdr_info, summary_results, date_str, time_str
    )

    # 6. Terminal Özet Görünümü
    print("\n" + "=" * 80)
    print("📊 MODEL KARŞILAŞTIRMA & PERFORMANS METRİKLERİ ÖZETİ")
    print("=" * 80)
    print(f"{'Model ID':<20} | {'Süre':<8} | {'Risk Sayısı':<12} | {'Karar Eğilimi'}")
    print("-" * 80)
    for r in summary_results:
        print(f"{r['model_id']:<20} | {r['analiz_suresi_saniye']:.2f}s   | {r['risk_sayisi']} Kalem    | {r['karar_egilimi']}")
    print("=" * 80)
    print(f"📁 Genel Performans Raporu: {relative_session_path}/{metrics_md_path.name}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
