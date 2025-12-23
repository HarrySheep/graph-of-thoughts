"""
按系统(description)聚合 SonarQube 数据
对所有数值属性取中位数
"""

import json
import statistics
from pathlib import Path
from collections import defaultdict


def aggregate_by_system(input_file: str, output_file: str):
    """
    按系统聚合数据，数值属性取中位数
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
    """
    print(f"读取文件: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"共 {len(data)} 个项目")
    
    # 按 description 分组收集数据
    # 结构: {description: {metric_name: [values]}}
    systems = defaultdict(lambda: {
        'project_keys': [],
        'metrics': defaultdict(list)
    })
    
    no_desc_projects = []
    error_projects = []
    
    for project_key, project in data.items():
        # 跳过错误项目
        if project.get('error'):
            error_projects.append(project_key)
            continue
        
        desc = project.get('description')
        if not desc:
            no_desc_projects.append(project_key)
            continue
        
        # 记录项目 key
        systems[desc]['project_keys'].append(project_key)
        
        # 收集所有 metrics 的值
        metrics = project.get('metrics', {})
        for metric_name, value in metrics.items():
            if isinstance(value, (int, float)):
                systems[desc]['metrics'][metric_name].append(value)
    
    print(f"按系统分组后: {len(systems)} 个系统")
    print(f"无 description 的项目: {len(no_desc_projects)} 个")
    print(f"错误项目: {len(error_projects)} 个")
    
    # 计算每个系统的中位数
    aggregated_data = {}
    
    for desc, system_data in systems.items():
        project_count = len(system_data['project_keys'])
        
        # 计算每个 metric 的中位数
        metrics_median = {}
        for metric_name, values in system_data['metrics'].items():
            if values:
                median_value = statistics.median(values)
                # 如果所有原始值都是整数，结果也保持整数
                if all(isinstance(v, int) for v in values) and median_value == int(median_value):
                    metrics_median[metric_name] = int(median_value)
                else:
                    # 保留2位小数
                    metrics_median[metric_name] = round(median_value, 2)
        
        aggregated_data[desc] = {
            'system_name': desc,
            'project_count': project_count,
            'project_keys': system_data['project_keys'],
            'metrics_median': metrics_median
        }
    
    # 按项目数量降序排序
    sorted_data = dict(sorted(
        aggregated_data.items(),
        key=lambda x: x[1]['project_count'],
        reverse=True
    ))
    
    # 写入新文件
    print(f"写入文件: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=2)
    
    # 统计信息
    output_size = Path(output_file).stat().st_size / 1024
    print(f"输出文件大小: {output_size:.2f} KB")
    print(f"聚合完成!")
    
    # 打印汇总
    print(f"\n{'='*60}")
    print(f"系统汇总 (共 {len(sorted_data)} 个系统):")
    print(f"{'='*60}")
    print(f"{'项目数':>6} | {'系统名称'}")
    print(f"{'-'*60}")
    for desc, info in sorted_data.items():
        print(f"{info['project_count']:>6} | {desc}")


if __name__ == '__main__':
    script_dir = Path(__file__).parent
    input_file = script_dir / 'sonar-output-transformed.json'
    output_file = script_dir / 'sonar-output-by-system.json'
    
    aggregate_by_system(str(input_file), str(output_file))

