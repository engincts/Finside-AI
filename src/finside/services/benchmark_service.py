import time
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path

from config import Config
from finside.analyzer import BDRAnalyzer
from finside.writers import ReportWriter
from finside.models import BenchmarkRequest


class BenchmarkService:
    """SOLID Single Responsibility & Facade: Model karşılaştırma ve benchmark servisi."""

    @classmethod
    def run_single_model_analysis(
        cls,
        model_id: str,
        request: BenchmarkRequest,
        session_dir: Path,
    ) -> Dict[str, Any]:
        """Tek bir modeli yapılandırarak BDR metnini analiz eder ve metrikleri paketler."""
        model_cfg = Config.get_model_config_by_id(model_id) or {"id": model_id, "name": model_id, "provider": "mock"}

        if request.is_mock_mode:
            model_cfg["provider"] = "mock"

        if request.hyperparams:
            model_cfg.update(request.hyperparams)

        try:
            analyzer = BDRAnalyzer(
                model_config=model_cfg,
                custom_system_prompt=request.system_prompt,
                custom_user_template=request.user_template,
            )
            report = analyzer.analyze(request.bdr_content)
            md_content = analyzer.format_report_as_markdown(report)
            ReportWriter.save_model_report(session_dir, model_id, report, md_content)

            result = {
                "model_id": model_id,
                "model_name": model_cfg.get("name", model_id),
                "report": report,
                "md_content": md_content,
                "config": model_cfg,
            }
            metrics = {
                "model_id": model_id,
                "model_name": model_cfg.get("name", model_id),
                "provider": model_cfg.get("provider"),
                "duration_sec": report.analiz_suresi_saniye,
                "is_mock_fallback": False,
                "fallback_reason": None,
                "risk_count": len(report.tespit_edilen_riskler),
                "karar_egilimi": report.karar_egilimi.value,
                "denetci_gorusu": report.denetci_gorusu.value if report.denetci_gorusu else None,
            }
            return {"result": result, "metrics": metrics}
        except Exception as err:
            err_msg = str(err)
            metrics = {
                "model_id": model_id,
                "model_name": model_cfg.get("name", model_id),
                "provider": model_cfg.get("provider"),
                "duration_sec": 0.0,
                "is_mock_fallback": True,
                "fallback_reason": err_msg,
                "risk_count": 0,
                "karar_egilimi": f"❌ HATA: {err_msg}",
                "denetci_gorusu": "Hata Alındı",
            }
            return {"result": None, "metrics": metrics}

    @classmethod
    def run_benchmark_suite(
        cls,
        request: BenchmarkRequest,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str], Path]:
        """Seçilen tüm modelleri paralel havuzda çalıştırarak benchmark tamamlar ve metrikleri kaydeder."""
        session_dir, input_stem = ReportWriter.create_session_directory(request.bdr_name)

        outputs = {}
        max_workers = min(len(request.selected_model_ids), Config.MAX_PARALLEL_MODELS)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    cls.run_single_model_analysis,
                    m_id,
                    request,
                    session_dir,
                ): m_id
                for m_id in request.selected_model_ids
            }
            done, not_done = futures_wait(futures, timeout=Config.BENCHMARK_MAX_WAIT_SEC)

            for future in done:
                outputs[futures[future]] = future.result()

            timeouts = [futures[f] for f in not_done]
            for future in not_done:
                future.cancel()

        tamamlanan = [m_id for m_id in request.selected_model_ids if m_id in outputs]
        results_list = [outputs[m_id]["result"] for m_id in tamamlanan if outputs[m_id].get("result") is not None]
        metrics_summary_list = [outputs[m_id]["metrics"] for m_id in tamamlanan]

        if metrics_summary_list:
            ReportWriter.save_summary_metrics(session_dir, input_stem, metrics_summary_list)

        return results_list, metrics_summary_list, timeouts, session_dir
