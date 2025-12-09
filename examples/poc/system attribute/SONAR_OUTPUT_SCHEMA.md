# SonarQube 输出数据结构解读文档

## 概述

`sonar-output.txt` 文件包含 SonarQube 代码质量分析的输出数据，是一个大型 JSON 文件（约 8.3MB）。

### 基本统计
- **总项目数**: 2,052 个
- **有效项目数**: 2,051 个（包含 component 数据）
- **错误项目数**: 1 个（仅包含 errors 信息）
- **无度量数据项目**: 109 个

---

## JSON 结构

### 顶层结构

```json
{
  "project_key_1": "内层JSON字符串",
  "project_key_2": "内层JSON字符串",
  ...
}
```

顶层是一个字典，键为项目标识符（如 `youcash-pls-dev_20221221`），值为**字符串化的 JSON**（需要二次解析）。

### 内层结构（正常项目）

```json
{
  "component": {
    "id": "AYT0xhrbSnb7zzjQuMwc",
    "key": "youcash-pls-dev_20221221",
    "name": "youcash-pls-dev_20221221",
    "description": "贷后检查系统",
    "qualifier": "TRK",
    "measures": [...]
  }
}
```

#### Component 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | SonarQube 内部唯一标识符 |
| `key` | string | 项目键名，通常与顶层键相同 |
| `name` | string | 项目显示名称 |
| `description` | string | 项目描述（可选） |
| `qualifier` | string | 组件类型，所有项目均为 `TRK`（Project） |
| `measures` | array | 度量指标数组 |

### 内层结构（错误项目）

当项目分析失败时，返回错误结构：

```json
{
  "errors": [
    {
      "msg": "An error has occurred. Please contact your administrator"
    }
  ]
}
```

---

## Measures（度量指标）结构

每个度量指标的结构：

```json
{
  "metric": "complexity",
  "value": "308",
  "periods": [
    {
      "index": 1,
      "value": "-244"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `metric` | string | 指标名称 |
| `value` | string | 当前值（部分指标可能无此字段） |
| `periods` | array | 变化周期数据（可选） |

### Periods（变化周期）说明

`periods` 记录了相对于某个基准点的变化量：
- `index`: 周期索引（通常为 1）
- `value`: 相对于基准的变化值（正数表示增加，负数表示减少）

---

## 度量指标分类详解

### 1. 代码规模指标 (Size Metrics)

| 指标 | 说明 | 示例值 |
|------|------|--------|
| `ncloc` | 非注释代码行数 (Non-Comment Lines of Code) | 1950 |
| `lines` | 总代码行数 | 2617 |
| `statements` | 语句数量 | 1398 |
| `files` | 文件数量 | 2 |
| `directories` | 目录数量 | 2 |
| `classes` | 类数量 | 2 |
| `functions` | 函数/方法数量 | 72 |
| `comment_lines` | 注释行数 | 379 |
| `comment_lines_density` | 注释密度百分比 | 16.3% |

### 2. 复杂度指标 (Complexity Metrics)

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| `complexity` | 圈复杂度 (Cyclomatic Complexity) | 基于控制流图 |
| `cognitive_complexity` | 认知复杂度 | 基于代码可理解性 |

### 3. 代码问题指标 (Issues Metrics)

#### 3.1 按严重程度分类

| 指标 | 说明 | 严重等级 |
|------|------|----------|
| `blocker_violations` | 阻断级违规 | 🔴 最高 |
| `critical_violations` | 严重级违规 | 🟠 高 |
| `major_violations` | 主要级违规 | 🟡 中 |
| `minor_violations` | 次要级违规 | 🟢 低 |
| `info_violations` | 提示级违规 | ⚪ 最低 |

#### 3.2 问题状态统计

| 指标 | 说明 |
|------|------|
| `violations` | 总违规数 |
| `open_issues` | 未解决问题数 |
| `confirmed_issues` | 已确认问题数 |
| `reopened_issues` | 重新打开的问题数 |
| `false_positive_issues` | 误报问题数 |
| `wont_fix_issues` | 不修复问题数 |

#### 3.3 问题类型统计

| 指标 | 说明 |
|------|------|
| `bugs` | Bug 数量 |
| `vulnerabilities` | 漏洞数量 |
| `code_smells` | 代码异味数量 |

#### 3.4 新代码期间的问题（带 `new_` 前缀）

以 `new_` 为前缀的指标表示在**新代码周期**内新增的问题：
- `new_bugs`, `new_vulnerabilities`, `new_code_smells`
- `new_blocker_violations`, `new_critical_violations` 等

### 4. 质量评级指标 (Rating Metrics)

评级范围：`1.0`（最佳/A级）到 `5.0`（最差/E级）

| 指标 | 说明 | 数据中出现的值 |
|------|------|---------------|
| `reliability_rating` | 可靠性评级（基于 Bug） | 1.0 ~ 5.0 |
| `security_rating` | 安全性评级（基于漏洞） | 1.0, 2.0, 4.0, 5.0 |
| `sqale_rating` | 可维护性评级（基于技术债务） | 1.0 ~ 4.0 |

#### 评级对照表

| 数值 | 等级 | 含义 |
|------|------|------|
| 1.0 | A | 优秀 |
| 2.0 | B | 良好 |
| 3.0 | C | 一般 |
| 4.0 | D | 较差 |
| 5.0 | E | 很差 |

### 5. 技术债务指标 (Technical Debt)

| 指标 | 说明 |
|------|------|
| `sqale_index` | 技术债务（分钟） |
| `sqale_debt_ratio` | 技术债务比率（%） |
| `new_sqale_debt_ratio` | 新代码技术债务比率 |
| `new_technical_debt` | 新增技术债务 |
| `effort_to_reach_maintainability_rating_a` | 达到A级可维护性所需工作量 |

### 6. 修复工作量指标 (Remediation Effort)

| 指标 | 说明 |
|------|------|
| `reliability_remediation_effort` | 修复可靠性问题所需工作量 |
| `security_remediation_effort` | 修复安全问题所需工作量 |
| `new_reliability_remediation_effort` | 新代码可靠性修复工作量 |
| `new_security_remediation_effort` | 新代码安全修复工作量 |

### 7. 代码覆盖率指标 (Coverage Metrics)

| 指标 | 说明 |
|------|------|
| `coverage` | 总体覆盖率（%） |
| `line_coverage` | 行覆盖率（%） |
| `branch_coverage` | 分支覆盖率（%） |
| `lines_to_cover` | 需要覆盖的代码行数 |
| `uncovered_lines` | 未覆盖的代码行数 |
| `conditions_to_cover` | 需要覆盖的条件数 |
| `uncovered_conditions` | 未覆盖的条件数 |

### 8. 测试指标 (Test Metrics)

| 指标 | 说明 |
|------|------|
| `tests` | 测试用例数量 |
| `test_errors` | 测试错误数 |
| `test_failures` | 测试失败数 |
| `test_success_density` | 测试成功率（%） |
| `test_execution_time` | 测试执行时间（ms） |
| `skipped_tests` | 跳过的测试数 |

### 9. 代码重复指标 (Duplication Metrics)

| 指标 | 说明 |
|------|------|
| `duplicated_lines` | 重复代码行数 |
| `duplicated_lines_density` | 重复代码密度（%） |
| `duplicated_blocks` | 重复代码块数 |
| `duplicated_files` | 包含重复代码的文件数 |

### 10. 质量门禁状态 (Quality Gate)

| 指标 | 说明 | 可能值 |
|------|------|--------|
| `alert_status` | 质量门禁状态 | `OK`（通过）/ `ERROR`（失败） |

---

## Python 解析示例

```python
import json

