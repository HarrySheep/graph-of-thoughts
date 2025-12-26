import os
import json

def aggregate_ilf_selection():
    output_file = os.path.join(os.path.dirname(__file__), "..", "..", "mypaper", "experiment", "section_5.4_results_ilf_selection.md")
    lines = []
    lines.append("## 5.4 ILF 识别实验结果 (ILF Selection Results)\n")
    lines.append("本节展示了对比不同推理范式在从非结构化需求文档中提取 ILF 逻辑实体的实验结果。识别任务不仅考验模型的规则理解，还考验其在术语表达差异下的语义匹配能力。\n")
    lines.append("### 5.4.1 实验结果汇总\n")
    lines.append("| 模型方案 | Solved | M_total | Exact | Fuzzy | Avg Precision | Avg Recall | Avg F1 | 推理成本 |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    results_dir = os.path.join(os.path.dirname(__file__), "results")
    if not os.path.exists(results_dir):
        print(f"Results directory not found: {results_dir}")
        return

    for folder in sorted(os.listdir(results_dir)):
        folder_path = os.path.join(results_dir, folder)
        if not os.path.isdir(folder_path):
            continue
            
        parts = folder.split('_')
        if len(parts) < 2:
            continue
        method = parts[1]
        
        # In ILF results, the structure seems to be method_date directly, but let's check if there is a subfolder 'method'
        # The EIF script checked for `subdir = os.path.join(folder_path, method)`.
        # Taking a safer approach: check if the 'method' subfolder exists, otherwise assume files are in folder_path
        # But looking at the list_dir output for EIF (Step 9) `.../deepseek_got_.../got/1.json`.
        # And user provided `examples/ilf_selection/results`.
        # Let's assume the structure is consistent: `results/model_method_date/method/1.json`.
        
        subdir = os.path.join(folder_path, method)
        if not os.path.exists(subdir):
            # Fallback checks? Or maybe the method naming in folder is inconsistent (e.g. qwen3-235b vs method)
            # Actually in the EIF script: `method = parts[1]` (e.g. deepseek_got_... -> got).
            # This logic holds if naming convention is consistent.
            if not os.path.exists(subdir):
                 # Try finding a folder that matches method or just look for json files in subdirectories?
                 # Let's stick to the EIF script logic for now as baselines usually share structure.
                 continue
            
        total_exact = 0
        total_fuzzy = 0.0
        sum_precision = 0.0
        sum_recall = 0.0
        total_cost = 0.0
        count = 0
        solved_count = 0
        
        for i in range(1, 11): 
            file_path = os.path.join(subdir, f"{i}.json")
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    sample_metrics = None
                    problem_solved = False
                    for item in data:
                        if isinstance(item, dict):
                            if "thoughts" in item:
                                for thought in item["thoughts"]:
                                    if isinstance(thought, dict) and "evaluation_metrics" in thought:
                                        sample_metrics = thought["evaluation_metrics"]
                                        # Do not break here; we want the LAST one (Fix from EIF script)
                            
                            # Check if this item has problem_solved at the top level
                            if "problem_solved" in item:
                                problem_solved = item["problem_solved"][0] if item["problem_solved"] else False
                    
                    cost = 0.0
                    if isinstance(data[-1], dict) and "cost" in data[-1]:
                        cost = data[-1]["cost"]
                    
                    if sample_metrics:
                        total_exact += sample_metrics.get("exact_matches", 0)
                        total_fuzzy += sample_metrics.get("fuzzy_score", 0.0)
                        sum_precision += sample_metrics.get("precision", 0.0)
                        sum_recall += sample_metrics.get("recall", 0.0)
                        total_cost += cost
                        count += 1
                        if problem_solved:
                            solved_count += 1
                            
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")
        
        if count > 0:
            m_total = total_exact + total_fuzzy
            avg_precision = sum_precision / count
            avg_recall = sum_recall / count
            avg_f1 = (2 * avg_precision * avg_recall / (avg_precision + avg_recall)) if (avg_precision + avg_recall) > 0 else 0
            
            lines.append(f"| {folder} | {solved_count}/{count} | {m_total:.2f} | {total_exact} | {total_fuzzy:.2f} | {avg_precision:.1%} | {avg_recall:.1%} | {avg_f1:.1%} | ${total_cost:.4f} |")

    lines.append("\n### 5.4.2 结果分析与讨论\n")
    lines.append("1. **待补充**: 根据上方表格数据补充具体的分析结论。")
    lines.append("2. **待补充**: ...")
 
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    print(f"Successfully wrote results to {output_file}")

if __name__ == "__main__":
    aggregate_ilf_selection()
