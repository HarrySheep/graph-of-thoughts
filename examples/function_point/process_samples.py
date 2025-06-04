#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import re
from typing import Dict, List, Tuple

def extract_doc_info(filename: str) -> Tuple[int, str]:
    """
    从文件名中提取文档ID和名称。
    
    :param filename: 文件名
    :type filename: str
    :return: (文档ID, 文档名称)
    :rtype: Tuple[int, str]
    """
    # 提取文档ID和名称
    match = re.match(r'(\d+)(.*?)(?:1|2)\.txt$', filename)
    if not match:
        raise ValueError(f"无法从文件名 '{filename}' 中提取ID和名称")
    
    doc_id = int(match.group(1))
    doc_name = match.group(2).strip()
    
    return doc_id, doc_name

def parse_analysis_result(content: str) -> Tuple[int, List[str], List[str]]:
    """
    解析ILF分析结果。
    
    :param content: 分析结果文本
    :type content: str
    :return: (ILF总数, ILF名称列表, ILF理由列表)
    :rtype: Tuple[int, List[str], List[str]]
    """
    # 提取ILF总数
    total_match = re.search(r'结论:\s*(\d+)个ILF功能点', content)
    total_ilfs = int(total_match.group(1)) if total_match else 0
    
    # 提取ILF名称和理由
    ilf_names = []
    ilf_reasons = []
    
    # 使用正则表达式匹配表格内容
    table_pattern = r'\|\s*([\w\s\u4e00-\u9fff]+)\s*\|\s*(是|否)\s*\|\s*(.+?)\s*\|'
    matches = re.finditer(table_pattern, content)
    
    for match in matches:
        name, is_ilf, reason = match.groups()
        if is_ilf == "是":
            ilf_names.append(name.strip())
            ilf_reasons.append(reason.strip())
    
    return total_ilfs, ilf_names, ilf_reasons

def process_samples(samples_dir: str, output_file: str):
    """
    处理示例数据并生成CSV文件。
    
    :param samples_dir: 示例数据目录
    :type samples_dir: str
    :param output_file: 输出CSV文件路径
    :type output_file: str
    """
    # 准备数据结构
    samples = {}  # {doc_id: {field: value}}
    
    # 读取所有文件
    for filename in os.listdir(samples_dir):
        filepath = os.path.join(samples_dir, filename)
        
        try:
            if filename.endswith("1.txt"):  # 需求文档
                doc_id, doc_name = extract_doc_info(filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                    if doc_id not in samples:
                        samples[doc_id] = {}
                    samples[doc_id].update({
                        "doc_id": doc_id,
                        "doc_name": doc_name,
                        "requirement_text": content
                    })
            
            elif filename.endswith("2.txt"):  # 分析结果
                doc_id, _ = extract_doc_info(filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    total_ilfs, ilf_names, ilf_reasons = parse_analysis_result(content)
                    
                    if doc_id not in samples:
                        samples[doc_id] = {}
                    samples[doc_id].update({
                        "analysis_result": content,
                        "total_ilfs": total_ilfs,
                        "ilf_names": "|".join(ilf_names),
                        "ilf_reasons": "|".join(ilf_reasons)
                    })
        except Exception as e:
            print(f"处理文件 '{filename}' 时出错: {str(e)}")
            continue
    
    # 写入CSV文件
    fieldnames = ["doc_id", "doc_name", "requirement_text", "analysis_result", 
                 "total_ilfs", "ilf_names", "ilf_reasons"]
    
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # 按文档ID排序写入
        for doc_id in sorted(samples.keys()):
            writer.writerow(samples[doc_id])

def main():
    # 设置路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    samples_dir = os.path.join(current_dir, "ILF samples")
    output_file = os.path.join(current_dir, "ilf_samples.csv")
    
    # 处理样本
    process_samples(samples_dir, output_file)
    print(f"数据处理完成，结果保存在: {output_file}")
    
    # 验证结果
    with open(output_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        print(f"\n处理结果统计:")
        print(f"总样本数: {len(rows)}")
        print(f"字段列表: {', '.join(reader.fieldnames)}")
        print("\nILF统计:")
        for row in rows:
            print(f"文档 {row['doc_id']} ({row['doc_name']}): {row['total_ilfs']} 个ILF")

if __name__ == "__main__":
    main() 