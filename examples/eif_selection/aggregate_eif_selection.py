import os
import json

def aggregate_eif_selection():
    output_file = os.path.join(os.path.dirname(__file__), "..", "..", "mypaper", "experiment", "section_5.2_results_eif_selection.md")
    lines = []
    lines.append("## 5.2 EIF 识别实验结果 (EIF Selection Results)\n")
    lines.append("本节展示了对比不同推理范式在从非结构化需求文档中提取 EIF 逻辑实体的实验结果。识别任务不仅考验模型的规则理解，还考验其在术语表达差异下的语义匹配能力。\n")
    lines.append("### 5.2.1 实验结果汇总\n")
    lines.append("| 模型方案 | Solved | M_total | Exact | Fuzzy | Avg Precision | Avg Recall | Avg F1 | 推理成本 |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    results_dir = os.path.join(os.path.dirname(__file__), "results")
    for folder in sorted(os.listdir(results_dir)):
        folder_path = os.path.join(results_dir, folder)
        if not os.path.isdir(folder_path):
            continue
            
        parts = folder.split('_')
        if len(parts) < 2:
            continue
        method = parts[1]
        
        subdir = os.path.join(folder_path, method)
        if not os.path.exists(subdir):
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
                                        break
                            if "problem_solved" in item:
                                problem_solved = item["problem_solved"][0] if item["problem_solved"] else False
                        if sample_metrics:
                            break
                    
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

    lines.append("\n### 5.2.2 结果分析与讨论\n")
    lines.append("1. **语义匹配的必要性**：实验结果显示 `Fuzzy Score` 占据了 `M_total` 的主要部分，而 `Exact Matches` 几乎为 0。这验证了我们在 4.2 节中的假设：即使模型识别正确，其术语表达也难以与专家标注完全吻合。")
    lines.append("2. **GoT 的性能提升**：在大部分模型上，GoT 的 `Solved` 比例和 `M_total` 均优于 IO 和 CoT。")
    lines.append("3. **推理成本的权衡**：尽管 GoT 带来了性能提升，但其成本通常是 IO 的数倍到十倍。对于识别任务这种高 Token 消耗的任务，如何优化 GoT 的拓扑以降低冗余生成是未来的研究方向。")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    print(f"Successfully wrote results to {output_file}")

if __name__ == "__main__":
    aggregate_eif_selection()
