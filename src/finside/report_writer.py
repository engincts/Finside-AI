import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

from config import Config
from prompts.schemas import BDRRiskAnalysisReport


class ReportWriter:
    """SOLID Single Responsibility: Dosya yazma, klasör yapılandırması ve metrik raporlama sorumlusu."""

    @staticmethod
    def create_session_directory(input_path: Path) -> Tuple[Path, str, str]:
        """
        outputs/{YYYY-MM-DD}/{HH-MM-SS}/{bdr_adi}/ formatında klasör hiyerarşisi oluşturur.
        :return: (session_dir_path, date_str, time_str)
        """
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H-%M-%S")
        input_stem = input_path.stem

        session_dir = Config.OUTPUT_DIR / date_str / time_str / input_stem
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir, date_str, time_str

    @staticmethod
    def save_model_report(
        session_dir: Path,
        model_id: str,
        report: BDRRiskAnalysisReport,
        md_content: str
    ) -> Tuple[Path, Path]:
        """Model analiz raporlarını (JSON ve MD) kaydeder."""
        json_path = session_dir / f"{model_id}_report.json"
        md_path = session_dir / f"{model_id}_report.md"

        with open(json_path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return json_path, md_path

    @staticmethod
    def save_summary_metrics(
        session_dir: Path,
        input_path: Path,
        bdr_info: Dict[str, Any],
        summary_results: List[Dict[str, Any]],
        date_str: str,
        time_str: str
    ) -> Tuple[Path, Path]:
        """Tüm modellerin birleşik metrik özet dosyalarını (JSON ve MD) kaydeder."""
        metrics_data = {
            "tarih": date_str,
            "saat": time_str,
            "bdr_dosyasi": input_path.name,
            "karakter_sayisi": bdr_info["character_count"],
            "kelime_sayisi": bdr_info["word_count"],
            "calistirilan_model_sayisi": len(summary_results),
            "modeller": summary_results
        }

        metrics_json_path = session_dir / "summary_metrics.json"
        with open(metrics_json_path, "w", encoding="utf-8") as f:
            json.dump(metrics_data, f, ensure_ascii=False, indent=2)

        metrics_md_lines = [
            f"# 📊 Finside AI — BDR Analiz & Performans Özet Raporu",
            f"**Tarih:** `{date_str}` | **Saat:** `{time_str}`",
            f"**BDR Dosyası:** `{input_path.name}` ({bdr_info['character_count']} karakter, {bdr_info['word_count']} kelime)",
            f"**Çalıştırılan Model Sayısı:** `{len(summary_results)}`",
            "",
            "---",
            "## 📈 Modeller Arası Karşılaştırma & Süre Metrikleri",
            "",
            "| Model ID | Sağlayıcı | Reasoning Effort | Analiz Süresi | Risk Sayısı | Karar Eğilimi |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ]

        for r in summary_results:
            metrics_md_lines.append(
                f"| `{r['model_id']}` | `{r['provider']}` | `{r['reasoning_effort']}` | `{r['analiz_suresi_saniye']:.2f}s` | `{r['risk_sayisi']} Kalem` | `{r['karar_egilimi']}` |"
            )

        metrics_md_lines.extend([
            "",
            "---",
            "## 📂 Oluşturulan Model Raporları",
        ])
        for r in summary_results:
            metrics_md_lines.append(f"- 📄 **{r['name']}**: [{r['report_md']}](./{r['report_md']}) | [{r['report_json']}](./{r['report_json']})")

        metrics_md_path = session_dir / "summary_metrics.md"
        with open(metrics_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(metrics_md_lines))

        return metrics_json_path, metrics_md_path
