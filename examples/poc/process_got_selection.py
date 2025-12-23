import os
import sys
import json
import logging
import importlib.util

# Add project root to sys.path to allow importing graph_of_thoughts
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

from graph_of_thoughts import controller, language_models

# Dynamic import helper
def import_module_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Import eif_selection and ilf_selection
# Import eif_selection and ilf_selection
eif_path = os.path.join(current_dir, 'eif_selection_inference.py')
ilf_path = os.path.join(current_dir, 'ilf_selection_inference.py')

eif_module = import_module_from_path('eif_selection', eif_path)
ilf_module = import_module_from_path('ilf_selection', ilf_path)

trans_path = os.path.join(current_dir, 'transaction_selection_inference.py')
trans_module = import_module_from_path('transaction_selection', trans_path)

def process_got_selection(root_dir, limit=None):
    """
    Process requirements using GoT for EIF and ILF selection.
    """
    
    # Setup Logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('got_selection.log', encoding='utf-8')
        ]
    )

    # Setup LLM
    config_path = os.path.join(project_root, "graph_of_thoughts", "language_models", "config.json")
    print(f"Config path: {config_path}")
    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        return

    lm = language_models.ChatGPT(
        config_path,
        model_name="deepseek", # Or qwen3, as per your config
        cache=True
    )

    # Get all month directories
    items = os.listdir(root_dir)
    month_dirs = [item for item in items if os.path.isdir(os.path.join(root_dir, item)) and item != 'rubbish']
    
    processed_count = 0
    
    for month in month_dirs:
        month_path = os.path.join(root_dir, month)
        req_folders = os.listdir(month_path)
        
        for req_folder in req_folders:
            if limit and processed_count >= limit:
                print(f"Reached limit of {limit} folders.")
                return

            req_path = os.path.join(month_path, req_folder)
            txt_path = os.path.join(req_path, 'requirement_text.txt')
            output_path = os.path.join(req_path, 'got_selection_result.json')
            
            if not os.path.exists(txt_path):
                continue
                
            if os.path.exists(output_path):
                print(f"Skipping already processed: {req_folder}")
                continue

            print(f"Processing: {req_folder}")
            
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    requirement_text = f.read()
                
                # --- EIF Selection ---
                logging.info(f"Running EIF Selection for {req_folder}")
                eif_graph = eif_module.got()
                eif_controller = controller.Controller(
                    lm,
                    eif_graph,
                    eif_module.FunctionPointPrompter(),
                    eif_module.FunctionPointParser(),
                    {
                        "requirement_text": requirement_text,
                        "ground_truth": [], # No ground truth for new files
                        "current": "",
                        "method": "got",
                    },
                )
                eif_controller.run()
                
                # Extract EIF result from the graph (find the final KeepBestN operation)
                # Since we can't easily access the graph state directly without traversing, 
                # we rely on the fact that the controller updates the state.
                # However, the controller doesn't return the final state directly in run().
                # We need to look at the graph's final operation's state.
                # Or simpler: The parser extracts the answer into "final_answer" in the state.
                # But we have multiple operations. The last one holds the final result.
                
                # Let's inspect the graph to find the final operation
                final_op = eif_graph.operations[-1]
                # The state of the final operation is what we want. 
                # But wait, operations don't store state, thoughts do.
                # The controller creates thoughts.
                # Actually, the easiest way is to use the output_graph method or inspect the last thought.
                # But for this script, let's just grab the "final_answer" from the last thought of the final operation.
                
                # HACK: Accessing private/internal structures if needed, or just iterate thoughts.
                # The controller stores the graph. The graph has operations. Operations have thoughts.
                
                eif_result = []
                if final_op.thoughts:
                    best_thought = max(final_op.thoughts, key=lambda t: t.score if t.score is not None else 0)
                    if "final_answer" in best_thought.state:
                        eif_result = best_thought.state["final_answer"]

                # --- ILF Selection ---
                logging.info(f"Running ILF Selection for {req_folder}")
                ilf_graph = ilf_module.got()
                ilf_controller = controller.Controller(
                    lm,
                    ilf_graph,
                    ilf_module.FunctionPointPrompter(),
                    ilf_module.FunctionPointParser(),
                    {
                        "requirement_text": requirement_text,
                        "ground_truth": [],
                        "current": "",
                        "method": "got",
                    },
                )
                ilf_controller.run()
                
                ilf_result = []
                final_op_ilf = ilf_graph.operations[-1]
                if final_op_ilf.thoughts:
                    best_thought_ilf = max(final_op_ilf.thoughts, key=lambda t: t.score if t.score is not None else 0)
                    if "final_answer" in best_thought_ilf.state:
                        ilf_result = best_thought_ilf.state["final_answer"]

                # --- Transaction Selection (EI, EO, EQ) ---
                # Use CoT as 'got' logic in transaction script might be incomplete for structure
                trans_types = [("EI", trans_module.cot_ei), ("EO", trans_module.cot_eo), ("EQ", trans_module.cot_eq)]
                trans_results = {}

                for t_type, t_func in trans_types:
                    logging.info(f"Running {t_type} Selection for {req_folder}")
                    t_graph = t_func()
                    t_controller = controller.Controller(
                        lm,
                        t_graph,
                        trans_module.FunctionPointPrompter(),
                        trans_module.FunctionPointParser(),
                        {
                            "requirement_text": requirement_text,
                            "ground_truth": [],
                            "current": "",
                            "method": "cot",
                            "function_type": t_type # Pass type to Prompter
                        },
                    )
                    t_controller.run()
                    
                    t_result = []
                    final_op_t = t_graph.operations[-1]
                    if final_op_t.thoughts:
                        best_thought_t = max(final_op_t.thoughts, key=lambda t: t.score if t.score is not None else 0)
                        if "final_answer" in best_thought_t.state:
                            t_result = best_thought_t.state["final_answer"]
                    trans_results[t_type] = t_result

                # Save Result
                result_data = {
                    "EIF": eif_result,
                    "ILF": ilf_result,
                    "EI": trans_results["EI"],
                    "EO": trans_results["EO"],
                    "EQ": trans_results["EQ"]
                }
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=4)
                
                print(f"Saved results to: {output_path}")
                processed_count += 1
                
            except Exception as e:
                logging.error(f"Error processing {req_folder}: {e}")
                print(f"Error processing {req_folder}: {e}")

if __name__ == "__main__":
    root_directory = r"d:\MEM\论文\GOT\code\graph-of-thoughts\examples\poc\requirement fetch"
    print(f"Starting GoT selection in: {root_directory}")
    # Limit to 1 for testing first
    process_got_selection(root_directory, limit=5)
    print("GoT selection complete.")
