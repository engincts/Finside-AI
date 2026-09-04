import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple
from config import Config
from finside.models import BDRRiskAnalysisReport


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
        cls.save_final_report(session_dir, report, markdown_content)

    @classmethod
    def save_final_report(cls, session_dir: Path, report: BDRRiskAnalysisReport, markdown_content: str):
        """Uçtan uca üretilen TEK NİHAİ RAPOR dosyalarını (final_report.md & nihai_rapor.md) kaydeder."""
        (session_dir / "final_report.md").write_text(markdown_content, encoding="utf-8")
        (session_dir / "final_report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
        (session_dir / "nihai_rapor.md").write_text(markdown_content, encoding="utf-8")
        (session_dir / "nihai_rapor.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def save_json(cls, session_dir: Path, dosya_adi: str, veri: Any):
        """Pipeline ara çıktılarını (segments.json, triage_log.json) kaydeder."""
        (session_dir / dosya_adi).write_text(
            json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def save_portfolio_summary(cls, kok_dir: Path, satirlar: List[Dict[str, Any]]):
        """Batch çalıştırma sonunda tek portföy özeti (tüm BDR'ler)."""
        md_lines = [
            "# Finside AI — Pipeline Portföy Özeti",
            f"**Tarih/Saat:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
            f"**İşlenen BDR:** {len(satirlar)}",
            "",
            "| Dosya | Firma | Dönem | Karar Eğilimi | Risk | QA Bayrak | Süre (sn) | ~USD | Modeller |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        def _g(deger):
            return deger if deger is not None else "-"

        for s in satirlar:
            md_lines.append(
                f"| `{s.get('dosya', '-')}` | {s.get('firma') or '-'} | {s.get('donem') or '-'} "
                f"| `{s.get('karar') or '-'}` | {s.get('risk_sayisi', 0)} | {s.get('qa_bayrak', 0)} "
                f"| `{_g(s.get('sure_sn'))}` | `{_g(s.get('usd'))}` "
                f"| {', '.join(s.get('modeller', []))} |"
            )
        (kok_dir / "portfoy_ozeti.md").write_text("\n".join(md_lines), encoding="utf-8")
        (kok_dir / "portfoy_ozeti.json").write_text(
            json.dumps(satirlar, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def _clean_trace_item(cls, item: Any) -> Dict[str, Any]:
        if isinstance(item, dict):
            return item
        if hasattr(item, "model_dump"):
            return item.model_dump()
        if hasattr(item, "to_dict"):
            return item.to_dict()
        if hasattr(item, "__dict__"):
            return vars(item)
        return {"raw_trace": str(item)}

    @classmethod
    def append_trace(cls, session_dir: Path, kayitlar: List[Any]):
        """Pipeline LLM çağrı izlerini satır satır `trace.jsonl`'e ekler (append)."""
        if not kayitlar:
            return
        trace_path = session_dir / "trace.jsonl"
        with open(trace_path, "a", encoding="utf-8") as f:
            for kayit in kayitlar:
                f.write(json.dumps(cls._clean_trace_item(kayit), ensure_ascii=False) + "\n")

    @classmethod
    def save_trace(cls, session_dir: Path, kayitlar: List[Any]):
        """Birikmiş tüm trace kayıtlarını `trace.jsonl`'e yazar (üzerine, tekrarsız)."""
        trace_path = session_dir / "trace.jsonl"
        with open(trace_path, "w", encoding="utf-8") as f:
            for kayit in kayitlar:
                f.write(json.dumps(cls._clean_trace_item(kayit), ensure_ascii=False) + "\n")

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
