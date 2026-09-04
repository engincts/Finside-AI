import os
import sys
import json
import time
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import Config
from finside.loaders import BDRLoader
from finside.pipeline.graph import build_graph
from langgraph.checkpoint.memory import MemorySaver


def run_single_pipeline(run_idx: int, bdr_path: Path, output_base: Path):
    print(f"\n========================================================")
    print(f"[RUN #{run_idx}] PIPELINE KOSUMU BASLADI")
    print(f"========================================================")
    start_t = time.time()
    
    run_dir = output_base / f"run_{run_idx}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    loader = BDRLoader(bdr_path)
    bdr_info = loader.get_processed_bdr()
    
    initial_state = {
        "bdr_id": bdr_path.stem,
        "bdr_adi": bdr_info["file_name"],
        "ham_metin": bdr_info["content"],
        "session_dir": str(run_dir),
        "secili_map_modelleri": Config.get_pipeline_config()["map_models"],
    }

    graph = build_graph(checkpointer=MemorySaver())
    final_state = graph.invoke(initial_state, config={"configurable": {"thread_id": f"consistency_run_{run_idx}"}})
    
    duration = time.time() - start_t
    print(f"[OK] Kosum #{run_idx} tamamlandi ({duration:.2f}s). Dizin: {run_dir}")
    
    nihai = final_state.get("nihai_rapor", {})
    riskler = nihai.get("tespit_edilen_riskler", []) if isinstance(nihai, dict) else []
    print(f"   [SUMMARY] Tespit edilen nihai risk sayisi: {len(riskler)}")
    
    # Save raw final state for deep inspection
    with open(run_dir / "full_state.json", "w", encoding="utf-8") as f:
        serializable_state = {
            "triaj_kararlari": final_state.get("triaj_kararlari", []),
            "analiz_edilecek_sira_nolari": final_state.get("analiz_edilecek_sira_nolari", []),
            "map_ciktilari": final_state.get("map_ciktilari", []),
            "uzlastirilmis_riskler": final_state.get("uzlastirilmis_riskler", []),
            "nihai_rapor": nihai,
            "qa_bayraklari": final_state.get("qa_bayraklari", []),
        }
        json.dump(serializable_state, f, ensure_ascii=False, indent=2)

    return {
        "run_idx": run_idx,
        "duration": duration,
        "dir": run_dir,
        "state": final_state,
        "nihai_riskler": riskler
    }


def analyze_runs_diff(results):
    print("\n========================================================")
    print("RUN-TO-RUN DIFF VE TUTARSIZLIK ANALIZI")
    print("========================================================")
    
    all_runs_risks = []
    for r in results:
        idx = r["run_idx"]
        risks = r["nihai_riskler"]
        all_runs_risks.append((idx, risks))
    
    unique_items = []
    
    for idx, risks in all_runs_risks:
        for r in risks:
            title = r.get("baslik", "")
            detail = r.get("detay", "")
            amount = r.get("tutar_bilgisi", "")
            category = r.get("risk_kategorisi", "")
            
            found = False
            for u in unique_items:
                u_title = u["canonical_title"]
                if (title.lower() in u_title.lower() or u_title.lower() in title.lower() or
                    (amount and amount != "Belirtilmemiş" and amount in u["amounts"])):
                    u["runs"][idx] = {
                        "baslik": title,
                        "detay": detail[:100] + "...",
                        "kategori": category,
                        "tutar": amount
                    }
                    if amount:
                        u["amounts"].add(amount)
                    found = True
                    break
            
            if not found:
                item_entry = {
                    "canonical_title": title,
                    "kategori": category,
                    "amounts": {amount} if amount else set(),
                    "runs": {
                        idx: {
                            "baslik": title,
                            "detay": detail[:100] + "...",
                            "kategori": category,
                            "tutar": amount
                        }
                    }
                }
                unique_items.append(item_entry)

    print(f"\nToplam {len(results)} kosumda toplam {len(unique_items)} benzersiz risk kalemi kumelendi.\n")
    
    header = f"| No | Canonical Risk Konusu | Katilim Orani | " + " | ".join([f"Kosum {r['run_idx']}" for r in results]) + " |"
    sep = "|---|" + "---|"*len(results) + "---|"
    print(header)
    print(sep)
    
    diff_report_lines = [
        "# Pipeline Run-to-Run Tutarsizlik ve Varyasyon Raporu",
        "",
        f"**Test Edilen BDR:** `data/bdr_samples/0f7bfcfebe7f422aa56aba17a28c610c.txt`",
        f"**Kosum Sayisi:** {len(results)}",
        "",
        "## 📌 Risk Karsilastirma Matrisi (Diff Tablosu)",
        "",
        header,
        sep
    ]

    for i, item in enumerate(unique_items, 1):
        present_count = len(item["runs"])
        katilim_ratio = f"{present_count}/{len(results)}"
        row_cells = []
        for r in results:
            idx = r["run_idx"]
            if idx in item["runs"]:
                row_cells.append(f"VAR ({item['runs'][idx]['kategori'][:15]})")
            else:
                row_cells.append("YOK")
        
        row_str = f"| {i} | {item['canonical_title'][:45]} | {katilim_ratio} | " + " | ".join(row_cells) + " |"
        print(row_str)
        diff_report_lines.append(row_str)

    diff_report_content = "\n".join(diff_report_lines)
    
    diff_file = Path("scratch/consistency_after_diff_report.md")
    diff_file.parent.mkdir(parents=True, exist_ok=True)
    with open(diff_file, "w", encoding="utf-8") as f:
        f.write(diff_report_content)
    
    print(f"\n[OUTPUT] Diff raporu yazildi: {diff_file}")


def main():
    bdr_path = Path("data/bdr_samples/0f7bfcfebe7f422aa56aba17a28c610c.txt")
    if not bdr_path.exists():
        print(f"HATA: {bdr_path} bulunamadi.")
        sys.exit(1)
        
    output_base = Path("outputs/consistency_experiment_after")
    output_base.mkdir(parents=True, exist_ok=True)
    
    results = []
    num_runs = 3
    for run_idx in range(1, num_runs + 1):
        res = run_single_pipeline(run_idx, bdr_path, output_base)
        results.append(res)
        
    analyze_runs_diff(results)


if __name__ == "__main__":
    main()
