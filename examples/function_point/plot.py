#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict, Any

def load_results(results_dir: str) -> List[Dict[str, Any]]:
    """
    加载实验结果。

    :param results_dir: 结果目录路径
    :type results_dir: str
    :return: 结果数据列表
    :rtype: List[Dict[str, Any]]
    """
    results = []
    for folder in os.listdir(results_dir):
        folder_path = os.path.join(results_dir, folder)
        if os.path.isdir(folder_path):
            config_path = os.path.join(folder_path, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                
                # 遍历方法目录
                for method in config["methods"]:
                    method_path = os.path.join(folder_path, method)
                    if os.path.exists(method_path):
                        # 读取每个样本的结果
                        for result_file in os.listdir(method_path):
                            if result_file.endswith(".json"):
                                with open(os.path.join(method_path, result_file), "r") as f:
                                    result = json.load(f)
                                    result["method"] = method
                                    result["lm"] = config["lm"]
                                    results.append(result)
    
    return results

def plot_accuracy(results: List[Dict[str, Any]], output_path: str):
    """
    绘制准确率对比图。

    :param results: 结果数据列表
    :type results: List[Dict[str, Any]]
    :param output_path: 输出文件路径
    :type output_path: str
    """
    methods = sorted(list(set(r["method"] for r in results)))
    accuracies = {m: [] for m in methods}
    
    for r in results:
        method = r["method"]
        # 计算准确率：正确识别的ILF数量 / 实际ILF总数
        accuracy = len(r["correct_ilfs"]) / r["total_ilfs"] if r["total_ilfs"] > 0 else 0
        accuracies[method].append(accuracy)
    
    plt.figure(figsize=(10, 6))
    plt.boxplot([accuracies[m] for m in methods], labels=methods)
    plt.title("ILF识别准确率对比")
    plt.ylabel("准确率")
    plt.grid(True)
    plt.savefig(output_path)
    plt.close()

def plot_time_cost(results: List[Dict[str, Any]], output_path: str):
    """
    绘制时间开销对比图。

    :param results: 结果数据列表
    :type results: List[Dict[str, Any]]
    :param output_path: 输出文件路径
    :type output_path: str
    """
    methods = sorted(list(set(r["method"] for r in results)))
    times = {m: [] for m in methods}
    
    for r in results:
        method = r["method"]
        times[method].append(r["time_cost"])
    
    plt.figure(figsize=(10, 6))
    plt.boxplot([times[m] for m in methods], labels=methods)
    plt.title("处理时间对比")
    plt.ylabel("时间 (秒)")
    plt.grid(True)
    plt.savefig(output_path)
    plt.close()

def plot_token_cost(results: List[Dict[str, Any]], output_path: str):
    """
    绘制Token开销对比图。

    :param results: 结果数据列表
    :type results: List[Dict[str, Any]]
    :param output_path: 输出文件路径
    :type output_path: str
    """
    methods = sorted(list(set(r["method"] for r in results)))
    tokens = {m: [] for m in methods}
    
    for r in results:
        method = r["method"]
        tokens[method].append(r["token_cost"])
    
    plt.figure(figsize=(10, 6))
    plt.boxplot([tokens[m] for m in methods], labels=methods)
    plt.title("Token使用量对比")
    plt.ylabel("Token数量")
    plt.grid(True)
    plt.savefig(output_path)
    plt.close()

def main():
    # 设置中文字体
    plt.rcParams["font.sans-serif"] = ["SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    
    # 加载结果
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    if not os.path.exists(results_dir):
        print("结果目录不存在")
        return
    
    results = load_results(results_dir)
    if not results:
        print("没有找到结果数据")
        return
    
    # 创建图表输出目录
    plots_dir = os.path.join(results_dir, "plots")
    if not os.path.exists(plots_dir):
        os.makedirs(plots_dir)
    
    # 绘制图表
    plot_accuracy(results, os.path.join(plots_dir, "accuracy.png"))
    plot_time_cost(results, os.path.join(plots_dir, "time_cost.png"))
    plot_token_cost(results, os.path.join(plots_dir, "token_cost.png"))
    
    print("图表生成完成，保存在:", plots_dir)

if __name__ == "__main__":
    main() 