## 3.5 评估指标体系与语义匹配机制 (Evaluation Metrics & Semantic Matching Mechanism)

为了全面且客观地量化 GoT 框架在功能点识别任务中的效能，我们构建了一套分层评估体系。考虑到本研究涉及“功能点判定 (Judge)”与“功能点抽取 (Selection)”两类性质不同的子任务，我们分别定义了针对性的评估指标，并引入了基于大语言模型的语义一致性校验机制，以解决生成式任务中普遍存在的“语义对齐”难题。

### 3.5.1 判别任务评估指标 (Metrics for Classification Tasks)

针对 **EIF/ILF 判别任务 (Judge Task)**，其本质是一个二分类问题（Binary Classification），即判断给定的数据实体是否属于特定的功能点类别（Yes/No）。对于此类任务，评估的核心在于模型判定的准确性与稳健性。如果不采用严格的统计指标，仅凭单一的准确率往往无法揭示模型在正负样本不平衡时的真实表现。因此，我们采用以下标准指标集：

设 $TP$ (True Positive) 为真阳性样本数，$TN$ (True Negative) 为真阴性样本数，$FP$ (False Positive) 为假阳性样本数，$FN$ (False Negative) 为假阴性样本数。

1.  **准确率 (Accuracy)**：
    衡量模型整体判断正确的比例，计算公式为：
    $$ Accuracy = \frac{TP + TN}{TP + TN + FP + FN} $$
    尽管准确率是最直观的指标，但在功能点评审中，由于非功能点实体（负样本）的数量可能远多于正样本，我们将结合 F1 分数进行综合研判。

2.  **精确率 (Precision)**：
    反映了模型判定的“置信度”，即在模型判定为“是”的样本中，真正符合 IFPUG 规范的比例：
    $$ Precision = \frac{TP}{TP + FP} $$
    高精确率意味着模型具有较低的误报率（False Positive Rate），能够有效抑制将临时文件或中间数据误判为功能点的“幻觉”现象。

3.  **召回率 (Recall)**：
    衡量了模型对真实功能点的“覆盖度”，即所有真实存在的功能点中被模型成功识别的比例：
    $$ Recall = \frac{TP}{TP + FN} $$
    在软件造价评估场景下，召回率至关重要，因为遗漏任何关键数据实体都可能导致项目规模估算的显著偏差（Underestimation）。

4.  **F1 分数 (F1 Score)**：
    作为精确率与召回率的调和平均数，F1 分数惩罚了极端的不平衡情况，能够最公正地反映模型在权衡“不误报”与“不漏报”时的综合性能：
    $$ F1 = 2 \cdot \frac{Precision \cdot Recall}{Precision + Recall} $$

### 3.5.2 抽取任务评估与集合相似度 (Metrics for Extraction Tasks)

针对 **功能点抽取任务 (Selection Task)**，模型需要从非结构化需求文本中提取出一个功能点集合 $S_{pred}$。这属于集合检索（Set Retrieval）问题，不能简单应用二分类指标。其难点在于模型输出的文本描述可能与基准集合 $S_{truth}$ 存在字面差异。

我们定义功能点集合间的匹配函数 $Match(s_i, S_{truth})$，当 $s_i \in S_{truth}$ 时返回 1，否则为 0。在此基础上，指标定义如下：

*   **集合精确率 (Set Precision)**：
    $$ P_{set} = \frac{| \{ s \in S_{pred} \mid Match(s, S_{truth}) = 1 \} |}{| S_{pred} |} $$

*   **集合召回率 (Set Recall)**：
    $$ R_{set} = \frac{| \{ s \in S_{truth} \mid Match(s, S_{pred}) = 1 \} |}{| S_{truth} |} $$

其中 $|\cdot|$ 表示集合的基数（Cardinality）。

### 3.5.3 基于 LLM 的语义一致性校验 (LLM-based Semantic Alignment)

在传统的自动化软件工程评估中，匹配函数 $Match(\cdot)$ 通常依赖于严格的字符串匹配（Exact String Match）。然而，在 IFPUG 功能点识别中，这种刚性匹配面临巨大挑战。同一功能实体往往存在多义性表达（Polysemy）或同义异名（Synonymy）。例如，标准答案中的 "Employee Security Config" 在需求文档中可能被表述为“人员权限配置表”或“User Access Control”。

为了突破硬编码映射（Hard-coded Mapping）的局限性，我们设计并实现了一种**语义松弛匹配算法 (Semantic Relaxation Matching Algorithm)**。该算法将二元真值匹配转化为连续的语义距离度量。

#### 1. 语义相似度函数 (Semantic Similarity Function)
我们利用大语言模型作为语义裁判（Semantic Judge），定义相似度函数 $Sim(x, y) \rightarrow [0, 1]$。具体实现上，我们构建了如下的 Prompt 模板 $\mathcal{P}_{sim}$：

> "Assess whether the functional entity '$x$' and '$y$' refer to the same logical data group within the context of IFPUG analysis. Return a score between 0.0 and 1.0."

设模型对于输入对 $(x, y)$ 的输出为 $O_{sim}$，则 $Sim(x, y) = ParseFloat(O_{sim})$。

#### 2. 模糊匹配判据 (Fuzzy Matching Criterion)
我们引入指示函数 $\mathbb{I}_{match}$ 来判定两个条目是否匹配：

$$
\mathbb{I}_{match}(s_{pred}, s_{truth}) = 
\begin{cases} 
1 & \text{if } Levenshtein(s_{pred}, s_{truth}) = 0 \quad \text{(Exact Match)} \\
1 & \text{if } Sim(s_{pred}, s_{truth}) > \tau \quad \text{(Semantic Match)} \\
0 & \text{otherwise}
\end{cases}
$$

其中 $\tau$ 为置信度阈值，在本研究中，经过在验证集上的参数搜索，我们将 $\tau$ 设定为 **0.7**。这一阈值在过滤无关项与容忍表达差异之间取得了最佳平衡。

#### 3. 语义增强的 F1 (Semantic-Augmented F1)
基于上述模糊匹配判据，我们重新定义了“模糊分数 (Fuzzy Score)”作为有效匹配的累计值：
$$ Score_{fuzzy} = \sum_{s_p \in S_{pred}} \max_{s_t \in S_{truth}} ( \mathbb{I}_{match}(s_p, s_t) \cdot Sim(s_p, s_t) ) $$

进而修正精确率与召回率的计算：
$$ P_{sem} = \frac{Score_{fuzzy}}{|S_{pred}|}, \quad R_{sem} = \frac{Score_{fuzzy}}{|S_{truth}|} $$

这种混合评估机制不仅展现了比 N-gram 或 编辑距离等传统算法更高的鲁棒性，还有效解决了中英文跨语言环境下的自动化评估难题，确保了实验结果能够真实反映模型对业务逻辑的理解深度，而非仅仅是对特定词汇的记忆能力。
