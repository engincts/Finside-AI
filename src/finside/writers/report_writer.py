import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple
from config import Config
from prompts.schemas import BDRRiskAnalysisReport


class ReportWriter:
    """SOLID Single Responsibility: Rapor dosyalarını ve özet metrikleri hiyerarşik dizinlere yazma sınıfı."""

    @classmethod
    def create_session_directory(cls, input_file_path: str) -> Tuple[Path, str]:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H-%M-%S")
        input_stem = Path(input_file_path).stem

        session_dir = Config.OUTPUT_DIR / date_str / time_str / input_stem
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir, input_stem

    @classmethod
    def save_model_report(cls, session_dir: Path, model_id: str, report: BDRRiskAnalysisReport, markdown_content: str):
        md_file = session_dir / f"{model_id}_report.md"
        json_file = session_dir / f"{model_id}_report.json"

        md_file.write_text(markdown_content, encoding="utf-8")
        json_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def save_summary_metrics(cls, session_dir: Path, bdr_name: str, metrics_list: List[Dict[str, Any]]):
        summary_json_path = session_dir / "summary_metrics.json"
        summary_md_path = session_dir / "summary_metrics.md"

        with open(summary_json_path, "w", encoding="utf-8") as f:
            json.dump(metrics_list, f, ensure_ascii=False, indent=2)

        md_lines = [
            f"# 📊 Finside AI — Model Performans & Karşılaştırma Özeti",
            f"**İşlenen Dosya:** `{bdr_name}`",
            f"**Tarih/Saat:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
            "",
            "| Model ID | Model Adı | Sağlayıcı | Süre (sn) | Fallback Durumu | Risk Adedi | Denetçi Görüşü | Karar Eğilimi |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ]

        for m in metrics_list:
            model_id = m.get("model_id", "N/A")
            model_name = m.get("model_name", "N/A")
            provider = m.get("provider", "N/A")
            duration = f"{m.get('duration_sec', 0.0):.2f}s"
            is_fallback = m.get("is_mock_fallback", False)
            fallback_status = "⚠️ Fallback (Mock)" if is_fallback else "✅ Gerçek API"
            risk_count = f"{m.get('risk_count', 0)} Kalem"
            opinion = m.get("denetci_gorusu", "N/A")
            decision = m.get("karar_egilimi", "N/A")

            md_lines.append(
                f"| `{model_id}` | {model_name} | `{provider}` | `{duration}` | `{fallback_status}` | {risk_count} | `{opinion}` | `{decision}` |"
            )

        md_lines.extend([
            "",
            "---",
            "### 📌 Notlar & Şeffaflık Beyanı",
            "- **Gerçek API**: Model doğrudan bulut veya HuggingFace Inference API üzerinden çalıştırılmıştır.",
            "- **Fallback (Mock)**: API anahtarı yokluğu, kota aşımı (429) veya 404/Inference hatası nedeniyle otomatik simülasyona düşmüştür.",
            "- Her modelin detaylı Markdown ve JSON raporları bu klasör içerisindedir."
        ])

        summary_md_path.write_text("\n".join(md_lines), encoding="utf-8")
