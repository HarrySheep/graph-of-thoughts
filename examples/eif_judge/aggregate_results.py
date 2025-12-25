import os
import json
import csv
import sys

def aggregate_results(results_dir, labels, task_name=""):
    if not os.path.exists(results_dir):
        print(f"Results directory not found: {results_dir}")
        return

    print(f"\n--- Aggregating {task_name} Results ---")
    # Iterate through each experiment folder
    for folder in sorted(os.listdir(results_dir)):
        folder_path = os.path.join(results_dir, folder)
        if not os.path.isdir(folder_path):
            continue
            
        # Determine the method name from the folder name (e.g., deepseek_got_...)
        parts = folder.split('_')
        if len(parts) < 2:
            continue
        method = parts[1]
        
        subdir = os.path.join(folder_path, method)
        if not os.path.exists(subdir):
            continue
            
        tp, tn, fp, fn = 0, 0, 0, 0
        total_cost = 0.0
        
        # Process each of the 10 samples
        for i in range(1, 11):
            file_path = os.path.join(subdir, f"{i}.json")
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    solved = False
                    cost = 0.0
                    
                    # Extract problem_solved and cost from the JSON structure
                    for item in data:
                        if isinstance(item, dict):
                            if "problem_solved" in item:
                                solved = item["problem_solved"][0]
                            if "cost" in item:
                                cost = item["cost"]
                    
                    total_cost += cost
                    gt = labels.get(i)
                    
                    if solved:
                        if gt is True:
                            tp += 1
                        else:
                            tn += 1
                    else:
                        if gt is True:
                            fn += 1
                        else:
                            fp += 1
                            
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")
        
        print(f"{folder} | TP:{tp} TN:{tn} FP:{fp} FN:{fn} | Cost:{total_cost:.7f}")

if __name__ == "__main__":
    # EIF labels
    eif_labels = {
        1: False, 2: True, 3: True, 4: False, 5: False,
        6: False, 7: False, 8: False, 9: False, 10: True
    }
    eif_dir = os.path.join(os.path.dirname(__file__), "results")
    # ILF labels (from function_point/ilf_samples.csv)
    ilf_labels = {
        1: False, 2: False, 3: False, 4: False, 5: False,
        6: True, 7: True, 8: True, 9: True, 10: True
    }
    ilf_dir = os.path.join(os.path.dirname(__file__), "..", "function_point", "results")

    if len(sys.argv) > 1 and sys.argv[1] == "ilf":
        aggregate_results(ilf_dir, ilf_labels, "ILF")
    else:
        aggregate_results(eif_dir, eif_labels, "EIF")