# 读取文件
with open('sonar-output.txt', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 遍历所有项目
for project_key, project_json_str in data.items():
    # 二次解析内层 JSON
    project_data = json.loads(project_json_str)
    
    # 检查是否有错误
    if 'errors' in project_data:
        print(f"Project {project_key} has errors: {project_data['errors']}")
        continue
    
    # 获取组件信息
    component = project_data['component']
    project_name = component.get('name', 'N/A')
    description = component.get('description', 'N/A')
    
    # 提取度量指标
    measures = component.get('measures', [])
    metrics_dict = {}
    for m in measures:
        metric_name = m['metric']
        current_value = m.get('value', None)
        period_value = None
        if 'periods' in m and m['periods']:
            period_value = m['periods'][0].get('value')
        
        metrics_dict[metric_name] = {
            'current': current_value,
            'change': period_value
        }
    
    # 示例：获取圈复杂度
    complexity = metrics_dict.get('complexity', {}).get('current', 'N/A')
    print(f"{project_name}: complexity = {complexity}")
```

---

## 重要注意事项

1. **字符串化 JSON**: 顶层值是字符串，需要用 `json.loads()` 二次解析
2. **可选字段**: 不是所有项目都有所有指标，需要做空值处理
3. **空度量列表**: 109 个项目的 measures 为空数组
4. **数值类型**: 所有数值都以字符串形式存储，使用时需要类型转换
5. **periods 含义**: periods 表示相对于某个基线（通常是上次分析或新代码周期）的变化量

---

## 关键指标快速参考

用于快速评估代码质量的核心指标：

| 维度 | 关键指标 | 健康阈值 |
|------|----------|----------|
| **整体质量** | `alert_status` | OK |
| **可靠性** | `reliability_rating`, `bugs` | ≤2.0, 尽量为0 |
| **安全性** | `security_rating`, `vulnerabilities` | ≤2.0, 尽量为0 |
| **可维护性** | `sqale_rating`, `code_smells` | ≤2.0, 尽量少 |
| **复杂度** | `complexity`, `cognitive_complexity` | 根据项目规模判断 |
| **测试覆盖** | `coverage`, `line_coverage` | ≥80% 为佳 |
| **代码重复** | `duplicated_lines_density` | ≤5% |
| **技术债务** | `sqale_debt_ratio` | ≤5% |

