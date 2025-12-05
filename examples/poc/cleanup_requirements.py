import os
import shutil
import json

def cleanup_requirements(root_dir):
    """
    Traverses the requirement fetch directory and moves incomplete folders to rubbish.
    """
    rubbish_dir = os.path.join(root_dir, 'rubbish')
    if not os.path.exists(rubbish_dir):
        os.makedirs(rubbish_dir)
        print(f"Created rubbish directory: {rubbish_dir}")

    # Get all month directories
    items = os.listdir(root_dir)
    month_dirs = [item for item in items if os.path.isdir(os.path.join(root_dir, item)) and item != 'rubbish']

    for month in month_dirs:
        month_path = os.path.join(root_dir, month)
        print(f"Checking month: {month}")
        
        req_folders = os.listdir(month_path)
        for req_folder in req_folders:
            req_path = os.path.join(month_path, req_folder)
            
            if not os.path.isdir(req_path):
                continue
                
            # Check for required files
            txt_path = os.path.join(req_path, 'requirement_text.txt')
            json_path = os.path.join(req_path, 'functions_cleaned.json')
            
            has_text = os.path.exists(txt_path)
            has_json = os.path.exists(json_path)
            
            is_valid = False
            if has_text and has_json:
                # Check if JSON is empty
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list) and len(data) > 0:
                            is_valid = True
                        else:
                            print(f"Invalid JSON (empty): {req_folder}")
                except Exception:
                    print(f"Invalid JSON (error): {req_folder}")
                    
                # Check if text file is too small (likely just header)
                if is_valid:
                    if os.path.getsize(txt_path) < 200:
                        print(f"Invalid Text (too small): {req_folder}")
                        is_valid = False

            if not is_valid:
                # Move to rubbish
                target_month_dir = os.path.join(rubbish_dir, month)
                if not os.path.exists(target_month_dir):
                    os.makedirs(target_month_dir)
                
                target_path = os.path.join(target_month_dir, req_folder)
                
                try:
                    if os.path.exists(target_path):
                        print(f"Target exists, skipping: {target_path}")
                    else:
                        shutil.move(req_path, target_path)
                        print(f"Moved invalid folder: {req_folder} -> rubbish/{month}/")
                except Exception as e:
                    print(f"Error moving {req_folder}: {e}")

if __name__ == "__main__":
    root_directory = r"d:\Downloads\aDrive\GOT\GOT\code\graph-of-thoughts\examples\poc\requirement fetch"
    print(f"Starting cleanup in: {root_directory}")
    cleanup_requirements(root_directory)
    print("Cleanup complete.")
