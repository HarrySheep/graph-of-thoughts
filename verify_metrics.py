
import os
import json
import glob

def calculate_metrics(results_dir):
    print(f"Analyzing {results_dir}")
    methods = ['cot', 'got', 'io', 'tot']
    
    with open("results.md", "w", encoding="utf-8") as f_out:
        f_out.write("| Model | Exact | Fuzzy | M_total | P (Macro) | R (Macro) | F1 (Harmonic) | Cost |\n")
        f_out.write("|---|---|---|---|---|---|---|---|\n")

        # Iterate over model directories
        for model_dir in os.listdir(results_dir):
            if not model_dir.startswith("deepseek") and not model_dir.startswith("qwen") and not model_dir.startswith("r1"):
                continue
                
            full_model_dir = os.path.join(results_dir, model_dir)
            if not os.path.isdir(full_model_dir):
                continue
                
            # Find which method is inside
            found_method = None
            for method in methods:
                if os.path.exists(os.path.join(full_model_dir, method)):
                    found_method = method
                    break
            
            if not found_method:
                continue
                
            method_dir = os.path.join(full_model_dir, found_method)
            json_files = glob.glob(os.path.join(method_dir, "*.json"))
            
            total_exact = 0
            total_fuzzy = 0
            total_pred = 0
            total_truth = 0
            total_cost = 0.0
            
            precisions = []
            recalls = []
            
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    metrics = None
                    cost = 0.0
                    
                    if isinstance(data, list):
                        if "cost" in data[-1]:
                            cost = data[-1]["cost"]
                        
                        for item in data:
                            if isinstance(item, dict) and item.get("operation") == "ground_truth_evaluator":
                                 if "thoughts" in item and len(item["thoughts"]) > 0:
                                     thought = item["thoughts"][0]
                                     if "evaluation_metrics" in thought:
                                         metrics = thought["evaluation_metrics"]
                                             
                    if metrics:
                        total_exact += metrics.get("exact_matches", 0)
                        total_fuzzy += metrics.get("fuzzy_score", 0.0)
                        
                        p = metrics.get("precision", 0)
                        r = metrics.get("recall", 0)
                        
                        if isinstance(p, (int, float)): precisions.append(p)
                        if isinstance(r, (int, float)): recalls.append(r)

                    total_cost += cost
                    
                except Exception as e:
                    print(f"Error reading {json_file}: {e}")

            # Macro calculation
            macro_p = sum(precisions) / len(precisions) if precisions else 0
            macro_r = sum(recalls) / len(recalls) if recalls else 0
            
            m_total = total_exact + total_fuzzy # Just for display as per table convention
            
            if (macro_p + macro_r) > 0:
                 table_f1 = 2 * macro_p * macro_r / (macro_p + macro_r)
            else:
                 table_f1 = 0
                 
            row_str = f"| {model_dir} | {total_exact} | {total_fuzzy:.2f} | {m_total:.2f} | {macro_p:.1%} | {macro_r:.1%} | {table_f1:.1%} | ${total_cost:.4f} |\n"
            f_out.write(row_str)
            print(f"Processed {model_dir}")

if __name__ == "__main__":
    calculate_metrics(r"d:\Downloads\aDrive\GOT\GOT\code\graph-of-thoughts\examples\eif_selection\results")
