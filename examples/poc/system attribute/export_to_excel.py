"""
将聚合后的 SonarQube 数据导出为 Excel
行: 系统名称
列: metrics 指标
"""

import json
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("需要安装 pandas 和 openpyxl:")
    print("pip install pandas openpyxl")
    exit(1)


def export_to_excel(input_file: str, output_file: str):
    """
    导出聚合数据到 Excel
    
    Args:
        input_file: 输入 JSON 文件路径
        output_file: 输出 Excel 文件路径
    """
    print(f"读取文件: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"共 {len(data)} 个系统")
    
    # 收集所有唯一的 metrics 列名
    all_metrics = set()
    for system_data in data.values():
        all_metrics.update(system_data.get('metrics_median', {}).keys())
    
    # 按类别排序指标
    metric_order = [
        # 基本信息
        'project_count',
        # 代码规模
        'ncloc', 'lines', 'statements', 'files', 'directories', 'classes', 'functions',
        'comment_lines', 'comment_lines_density',
        # 复杂度
        'complexity', 'cognitive_complexity',
        # 质量评级
        'reliability_rating', 'security_rating', 'sqale_rating',
        # Bug 和漏洞
        'bugs', 'vulnerabilities', 'code_smells',
        # 违规分级
        'violations', 'blocker_violations', 'critical_violations', 
        'major_violations', 'minor_violations', 'info_violations',
        # 问题状态
        'open_issues', 'confirmed_issues', 'reopened_issues', 
        'false_positive_issues', 'wont_fix_issues',
        # 技术债务
        'sqale_index', 'sqale_debt_ratio', 'effort_to_reach_maintainability_rating_a',
        # 修复工作量
        'reliability_remediation_effort', 'security_remediation_effort',
        # 代码重复
        'duplicated_lines', 'duplicated_lines_density', 'duplicated_blocks', 'duplicated_files',
        # 测试覆盖
        'coverage', 'line_coverage', 'branch_coverage',
        'lines_to_cover', 'uncovered_lines', 'conditions_to_cover', 'uncovered_conditions',
        # 测试执行
        'tests', 'test_errors', 'test_failures', 'skipped_tests',
        'test_success_density', 'test_execution_time',
    ]
    
    # 确保所有指标都在排序列表中
    ordered_metrics = [m for m in metric_order if m in all_metrics or m == 'project_count']
    remaining = sorted(all_metrics - set(metric_order))
    ordered_metrics.extend(remaining)
    
    # 构建数据行
    rows = []
    for system_name, system_data in data.items():
        row = {'system_name': system_name}
        row['project_count'] = system_data.get('project_count', 0)
        
        metrics = system_data.get('metrics_median', {})
        for metric in ordered_metrics:
            if metric != 'project_count':
                row[metric] = metrics.get(metric, None)
        
        rows.append(row)
    
    # 创建 DataFrame
    df = pd.DataFrame(rows)
    
    # 设置列顺序
    columns = ['system_name'] + ordered_metrics
    columns = [c for c in columns if c in df.columns]
    df = df[columns]
    
    # 按项目数降序排序
    df = df.sort_values('project_count', ascending=False)
    
    print(f"数据维度: {df.shape[0]} 行 x {df.shape[1]} 列")
    
    # 导出到 Excel
    print(f"写入文件: {output_file}")
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='系统指标汇总', index=False)
        
        # 获取工作表进行格式调整
        worksheet = writer.sheets['系统指标汇总']
        
        # 调整列宽
        worksheet.column_dimensions['A'].width = 50  # 系统名称列
        for col_idx in range(2, len(columns) + 1):
            col_letter = chr(64 + col_idx) if col_idx <= 26 else f'A{chr(64 + col_idx - 26)}'
            worksheet.column_dimensions[col_letter].width = 15
    
    output_size = Path(output_file).stat().st_size / 1024
    print(f"输出文件大小: {output_size:.2f} KB")
    print("导出完成!")
    
    # 打印列名参考
    print(f"\n列名说明:")
    print("-" * 60)
    metric_desc = {
        'system_name': '系统名称',
        'project_count': '项目数量',
        'ncloc': '非注释代码行数',
        'lines': '总代码行数',
        'statements': '语句数',
        'files': '文件数',
        'directories': '目录数',
        'classes': '类数',
        'functions': '函数数',
        'comment_lines': '注释行数',
        'comment_lines_density': '注释密度(%)',
        'complexity': '圈复杂度',
        'cognitive_complexity': '认知复杂度',
        'reliability_rating': '可靠性评级(1-5)',
        'security_rating': '安全性评级(1-5)',
        'sqale_rating': '可维护性评级(1-5)',
        'bugs': 'Bug数',
        'vulnerabilities': '漏洞数',
        'code_smells': '代码异味数',
        'violations': '总违规数',
        'sqale_index': '技术债务(分钟)',
        'sqale_debt_ratio': '技术债务比率(%)',
        'coverage': '总覆盖率(%)',
        'duplicated_lines_density': '重复代码密度(%)',
    }
    for col in columns[:15]:  # 只显示前15个
        desc = metric_desc.get(col, col)
        print(f"  {col}: {desc}")
    print("  ...")


if __name__ == '__main__':
    script_dir = Path(__file__).parent
    input_file = script_dir / 'sonar-output-by-system.json'
    output_file = script_dir / 'sonar-systems-metrics.xlsx'
    
    export_to_excel(str(input_file), str(output_file))

