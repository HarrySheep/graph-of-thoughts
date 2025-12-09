"""
转换 sonar-output.txt JSON 结构
- 将 measures 数组转换为以 metric 名称为 key 的字典
- 去掉 periods 属性，只保留 value
"""

import json
from pathlib import Path


def transform_sonar_data(input_file: str, output_file: str):
    """
    转换 SonarQube 输出数据格式
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
    """
    print(f"读取文件: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"共 {len(data)} 个项目")
    
    transformed_data = {}
    error_count = 0
    success_count = 0
    
    for project_key, project_json_str in data.items():
        # 二次解析内层 JSON
        project_data = json.loads(project_json_str)
        
        # 检查是否有错误
        if 'errors' in project_data:
            transformed_data[project_key] = {
                'error': True,
                'message': project_data['errors'][0].get('msg', 'Unknown error')
            }
            error_count += 1
            continue
        
        # 获取组件信息
        component = project_data.get('component', {})
        
        # 构建新的项目结构
        new_project = {
            'id': component.get('id'),
            'key': component.get('key'),
            'name': component.get('name'),
            'description': component.get('description'),
            'qualifier': component.get('qualifier'),
            'metrics': {}
        }
        
        # 转换 measures 数组为字典
        measures = component.get('measures', [])
        for measure in measures:
            metric_name = measure.get('metric')
            if metric_name:
                # 只保留 value，去掉 periods
                value = measure.get('value')
                if value is not None:
                    # 尝试转换为数值类型
                    try:
                        if '.' in value:
                            new_project['metrics'][metric_name] = float(value)
                        else:
                            new_project['metrics'][metric_name] = int(value)
                    except (ValueError, TypeError):
                        new_project['metrics'][metric_name] = value
        
        transformed_data[project_key] = new_project
        success_count += 1
    
    print(f"成功转换: {success_count} 个项目")
    print(f"错误项目: {error_count} 个")
    
    # 写入新文件
    print(f"写入文件: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(transformed_data, f, ensure_ascii=False, indent=2)
    
    # 统计文件大小
    input_size = Path(input_file).stat().st_size / 1024 / 1024
    output_size = Path(output_file).stat().st_size / 1024 / 1024
    print(f"原文件大小: {input_size:.2f} MB")
    print(f"新文件大小: {output_size:.2f} MB")
    print("转换完成!")


if __name__ == '__main__':
    script_dir = Path(__file__).parent
    input_file = script_dir / 'sonar-output.txt'
    output_file = script_dir / 'sonar-output-transformed.json'
    
    transform_sonar_data(str(input_file), str(output_file))

