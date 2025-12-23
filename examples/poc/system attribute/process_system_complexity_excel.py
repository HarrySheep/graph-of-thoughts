import pandas as pd
import json
import os

def excel_to_system_json(file_path, output_file='output.json'):
    try:
        # 1. 读取 Excel 文件，sheet_name=None 表示读取所有 sheet
        # header=0 表示第一行是表头
        print(f"正在读取文件: {file_path}...")
        all_sheets = pd.read_excel(file_path, sheet_name=None, header=0)
        
        final_data = {}

        # 2. 遍历每一个 Sheet
        for sheet_name, df in all_sheets.items():
            print(f"正在处理 Sheet: {sheet_name}")
            
            # 数据清洗：如果有空值，填充为0或空字符串（根据你的需求）
            # df = df.fillna(0) 
            
            # 3. 关键步骤：
            # 将第一列（也就是"考核项"这一列）设为索引
            # 这样后面的 to_dict 就会自动把这一列的值作为内部的 key
            if not df.empty:
                # 获取第一列的列名（例如"考核项"）
                first_col_name = df.columns[0]
                df.set_index(first_col_name, inplace=True)
                
                # 4. 转为字典
                # orient='dict' 格式为: {列名(系统名): {索引名(考核项): 值}}
                sheet_data = df.to_dict(orient='dict')
                
                final_data[sheet_name] = sheet_data

        # 5. 保存为 JSON 文件
        with open(output_file, 'w', encoding='utf-8') as f:
            # ensure_ascii=False 保证中文正常显示
            # indent=4 保证格式美观缩进
            json.dump(final_data, f, ensure_ascii=False, indent=4)
            
        print(f"转换成功！文件已保存为: {output_file}")

    except Exception as e:
        print(f"发生错误: {e}")

# --- 执行部分 ---
if __name__ == '__main__':
    # 请在这里修改你的 Excel 文件路径
    input_excel = '清洗后的分数.xlsx' 
    
    # 检查文件是否存在
    if os.path.exists(input_excel):
        excel_to_system_json(input_excel)
    else:
        print(f"找不到文件: {input_excel}，请检查路径。")