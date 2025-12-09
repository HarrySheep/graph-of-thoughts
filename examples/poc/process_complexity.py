import pandas as pd

def parse_complex_excel(file_path):
    # ================= 关键修改 1：指定 Sheet 名称 =================
    # 请务必将 '系统复杂度评分-更新' 换成你 Excel 底部实际的 Tab 名字
    # header=None 表示不让 pandas 自作聪明去猜表头，我们按坐标硬解
    try:
        df = pd.read_excel(file_path, sheet_name='系统复杂度评估-旧2022年-供参考', header=None)
    except ValueError:
        print("错误：找不到指定的 Sheet，请检查代码里的 sheet_name 是否和 Excel 左下角的名字完全一致。")
        return None

    # ================= 关键修改 2：重新定位坐标 =================
    
    # 1. 定位系统名称行 (Excel 第1行 -> Index 0)
    # 使用 ffill() 处理合并单元格 (例如 D1是渠道系统，E1其实是空，填满它)
    row_system_names = df.iloc[0].ffill()
    
    # 2. 定位 "评分" 标记行 (Excel 第4行 -> Index 3)
    row_marker = df.iloc[3]

    # 3. 找出所有 "评分" 所在的列索引
    # 逻辑：遍历第4行，只要格子里的字是 "评分"，记下这一列
    target_cols = []
    for col_idx, value in row_marker.items():
        if str(value).strip() == "评分":
            # 拿到这一列对应的系统名 (从第1行拿)
            sys_name = row_system_names[col_idx]
            target_cols.append({
                "name": sys_name,
                "col_idx": col_idx
            })

    print(f"解析到 {len(target_cols)} 个系统列: {[t['name'] for t in target_cols]}")

    # ================= 关键修改 3：提取数据 =================
    results = []
    
    # 数据从 Excel 第5行开始 (Index 4)
    # 我们只需要关注 A 列 (Index 0) 有内容的行
    # 因为合并单元格的数据只会在第一行出现，下面行的 A 列都是 NaN
    for row_idx in range(4, len(df)):
        category_cell = df.iloc[row_idx, 0] # A列：分类名称
        
        # 只有当 A 列不为空，且看起来像是分类（比如 "1.", "2." 开头）时，才提取数据
        if pd.notna(category_cell) and str(category_cell)[0].isdigit():
            
            # 清洗分类名称 (去掉换行符)
            clean_category = str(category_cell).split('\n')[0].strip()
            
            row_data = {"考核项": clean_category}
            
            # 遍历刚才找到的那些系统列，把分数抓出来
            for target in target_cols:
                score = df.iloc[row_idx, target['col_idx']]
                
                # 如果是合并单元格的空值或未填，设为 0
                if pd.isna(score):
                    score = 0
                row_data[target['name']] = score
            
            results.append(row_data)

    return pd.DataFrame(results)

# 运行部分
if __name__ == "__main__":
    file_path = r"D:\Downloads\aDrive\GOT\GOT\code\graph-of-thoughts\examples\poc\系统复杂度评估20240711.xlsx" # 记得改文件名
    
    df_result = parse_complex_excel(file_path)
    
    if df_result is not None:
        print("\n--- 提取结果预览 ---")
        print(df_result)
        
        # 保存结果
        df_result.to_excel("清洗后的分数.xlsx", index=False)
        print("\n已保存为 '清洗后的分数.xlsx'")