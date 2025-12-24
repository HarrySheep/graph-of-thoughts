## 4.2 评估指标 (Evaluation Metrics)

针对功能点分析中两类不同性质的任务——判别任务（Judgment Tasks）与识别任务（Selection Tasks），本研究分别构建了针对性的评估体系，以确保实验结果能够客观、全面地反映模型在合规性判断与语义理解层面的综合能力。

### 4.2.1 判别任务评估指标 (Metrics for Judgment Tasks)
判别任务（包括 ILF 判别与 EIF 判别）本质上属于**二分类问题 (Binary Classification)**。在此类任务中，模型的输入为明确的候选实体，输出为“合规（True）”或“不合规（False）”的布尔判断。我们采用机器学习领域的标准指标来衡量模型的效能：

*   **Accuracy (准确率)**：评估模型整体分类的正确程度。
    $$ Accuracy = \frac{TP + TN}{TP + TN + FP + FN} $$
*   **Precision (精确率)**：反映模型在判定为“是”的功能点中，真正符合 IFPUG 规则的比例。
    $$ Precision = \frac{TP}{TP + FP} $$
*   **Recall (召回率)**：反映模型在所有真实功能点中，成功识别出的比例。
    $$ Recall = \frac{TP}{TP + FN} $$
*   **F1 Score**：Precision 与 Recall 的调和平均数，用于综合衡量模型在正负样本不平衡情况下的稳健性。
    $$ F1 = 2 \cdot \frac{Precision \cdot Recall}{Precision + Recall} $$

### 4.2.2 识别任务评估指标 (Metrics for Selection Tasks)
识别任务（包括 ILF 识别与 EIF 识别）属于**信息抽取 (Information Extraction)** 范畴。由于自然语言表达的多样性，模型输出的实体名称（例如“员工信息表”）与标准答案（例如“人员档案”）往往存在字面不一致但语义相同的情况。传统的精确字符串匹配（Exact String Match）极易导致误判。为此，本研究引入了以 **语义相似度 (Semantic Similarity)** 为核心的模糊评估体系。即我们在计算 True Positive (TP) 时，不再局限于字符串的完全匹配，而是引入一个独立的 LLM 评分器（Scorer）来计算预测项 $p$ 与真值项 $t$ 之间的语义距离 $Sim(p, t)$。
只有当 $Sim(p, t) > \tau$（本实验中设定阈值 $\tau=0.7$）时，我们才认定该预测有效。该机制能够有效处理：
*   **跨语言匹配**：如识别 "Job Information" 与 "职位信息" 为同一实体。
*   **同义词/近义词**：如识别 "Screen Security" 与 "界面权限控制" 的等价性。
根据语义相似度设计，我们定义了以下两种语义匹配指标：

#### 1. 基础语义匹配 (Basic Semantic Measures)
*   **Exact Matches (精确匹配数)**：
    仅统计经过去除大小写、去空格等标准化处理后，与 Ground Truth 完全一致的预测数量：
    $$ N_{exact} = \sum_{p \in Pred} \mathbb{I}(p \in Truth_{norm}) $$

*   **Semantic Matches (语义匹配列表)**：
    对于非精确匹配项，记录所有通过 LLM 语义校验（相似度 $ > 0.7$）的配对 $(p, t)$ 及其相似度得分。这提供了可解释的定性分析依据。

*   **Fuzzy Score (模糊匹配总分 / Effective TP)**：
    作为“有效真阳性数” ($TP_{fuzzy}$)，它是所有有效匹配项的语义相似度累加值。该指标通过给予高相似度匹配更高的权重，比单纯的 0/1 计数更细腻地反映了模型的“理解深度”。
    $$ TP_{fuzzy} = \sum_{p \in Pred, t \in Truth} match(p, t) \cdot Sim(p, t) $$
    其中 $match(p,t)$ 为基于最大权重的一对一匹配映射。

#### 2. 模糊效能指标 (Fuzzy Performance Metrics)
基于 $TP_{fuzzy}$，我们重新定义了适用于非结构化抽取任务的 Precision、Recall 和 F1：

*   **Fuzzy Precision (模糊精确率)**：
    $$ Precision_{fuzzy} = \frac{TP_{fuzzy}}{|Pred|} $$
    其中 $|Pred|$ 为模型预测出的总实体数量。

*   **Fuzzy Recall (模糊召回率)**：
    $$ Recall_{fuzzy} = \frac{TP_{fuzzy}}{|Truth|} $$
    其中 $|Truth|$ 为标准答案中的总实体数量。

*   **Fuzzy F1 Score (模糊 F1 分数)**：
    $$ F1_{fuzzy} = 2 \cdot \frac{Precision_{fuzzy} \cdot Recall_{fuzzy}}{Precision_{fuzzy} + Recall_{fuzzy}} $$

这套指标体系（Fuzzy Metrics）能够在模型预测结果“虽不中亦不远”时给予合理评价，例如当模型识别出的“职位分配”与真值“Job Assignment”相似度为 0.9 时，其贡献的 $TP$ 为 0.9 而非 0，从而避免了因术语差异导致的性能低估。
