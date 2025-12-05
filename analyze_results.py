import os
import json
import pandas as pd
from collections import defaultdict

# Define the root directories to analyze
TARGET_DIRS = [
    r"d:\Downloads\aDrive\GOT\GOT\code\graph-of-thoughts\examples\ilf_selection\results",
    r"d:\Downloads\aDrive\GOT\GOT\code\graph-of-thoughts\examples\eif_selection\results",
    r"d:\Downloads\aDrive\GOT\GOT\code\graph-of-thoughts\examples\eif_judge\results"
]

def analyze_directory(base_dir):
    results = []
    
    # Walk through the directory to find experiment folders
    for root, dirs, files in os.walk(base_dir):
        if "config.json" in files:
            # This is an experiment directory
            config_path = os.path.join(root, "config.json")
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception as e:
                print(f"Error reading config at {config_path}: {e}")
                continue

            # Extract metadata
            model = config.get("lm", "unknown")
            methods = config.get("methods", ["unknown"])
            method = methods[0] if isinstance(methods, list) and methods else "unknown"
            
            # The result files are usually in a subdirectory named after the method
            # But sometimes the method name in config doesn't match the folder name exactly
            # Let's look for a subdirectory that is NOT the current one, or just check known method names
            # Based on `ls` output, there is a subdirectory like `cot`, `got`, `io`, `tot`
            
            result_subdir = None
            for d in dirs:
                if d in ["cot", "got", "tot", "io", "bfs", "dfs"]:
                    result_subdir = os.path.join(root, d)
                    break
            
            if not result_subdir:
                # Fallback: check if there are json files in the current dir (unlikely based on ls)
                # Or maybe the method name is different.
                # Let's try to use the method name from config
                candidate = os.path.join(root, method)
                if os.path.exists(candidate):
                    result_subdir = candidate
                else:
                    # print(f"Could not find result subdir for {root}, method {method}")
                    continue

            # Process result files
            metrics = {
                "total_cost": 0.0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "f1_scores": [],
                "precisions": [],
                "recalls": [],
                "exact_matches": [],
                "problem_solved_count": 0,
                "total_files": 0
            }

            for res_file in os.listdir(result_subdir):
                if not res_file.endswith(".json"):
                    continue
                
                res_path = os.path.join(result_subdir, res_file)
                try:
                    with open(res_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except:
                    continue
                
                metrics["total_files"] += 1
                
                # Extract metrics from the list of operations
                file_cost = 0
                file_f1 = 0
                file_precision = 0
                file_recall = 0
                file_solved = False
                
                for item in data:
                    # Cost is usually in an item with "cost" key
                    if "cost" in item:
                        file_cost = item.get("cost", 0)
                        metrics["total_cost"] += file_cost
                        metrics["total_prompt_tokens"] += item.get("prompt_tokens", 0)
                        metrics["total_completion_tokens"] += item.get("completion_tokens", 0)
                    
                    # Evaluation metrics
                    if "evaluation_metrics" in item:
                        eval_m = item["evaluation_metrics"]
                        file_f1 = eval_m.get("f1_score", 0)
                        file_precision = eval_m.get("precision", 0)
                        file_recall = eval_m.get("recall", 0)
                        metrics["f1_scores"].append(file_f1)
                        metrics["precisions"].append(file_precision)
                        metrics["recalls"].append(file_recall)
                        metrics["exact_matches"].append(eval_m.get("exact_matches", 0))

                    # Problem solved
                    if "problem_solved" in item:
                        # It might be a list [true] or boolean
                        ps = item["problem_solved"]
                        if isinstance(ps, list) and len(ps) > 0:
                            if ps[0]:
                                file_solved = True
                        elif isinstance(ps, bool) and ps:
                            file_solved = True
                
                if file_solved:
                    metrics["problem_solved_count"] += 1

            # Aggregate for this experiment
            num_files = metrics["total_files"]
            if num_files > 0:
                avg_f1 = sum(metrics["f1_scores"]) / len(metrics["f1_scores"]) if metrics["f1_scores"] else 0
                avg_precision = sum(metrics["precisions"]) / len(metrics["precisions"]) if metrics["precisions"] else 0
                avg_recall = sum(metrics["recalls"]) / len(metrics["recalls"]) if metrics["recalls"] else 0
                success_rate = metrics["problem_solved_count"] / num_files
                avg_cost = metrics["total_cost"] / num_files
                
                results.append({
                    "Task": os.path.basename(os.path.dirname(base_dir)), # e.g. ilf_selection
                    "Model": model,
                    "Method": method,
                    "Files": num_files,
                    "Avg_F1": avg_f1,
                    "Avg_Precision": avg_precision,
                    "Avg_Recall": avg_recall,
                    "Success_Rate": success_rate,
                    "Avg_Cost": avg_cost,
                    "Total_Cost": metrics["total_cost"]
                })

    return results

all_results = []
for d in TARGET_DIRS:
    if os.path.exists(d):
        all_results.extend(analyze_directory(d))

df = pd.DataFrame(all_results)
# Sort for better readability
df = df.sort_values(by=["Task", "Model", "Method"])

# Save to CSV
output_path = r"d:\Downloads\aDrive\GOT\GOT\code\graph-of-thoughts\analysis_results.csv"
df.to_csv(output_path, index=False, encoding='utf-8')
print(f"Results saved to {output_path}")
