# 功能点评估 - 提示模板和示例

## 提示模板

### GENERATE: identify_prompt
用于识别需求文档中的候选ILF。替换`{doc}`为需求文档内容。
```
分析以下需求文档，识别所有可能的内部逻辑文件(ILF)候选项。对于每个候选项，说明其名称、包含的属性、维护方式，以及是否构成ILF的初步判断和理由。

请按以下格式输出结果：
<Candidates>
[候选项1]
名称：[数据组名称]
属性：[属性列表]
维护：[维护方式]
判断：[是/否]
理由：[判断理由]

[候选项2]
...
</Candidates>

需求文档内容：
{doc}
```

### SCORE: score_prompt
用于评估候选ILF的识别结果。替换`{doc}`为原始需求文档，`{candidates}`为候选项列表。
```
评估以下候选ILF识别结果的质量。评分标准：
1. 完整性（0-10分）：是否识别出所有可能的ILF
2. 准确性（0-10分）：判断是否符合IFPUG标准
3. 理由充分性（0-10分）：解释是否清晰合理

请在分析后，给出0-10的总体评分，10分表示完全符合标准，0分表示完全不符合。

需求文档：
{doc}

候选项列表：
{candidates}

请提供评分理由，并在<Score>标签中给出最终分数。
```

### GENERATE: verify_prompt
用于验证候选ILF是否满足IFPUG标准。替换`{doc}`为原始需求文档，`{candidates}`为候选项列表。
```
验证以下候选ILF是否满足IFPUG标准的三个条件：
1. 是否是用户可识别的逻辑相关数据组
2. 是否在应用边界内维护
3. 是否通过应用的基本流程维护

对每个候选项进行详细分析，并给出最终判断。

需求文档：
{doc}

候选项列表：
{candidates}

请按以下格式输出验证结果：
<Verification>
[候选项1]
条件1：[是/否] - [分析理由]
条件2：[是/否] - [分析理由]
条件3：[是/否] - [分析理由]
最终判断：[是/否]
详细说明：[综合分析]

[候选项2]
...
</Verification>
```

### GENERATE: aggregate_prompt
用于合并和整理验证结果。替换`{doc}`为原始需求文档，`{verifications}`为验证结果。
```
整合以下ILF验证结果，解决可能的重复或冲突，生成最终的ILF列表。

需求文档：
{doc}

验证结果：
{verifications}

请按以下格式输出最终结果：
<Final>
确认的ILF总数：[数量]

[ILF 1]
名称：[名称]
理由：[确认理由]

[ILF 2]
...
</Final>
```

## 示例输入输出

### 示例1：职位信息管理

输入文档：
```
# 需求文档：人力资源管理系统 - 职位信息管理模块

## 1. 用户需求概述
用户需要能够录入、查询和生成关于职位信息的报表。

## 2. 核心数据需求
必须维护的职位相关信息包括：
- 职位编号 (Job number)
- 职位名称 (Job name)
- 职位薪资等级 (Job pay grade)
- 职位描述行号 (Job description line number)
- 职位描述内容 (Job description lines)
...
```

候选项识别输出：
```
<Candidates>
[候选项1]
名称：Job
属性：
- Job number
- Job name
- Job pay grade
维护：通过职位信息管理模块的基本流程维护
判断：否
理由：Job单独使用时不符合用户逻辑需求，必须包含Job description才能完整表示用户需求。

[候选项2]
名称：Job description
属性：
- Job number
- Job description line number
- Job description lines
维护：通过职位信息管理模块的基本流程维护
判断：否
理由：Job description单独使用时不符合用户逻辑需求，必须与Job结合使用才能完整表示用户需求。

[候选项3]
名称：Job information
属性：
- Job number
- Job name
- Job pay grade
- Job description line number
- Job description lines
维护：通过职位信息管理模块的基本流程维护
判断：是
理由：Job和Job description合并后形成一个逻辑组，符合用户需求，并通过基本流程在应用边界内维护。
</Candidates>
```

评分输出：
```
分析理由：
1. 完整性（10分）：识别出了所有可能的数据组，包括独立的Job、Job description以及它们的组合。
2. 准确性（10分）：正确判断了单独的Job和Job description不构成ILF，而它们的组合构成一个有效的ILF。
3. 理由充分性（9分）：对每个判断都提供了清晰的解释，特别说明了为什么需要合并Job和Job description。

<Score>9.7</Score>
```

验证输出：
```
<Verification>
[候选项3：Job information]
条件1：是 - Job information包含完整的职位信息（基本信息和描述），是用户在业务上可识别的逻辑相关数据组。
条件2：是 - 根据需求文档，这些数据完全在职位信息管理模块内维护，属于应用边界内。
条件3：是 - 通过职位信息管理模块的录入、查询等基本流程进行维护。
最终判断：是
详细说明：Job information完全满足ILF的三个条件，应被确认为一个ILF。Job和Job description的合并是必要的，因为它们在业务逻辑上是不可分割的整体。
</Verification>
```

最终结果：
```
<Final>
确认的ILF总数：1

[ILF 1]
名称：Job information
理由：该数据组包含完整的职位信息（基本信息和描述），是用户可识别的逻辑相关数据组，在应用边界内通过基本流程维护，完全满足ILF的定义要求。
</Final>
``` 