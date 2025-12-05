import json
import os

file_path = r"d:\Downloads\aDrive\GOT\GOT\code\graph-of-thoughts\examples\ilf_selection\results\deepseek_cot_2025-11-17_15-55-06\cot\1.json"

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error reading file: {e}")
