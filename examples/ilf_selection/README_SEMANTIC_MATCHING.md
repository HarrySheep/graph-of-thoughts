# ILF功能点语义匹配功能说明

## 概述

为了解决中英文ILF功能点名称对比的问题，我们实现了基于LLM的语义相似度判断功能。这个功能可以智能地判断两个不同表达的功能点名称是否指代同一个实体。

## 问题背景

### 之前的问题
- Ground truth使用英文：`["Suspended job", "Suspended job description"]`
- LLM预测使用中文：`["职位挂起文件", "操作日志"]`
- 简单的字符串匹配无法识别它们的语义关系

### 硬编码映射的局限性
使用映射字典的方法"治标不治本"：
1. **维护成本高**：每个新功能点都需要手动添加映射
2. **覆盖不全**：LLM可能使用各种表达方式，无法穷举
3. **语义理解差**：无法理解同义词、缩写、描述性表达等

## 解决方案

### 基于LLM的语义相似度判断

我们实现了一个智能的相似度计算系统：

1. **精确匹配**（快速路径）
   - 首先进行标准化后的字符串精确匹配
   - 成本：无

2. **语义匹配**（可选）
   - 对未匹配的功能点，使用LLM判断语义相似度
   - LLM会考虑：
     * 中英文翻译
     * 同义词
     * 缩写
     * 描述性表达
   - 返回0.0-1.0的相似度分数

3. **混合评分**
   - 精确匹配得1分
   - 语义匹配得相似度分数（0.7以上才算匹配）
   - 使用F1-score综合准确率和召回率

## 使用方法

### 1. 启用LLM语义匹配

在 `ilf_selection.py` 中修改：

```python
# 在 run 函数中，找到这一行：
use_semantic = False  # 设置为True启用LLM语义相似度判断

# 改为：
use_semantic = True  # 启用LLM语义判断
```

### 2. 工作原理

```python
# 示例：判断两个功能点是否相同
check_ilf_semantic_similarity(
    "职位挂起文件",           # 中文表达
    "Suspended job",         # 英文表达
    lm=your_lm_instance,     # LLM实例
    use_lm=True              # 启用LLM判断
)
# 可能返回：0.95（高度相似）

check_ilf_semantic_similarity(
    "操作日志",
    "Suspended job description",
    lm=your_lm_instance,
    use_lm=True
)
# 可能返回：0.2（不相似）
```

### 3. 评分流程

```
预测: ["职位挂起文件", "操作日志"]
真实: ["Suspended job", "Suspended job description"]

步骤1: 精确匹配
  - 标准化后没有精确匹配 → 0个匹配

步骤2: LLM语义匹配
  - "职位挂起文件" vs "Suspended job" → 0.95 ✓ (>0.7)
  - "职位挂起文件" vs "Suspended job description" → 0.30 ✗
  - "操作日志" vs "Suspended job description" → 0.25 ✗
  → 1个语义匹配 (得分0.95)

步骤3: 计算F1-score
  - 精确匹配: 0
  - 模糊匹配: 0.95
  - 总匹配: 0.95
  - Precision: 0.95/2 = 0.475
  - Recall: 0.95/2 = 0.475
  - F1: 0.475
```

## 优势

### ✅ 智能理解
- 自动处理中英文混合
- 理解同义词和缩写
- 考虑业务领域上下文

### ✅ 灵活适应
- 无需维护映射字典
- 自动适应新的表达方式
- 支持任意语言组合

### ✅ 可配置
- 可选启用/禁用
- 可调整阈值
- 有回退机制（LLM失败时用字符串相似度）

## 成本考虑

### API调用次数
- **不启用语义匹配**：0次额外调用
- **启用语义匹配**：最多 `M × N` 次
  - M = 预测中未精确匹配的功能点数
  - N = 真实答案中未精确匹配的功能点数

### 示例
如果有5个测试样本，每个平均2个未匹配项：
- 每个样本：最多 2×2 = 4次调用
- 总计：5×4 = 20次额外调用

### 建议
1. **开发阶段**：关闭（`use_semantic=False`）
2. **最终评估**：开启（`use_semantic=True`）
3. **生产环境**：根据需求决定

## 配置选项

### 相似度阈值
在 `calculate_ilf_similarity` 函数中：
```python
if max_similarity > 0.7 and best_match:  # 默认0.7
```

调整阈值：
- **0.8-0.9**：严格匹配，减少误判
- **0.6-0.7**：宽松匹配，增加召回率

### Prompt定制
在 `check_ilf_semantic_similarity` 函数中可以修改提示词，以：
- 强调特定的匹配规则
- 添加领域知识
- 调整评分标准

## 示例场景

### 场景1：中英文翻译
```
预测: "员工安全"
真实: "Employee security"
结果: 0.95 ✓ 匹配
```

### 场景2：同义词
```
预测: "报表定义"
真实: "Report definition"
结果: 0.95 ✓ 匹配
```

### 场景3：描述性表达
```
预测: "员工数据访问权限控制文件"
真实: "Employee security"
结果: 0.85 ✓ 匹配（描述了同一个实体）
```

### 场景4：不同实体
```
预测: "操作日志"
真实: "Suspended job description"
结果: 0.25 ✗ 不匹配
```

## 日志输出

启用后会在日志中看到：
```
INFO - ILF Similarity - Predicted: ['职位挂起文件', '操作日志'], Truth: ['Suspended job', 'Suspended job description']
INFO -   Exact matches: 0, Fuzzy score: 0.95
INFO -   Semantic matches: 职位挂起文件 <-> Suspended job (0.95)
INFO -   Precision: 0.48, Recall: 0.48, F1: 0.48
```

## 故障处理

### 如果LLM调用失败
系统会自动回退到字符串相似度判断：
```python
try:
    # 尝试使用LLM
    response = lm.generate_text(prompt, 1)
    ...
except Exception as e:
    logging.warning(f"Error using LLM: {e}")
    # 回退到字符串相似度
    return _string_similarity(name1, name2)
```

### 如果语义判断不准确
可以：
1. 调整提示词，增加领域知识
2. 修改相似度阈值
3. 增加预处理规则
4. 使用更强大的模型

## 总结

这个基于LLM的语义匹配方案：
- ✅ 解决了中英文对比问题
- ✅ 无需维护硬编码映射
- ✅ 可选启用，控制成本
- ✅ 有回退机制，保证可用性

是一个"治本"的解决方案！🎉

