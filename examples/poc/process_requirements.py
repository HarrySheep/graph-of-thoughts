import os
import json
import glob
from docx import Document

def process_functions_json(file_path):
    """
    Reads functions.txt (JSON), extracts relevant fields, and saves as functions_cleaned.json.
    Refinements:
    - Filter out items where tabType == "1".
    - Map functionType: "01"->ILF, "02"->EIF, "04"->EF.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cleaned_data = []
        function_type_map = {
            "01": "ILF",
            "02": "EIF",
            "04": "EF"
        }

        if 'result' in data and isinstance(data['result'], list):
            for item in data['result']:
                # Filter by tabType
                if str(item.get('tabType')) == "1":
                    continue

                if 'formIssueFunctionDOList' in item:
                    for func in item['formIssueFunctionDOList']:
                        # Map functionType
                        raw_type = func.get("functionType")
                        mapped_type = function_type_map.get(raw_type, raw_type)

                        cleaned_data.append({
                            "functionName": func.get("functionName"),
                            "functionType": mapped_type,
                            "estimateWorkload": func.get("estimateWorkload"),
                            "changeScale": func.get("changeScale"),
                            "systemName": func.get("systemName")
                        })
        
        output_path = os.path.join(os.path.dirname(file_path), 'functions_cleaned.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=4)
        print(f"Processed JSON: {output_path}")
        return True
    except Exception as e:
        print(f"Error processing JSON {file_path}: {e}")
        return False

def convert_docx_to_txt(file_path):
    """
    Converts .docx file to .txt file.
    """
    try:
        doc = Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        
        text_content = '\n'.join(full_text)
        
        output_path = os.path.join(os.path.dirname(file_path), 'requirement_text.txt')
        # Append if multiple docs exist? Or overwrite? 
        # Requirement says "convert to text", usually implies one main doc. 
        # Let's append if it exists to handle multiple docs in one folder.
        mode = 'a' if os.path.exists(output_path) else 'w'
        with open(output_path, mode, encoding='utf-8') as f:
            f.write(f"--- Source: {os.path.basename(file_path)} ---\n")
            f.write(text_content)
            f.write("\n\n")
            
        print(f"Converted Doc: {file_path} -> {output_path}")
        return True
    except Exception as e:
        print(f"Error converting {file_path}: {e}")
        return False

def process_directory(root_dir):
    """
    Traverses the directory and processes files.
    """
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Process functions.txt
        if 'functions.txt' in filenames:
            process_functions_json(os.path.join(dirpath, 'functions.txt'))
        
        # Process Requirement Docs
        for filename in filenames:
            if filename.lower().endswith('.docx') and '需求' in filename:
                if '确认单' not in filename:
                    convert_docx_to_txt(os.path.join(dirpath, filename))
                else:
                    print(f"Skipping Confirmation Sheet: {os.path.join(dirpath, filename)}")

if __name__ == "__main__":
    root_directory = r"d:\Downloads\aDrive\GOT\GOT\code\graph-of-thoughts\examples\poc\requirement fetch"
    
    # Months to process (excluding 2024-02 and 2024-08 which are already done)
    months_to_process = [
        '2024-03', 
        '2024-05', 
        '2024-06', 
        '2024-10', 
        '2024-11', 
        '2024-12', 
        '2025-01'
    ]

    print(f"Starting processing for months: {months_to_process}")
    
    for month in months_to_process:
        month_path = os.path.join(root_directory, month)
        if os.path.exists(month_path):
            print(f"Processing month: {month}")
            process_directory(month_path)
        else:
            print(f"Warning: Directory not found for month {month}: {month_path}")

    print("Processing complete.")
