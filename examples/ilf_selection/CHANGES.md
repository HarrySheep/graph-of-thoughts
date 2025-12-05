# ILF功能点分析实验修改说明

## 修改概述

将原有的"ILF判断实验"（判断单个候选功能点是否为ILF）改造为"ILF功能点分析实验"（从需求文档中识别所有ILF功能点）。

## 主要变更

### 1. 数据格式变更

**旧格式** (`ilf_samples.csv`):
- 列: `doc_id`, `candidate_ilf`, `requirement_text`, `ground_truth`
- 每行: 一个需求文档 + 一个候选功能点 + 布尔判断结果
- 示例: `1, "Job information", "需求文档...", TRUE`

**新格式** (`ilf_selection_samples_init.csv`):
- 列: `doc_id`, `true_ilf`, `requirement_text`
- 每行: 一个需求文档 + 正确的ILF功能点列表（逗号分隔）
- 示例: `1, "Job information", "需求文档..."`

### 2. Prompt模板修改

所有prompt模板（IO, CoT, ToT, GoT）都已修改为：
- **旧**: 判断候选功能点是否为ILF，输出"是/否"
- **新**: 分析需求文档，输出所有ILF功能点列表

关键变化：
- 移除了 `{candidate_name}` 参数
- 输出格式改为: `ILF功能点列表：[功能点1, 功能点2, ...]`

### 3. Parser解析器修改

#### `extract_answer()` 方法
- **旧**: 提取"是/否"答案，返回字符串
- **新**: 提取ILF功能点列表，返回 `List[str]`

新增功能：
- 支持多种输出格式识别
- 自动清理功能点名称（去除编号、多余空格等）
- Fallback机制：如果标准格式失败，尝试从文本中提取数据实体名称

#### `parse_generate_answer()` 方法
- `final_answer` 字段从布尔值改为列表

### 4. 评分机制重新设计

这是最关键的修改。由于答案从布尔值变为列表，评分变得更加复杂。

#### 新增函数

**`normalize_ilf_name(name: str) -> str`**
- 标准化功能点名称用于比较
- 转小写、去除空格、去除括号内容

**`calculate_ilf_similarity(predicted: List[str], ground_truth: List[str]) -> float`**
- 计算预测列表和真实列表的相似度
- 使用精确匹配 + 模糊匹配相结合的方法
- 返回F1-score (0.0 - 1.0)

算法说明：
1. **精确匹配**: 标准化后的功能点名称完全相同
2. **模糊匹配**: 对未精确匹配的项，计算字符串相似度（基于Jaccard）
3. **F1-score**: 同时考虑准确率和召回率

**`_string_similarity(s1: str, s2: str) -> float`**
- 计算两个字符串的Jaccard相似度

#### 修改的函数

**`score_assessment(state: Dict) -> float`**
- **旧**: 布尔匹配，返回0.0或1.0
- **新**: 返回列表相似度分数（0.0-1.0的连续值）

**`test_ilf_assessment(state: Dict) -> bool`**
- **旧**: 直接比较布尔值
- **新**: 计算相似度，如果 >= 0.8 则认为正确

### 5. 数据加载逻辑修改

在 `run()` 函数中：
- 读取 `ilf_selection_samples_init.csv` 而不是 `ilf_samples.csv`
- 编码从GBK改为UTF-8
- 解析 `true_ilf` 字段为列表
- 移除 `candidate_name` 参数

### 6. 控制器初始化修改

传递给 `Controller` 的初始状态：
```python
{
    "requirement_text": data[1],  # 需求文档
    "ground_truth": data[2],      # ILF功能点列表
    "current": "",
    "method": method.__name__,
}
```

注意移除了 `candidate_name` 字段。

## 评分方案说明

### 为什么选择这个方案？

用户提到评分是个难点，可能需要LLM打分或人工打分。当前实现的方案是**基于规则的自动评分**，具有以下优点：

1. **完全自动化**: 不需要额外的LLM调用或人工介入
2. **成本低**: 无额外API费用
3. **可解释性强**: 分数计算逻辑清晰
4. **连续评分**: 返回0-1之间的连续值，而不是简单的对/错

### 评分细节

#### 精确匹配
```
预测: ["Job information", "Employee information"]
真实: ["Job information", "Employee data"]
精确匹配: 1个 (Job information)
```

#### 模糊匹配
```
未匹配的预测: ["Employee information"]
未匹配的真实: ["Employee data"]
字符串相似度: ~0.7 (因为"employee"相同)
如果相似度 > 0.6, 计入部分分数
```

#### F1-score计算
```
总匹配分数 = 精确匹配数 + 模糊匹配分数
准确率 = 总匹配分数 / 预测功能点数
召回率 = 总匹配分数 / 真实功能点数
F1 = 2 * (准确率 * 召回率) / (准确率 + 召回率)
```

### 替代方案

如果需要更准确的评分，可以考虑：

1. **LLM评分**: 
   - 实现 `score_prompt()` 和 `parse_score_answer()`
   - 让LLM比较两个列表的语义相似度
   - 优点: 更准确
   - 缺点: 额外成本、速度慢

2. **人工评分**:
   - 修改 `score_assessment()` 返回 `None` 或固定值
   - 在实验后手动评分
   - 优点: 最准确
   - 缺点: 不可扩展

## 使用方法

运行修改后的实验：

```bash
cd examples/ilf_selection
python ilf_selection.py
```

默认配置:
- 样本: [0, 1] (前两个样本)
- 方法: [io, cot]
- 预算: $5
- 模型: r1-7b

## 注意事项

1. **CSV文件编码**: 新文件使用UTF-8编码
2. **功能点名称标准化**: 比较时会自动标准化，不区分大小写和多余空格
3. **模糊匹配阈值**: 当前设为0.6，可根据需要调整
4. **测试阈值**: test_ilf_assessment中相似度阈值为0.8

## 后续优化建议

1. **改进模糊匹配**: 
   - 使用更高级的字符串相似度算法（如编辑距离）
   - 考虑领域知识（如"Employee"和"员工"的映射）

2. **引入LLM评分**:
   - 对于难以判断的情况，可选择性使用LLM评分
   - 设置阈值，只对相似度在0.4-0.8之间的结果使用LLM

3. **多样本测试**:
   - 在更多样本上测试评分方案的有效性
   - 根据实际结果调整参数

4. **结果分析**:
   - 添加详细的评分日志
   - 统计精确匹配、模糊匹配的比例
   - 识别常见的误判模式

## 修改文件清单

- ✅ `ilf_selection.py` - 主实验文件（所有修改）
- ✅ `ilf_selection_samples_init.csv` - 新数据格式（已存在）
- ✅ `CHANGES.md` - 本文档

## 测试建议

1. 先用1-2个样本测试，确保pipeline正常运行
2. 检查日志中的相似度计算细节
3. 人工检查几个结果，验证评分合理性
4. 逐步增加样本数量和方法复杂度

---

修改完成时间: 2025-11-07

