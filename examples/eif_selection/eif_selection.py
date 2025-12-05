#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
功能点评估实验实现。
使用不同的提示工程方法（IO、COT、TOT、GOT）来从需求文档中选择和识别EIF功能点。
"""

import os
import logging
import datetime
import json
import csv
import re
from functools import partial, total_ordering
from typing import Dict, List, Callable, Union
from graph_of_thoughts import controller, language_models, operations, prompter, parser

# 全局配置：用于语义相似度判断的LLM实例
_GLOBAL_LM_FOR_SCORING = None
_USE_LLM_SEMANTIC = False  # 默认关闭（避免额外成本）

def set_scoring_lm(lm, use_semantic: bool = False):
    """
    设置用于评分的LLM实例。
    
    :param lm: 语言模型实例
    :type lm: language_models.AbstractLanguageModel
    :param use_semantic: 是否启用LLM语义相似度判断
    :type use_semantic: bool
    """
    global _GLOBAL_LM_FOR_SCORING, _USE_LLM_SEMANTIC
    _GLOBAL_LM_FOR_SCORING = lm
    _USE_LLM_SEMANTIC = use_semantic
    logging.info(f"Scoring LLM set, semantic matching: {use_semantic}")

def normalize_eif_name(name: str) -> str:
    """
    标准化EIF功能点名称，用于比较。
    
    :param name: EIF功能点名称
    :type name: str
    :return: 标准化后的名称
    :rtype: str
    """
    # 转小写
    name = name.lower().strip()
    # 去除多余空格
    name = ' '.join(name.split())
    # 去除括号内容
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'（[^）]*）', '', name)
    return name.strip()

def check_eif_semantic_similarity(name1: str, name2: str, lm=None, use_lm: bool = True) -> float:
    """
    使用LLM判断两个EIF功能点名称是否语义相同。
    
    :param name1: 第一个功能点名称
    :type name1: str
    :param name2: 第二个功能点名称
    :type name2: str
    :param lm: 语言模型实例（可选）
    :type lm: language_models.AbstractLanguageModel
    :param use_lm: 是否使用LLM进行语义判断
    :type use_lm: bool
    :return: 相似度分数 (0.0 - 1.0)
    :rtype: float
    """
    # 如果不使用LLM或LLM未提供，回退到字符串相似度
    if not use_lm or lm is None:
        return _string_similarity(name1, name2)
    
    # 使用LLM进行语义相似度判断
    prompt = f"""你是一个IFPUG功能点分析专家。请判断以下两个EIF（外部接口文件）功能点名称是否指代同一个功能点。

功能点1: {name1}
功能点2: {name2}

请分析：
1. 它们是否指代相同的外部数据源或接口？
2. 考虑中英文翻译、同义词、缩写等因素
3. 只要语义相同即可，不需要完全字面匹配

请直接回答相似度分数（0.0到1.0之间的小数）：
- 1.0: 完全相同的功能点
- 0.8-0.9: 高度相似，很可能是同一个功能点
- 0.5-0.7: 中等相似，可能相关
- 0.0-0.4: 不相似或不相关

只需要回答一个数字，格式：0.95"""

    try:
        # 使用query方法调用LLM
        query_response = lm.query(prompt, num_responses=1)
        # 提取响应文本
        response_texts = lm.get_response_texts(query_response)
        
        if response_texts and len(response_texts) > 0:
            # 提取数字
            text = response_texts[0].strip()
            logging.debug(f"LLM response for similarity check: '{text}'")
            match = re.search(r'(\d+\.?\d*)', text)
            if match:
                score = float(match.group(1))
                # 确保在0-1范围内
                score = max(0.0, min(1.0, score))
                logging.debug(f"LLM semantic similarity for '{name1}' vs '{name2}': {score}")
                return score
            else:
                logging.warning(f"Could not extract score from LLM response: '{text}'")
        else:
            logging.warning(f"Empty response from LLM for similarity check")
    except Exception as e:
        logging.warning(f"Error using LLM for semantic similarity: {e}")
    
    # 如果LLM调用失败，回退到字符串相似度
    fallback_score = _string_similarity(name1, name2)
    logging.warning(f"Falling back to string similarity for '{name1}' vs '{name2}': {fallback_score:.2f}")
    return fallback_score

def calculate_eif_similarity(predicted: List[str], ground_truth: List[str], lm=None, use_lm_semantic: bool = True) -> Dict:
    """
    计算预测的EIF功能点列表和真实答案的相似度。
    使用精确匹配、语义匹配（可选LLM）相结合的方法。
    
    :param predicted: 预测的EIF功能点列表
    :type predicted: List[str]
    :param ground_truth: 真实的EIF功能点列表
    :type ground_truth: List[str]
    :param lm: 语言模型实例（可选，用于语义相似度判断）
    :type lm: language_models.AbstractLanguageModel
    :param use_lm_semantic: 是否使用LLM进行语义相似度判断
    :type use_lm_semantic: bool
    :return: 包含相似度分数和详细指标的字典，包括 f1_score, precision, recall, exact_matches, fuzzy_score, semantic_matches
    :rtype: Dict
    """
    if not ground_truth and not predicted:
        # 都为空，完全匹配
        return {
            "f1_score": 1.0,
            "precision": 1.0,
            "recall": 1.0,
            "exact_matches": 0,
            "fuzzy_score": 0.0,
            "semantic_matches": []
        }
    if not ground_truth or not predicted:
        # 一个为空，一个不为空
        return {
            "f1_score": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "exact_matches": 0,
            "fuzzy_score": 0.0,
            "semantic_matches": []
        }
    
    # 标准化所有名称
    pred_normalized = [normalize_eif_name(p) for p in predicted]
    truth_normalized = [normalize_eif_name(t) for t in ground_truth]
    
    # 精确匹配
    pred_set = set(pred_normalized)
    truth_set = set(truth_normalized)
    
    exact_matches = len(pred_set & truth_set)
    
    # 语义/模糊匹配：对于没有精确匹配的项
    unmatched_pred = [(p, predicted[i]) for i, p in enumerate(pred_normalized) if p not in truth_set]
    unmatched_truth = [(t, ground_truth[i]) for i, t in enumerate(truth_normalized) if t not in pred_set]
    
    fuzzy_score = 0.0
    matched_truth = set()  # 存储已匹配的原始名称（而非标准化名称）
    match_details = []
    
    for pred_norm, pred_orig in unmatched_pred:
        max_similarity = 0.0
        best_match = None
        best_match_orig = None
        
        # 添加调试日志
        logging.debug(f"  Matching '{pred_orig}' against ground truth...")
        
        for truth_norm, truth_orig in unmatched_truth:
            # 使用原始名称判断是否已匹配（避免标准化后名称重复的问题）
            if truth_orig in matched_truth:
                continue
            
            # 首先尝试使用LLM进行语义相似度判断（如果启用）
            if use_lm_semantic and lm is not None:
                similarity = check_eif_semantic_similarity(pred_orig, truth_orig, lm, use_lm=True)
                logging.debug(f"    LLM similarity with '{truth_orig}': {similarity:.2f}")
            else:
                # 回退到字符串相似度
                similarity = _string_similarity(pred_norm, truth_norm)
                logging.debug(f"    String similarity with '{truth_orig}': {similarity:.2f}")
            
            if similarity > max_similarity:
                max_similarity = similarity
                best_match = truth_norm
                best_match_orig = truth_orig
        
        # 添加调试日志
        logging.debug(f"  Best match for '{pred_orig}': '{best_match_orig}' (score: {max_similarity:.2f})")
        
        # 如果相似度大于阈值，认为是部分匹配
        if max_similarity > 0.7 and best_match:  # 提高阈值到0.7（LLM更准确）
            fuzzy_score += max_similarity
            matched_truth.add(best_match_orig)  # 使用原始名称而非标准化名称
            match_details.append(f"{pred_orig} <-> {best_match_orig} ({max_similarity:.2f})")
            logging.info(f"  ✓ Matched: {pred_orig} <-> {best_match_orig} ({max_similarity:.2f})")
        else:
            logging.warning(f"  ✗ No match for '{pred_orig}' (best score: {max_similarity:.2f}, threshold: 0.7)")
    
    # 总分 = 精确匹配分数 + 模糊匹配分数
    total_matches = exact_matches + fuzzy_score
    
    # 使用F1-score的思想：同时考虑召回率和准确率
    precision = total_matches / len(predicted) if predicted else 0
    recall = total_matches / len(ground_truth) if ground_truth else 0
    
    if precision + recall == 0:
        f1_score = 0.0
    else:
        f1_score = 2 * (precision * recall) / (precision + recall)
    
    logging.info(f"EIF Similarity - Predicted: {predicted}, Truth: {ground_truth}")
    logging.info(f"  Exact matches: {exact_matches}, Fuzzy score: {fuzzy_score:.2f}")
    if match_details:
        logging.info(f"  Semantic matches: {', '.join(match_details)}")
    logging.info(f"  Precision: {precision:.2f}, Recall: {recall:.2f}, F1: {f1_score:.2f}")
    
    # 返回详细的评估结果
    return {
        "f1_score": f1_score,
        "precision": precision,
        "recall": recall,
        "exact_matches": exact_matches,
        "fuzzy_score": fuzzy_score,
        "semantic_matches": match_details
    }

def _string_similarity(s1: str, s2: str) -> float:
    """
    计算两个字符串的相似度（基于最长公共子序列）。
    
    :param s1: 字符串1
    :type s1: str
    :param s2: 字符串2
    :type s2: str
    :return: 相似度 (0.0 - 1.0)
    :rtype: float
    """
    if not s1 or not s2:
        return 0.0
    
    # 简单的基于集合的相似度（Jaccard）
    set1 = set(s1.split())
    set2 = set(s2.split())
    
    if not set1 or not set2:
        # 如果没有空格分隔，使用字符级别
        set1 = set(s1)
        set2 = set(s2)
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0

def test_eif_assessment(state: Dict) -> bool:
    """
    Function to test whether the final solution matches ground truth.
    支持使用LLM进行语义相似度判断。

    :param state: Thought state that represents the final solution.
    :type state: Dict
    :return: Returns whether the solution matches the ground truth.
    :rtype: bool
    """
    try:
        # 获取预测的EIF功能点列表
        if "final_answer" in state:
            prediction = state["final_answer"]  # 现在是列表
        else:
            # 向后兼容
            prediction = []
        
        ground_truth = state["ground_truth"]  # 现在也是列表
        
        # 使用全局LLM进行语义相似度判断
        similarity_result = calculate_eif_similarity(
            prediction, ground_truth,
            lm=_GLOBAL_LM_FOR_SCORING,
            use_lm_semantic=_USE_LLM_SEMANTIC
        )
        
        # 保存详细指标到state
        state["evaluation_metrics"] = similarity_result
        
        return similarity_result["f1_score"] >= 0.8
    except Exception as e:
        logging.error(f"Error in test_eif_assessment: {e}")
        return False

def score_assessment(state: Dict) -> float:
    """
    Function to locally score the assessment that serves as a score.
    使用EIF功能点列表的相似度作为分数。
    支持使用LLM进行语义相似度判断。

    :param state: Thought state to be scored.
    :type state: Dict
    :return: Score (0.0 to 1.0) based on EIF list similarity.
    :rtype: float
    """
    try:
        # 获取预测的EIF功能点列表
        if "final_answer" in state:
            prediction = state["final_answer"]  # 现在是列表
        else:
            # 向后兼容
            prediction = []
            
        ground_truth = state["ground_truth"]  # 现在也是列表
        
        # 使用全局LLM进行语义相似度判断
        similarity_result = calculate_eif_similarity(
            prediction, ground_truth,
            lm=_GLOBAL_LM_FOR_SCORING,
            use_lm_semantic=_USE_LLM_SEMANTIC
        )
        
        # 保存详细指标到state
        state["evaluation_metrics"] = similarity_result
        
        return similarity_result["f1_score"]
    except Exception as e:
        logging.error(f"Error in score_assessment: {e}")
        return 0.0

class FunctionPointPrompter(prompter.Prompter):
    """
    FunctionPointPrompter provides the generation of prompts specific to the
    function point assessment example for the language models.

    Inherits from the Prompter class and implements its abstract methods.
    """

    io_prompt = """你是一个IFPUG功能点分析专家。请分析给定的需求文档，识别出其中所有可能的外部接口文件（EIF）功能点。

[需求文档]
{requirement_text}

**【重要】请严格按照以下格式输出（必须使用方括号，功能点之间用逗号分隔）：**

EIF功能点列表：[功能点1, 功能点2, 功能点3]

如果没有EIF功能点，请输出：
EIF功能点列表：无"""

    cot_prompt = """你是一个IFPUG功能点分析专家。请分析给定的需求文档，识别出其中所有可能的外部接口文件（EIF）功能点。
请按照以下步骤进行分析：

1. 识别需求文档中提到的所有外部数据源/接口
2. 对每个外部数据源，判断是否逻辑上独立且用户可识别
3. 判断是否被当前应用引用，但物理/逻辑上存在于当前应用之外
4. 判断是否不由当前应用进行维护（即只读，不增删改）
5. 根据以上分析，列出所有满足EIF条件的功能点

[需求文档]
{requirement_text}

请按以下格式输出：
思考过程：
1. 识别的外部数据源：[列出所有外部数据源]
2. EIF条件分析：
   - 数据源1：[分析是否满足EIF条件]
   - 数据源2：[分析是否满足EIF条件]
   ...
3. 结论：[总结]

**【重要】请在最后一行严格按照以下格式输出（必须使用方括号，功能点之间用逗号分隔）：**

EIF功能点列表：[功能点1, 功能点2, 功能点3]

如果没有EIF功能点，请输出：
EIF功能点列表：无"""

    tot_prompt = """你是一个IFPUG功能点分析专家。请分析给定的需求文档，识别出其中所有可能的外部接口文件（EIF）功能点。

[需求文档]
{requirement_text}

请按以下方法进行分析：

1. 初步识别
   1.1 扫描文档，列出所有外部数据源/接口
   1.2 标注每个数据源的特征（来源、访问方式等）

2. 深入分析每个外部数据源
   2.1 数据组特征
       - 是否逻辑上独立
       - 用户是否可识别
   2.2 数据位置与访问方式
       - 是否存在于应用边界之外
       - 应用是否仅引用（读取）该数据，不进行维护

3. 反向验证
   3.1 检查是否有遗漏的外部数据源
   3.2 验证已识别的功能点是否真正满足EIF条件

4. 最终结论

**【重要】请在最后一行严格按照以下格式输出（必须使用方括号，功能点之间用逗号分隔）：**

EIF功能点列表：[功能点1, 功能点2, 功能点3]

如果没有EIF功能点，请输出：
EIF功能点列表：无"""

    got_prompt = """你是一个IFPUG功能点分析专家。请分析给定的需求文档，识别出其中所有可能的外部接口文件（EIF）功能点。

[需求文档]
{requirement_text}

请按以下步骤分析：

1. 需求分解
- 识别文档中提到的所有外部系统/数据源
- 分析当前应用如何访问这些外部数据
- 标注每个外部数据源的访问方式（只读/读写）

2. 多路径验证
路径1：从用户视角
- 哪些外部数据组用户可以识别
- 哪些外部数据对业务有价值

路径2：从系统视角
- 哪些数据存在于应用边界之外
- 哪些数据应用只引用（读取）不维护

路径3：从IFPUG规则视角
- 检查每个数据源是否符合EIF定义
- 验证是否满足所有必要条件（逻辑独立、外部存储、只读引用）

3. 结果合并
- 综合各路径结果
- 去除重复和不符合条件的
- 得出最终的EIF功能点列表

**【重要】请在最后一行严格按照以下格式输出（必须使用方括号，功能点之间用逗号分隔）：**

EIF功能点列表：[功能点1, 功能点2, 功能点3]

如果没有EIF功能点，请输出：
EIF功能点列表：无"""

    tot_improve_prompt = """你是一个IFPUG功能点分析专家。基于之前的分析结果进行改进：

之前识别的EIF功能点：{current}

[需求文档]
{requirement_text}

请基于之前的分析进行改进：
1. 分析之前识别的功能点是否准确
2. 检查是否有遗漏的EIF功能点
3. 检查是否有误判的非EIF功能点（例如内部数据或有写操作的数据）
4. 重新验证EIF的三个关键条件
5. 给出改进后的功能点列表

**【重要】请在最后一行严格按照以下格式输出（必须使用方括号，功能点之间用逗号分隔）：**

改进后的EIF功能点列表：[功能点1, 功能点2, 功能点3]

如果没有EIF功能点，请输出：
改进后的EIF功能点列表：无"""

    perspective_prompt = """你是一个IFPUG功能点分析专家。请从{perspective}分析需求文档，识别出所有可能的EIF功能点。

[需求文档]
{requirement_text}

[分析视角说明]
用户视角 - 关注：
- 哪些外部数据组逻辑上独立且用户可识别
- 哪些外部数据对业务有实际价值
- 用户是否能够理解这些外部数据的业务含义

系统视角 - 关注：
- 哪些数据存在于应用边界之外
- 应用如何访问这些外部数据（只读/读写）
- 哪些数据由外部系统维护，当前应用不进行增删改

IFPUG规则视角 - 关注：
- 哪些外部数据源满足EIF的所有必要条件（逻辑独立、外部存储、只读引用）
- 需要排除哪些不符合条件的候选项（内部数据、有写操作的数据）
- 是否符合IFPUG的最佳实践

[分析步骤]
1. 识别文档中提到的所有外部数据源/接口
2. 从该视角评估每个外部数据源
3. 列出符合EIF条件的功能点
4. 说明判断依据

[输出格式]
分析过程：
1. 识别的外部数据源：
   [列出所有外部数据源]

2. 从{perspective}评估：
   - 数据源1：[评估结果和理由]
   - 数据源2：[评估结果和理由]
   ...

3. 结论：
   [总结性分析]

**【重要】请在最后一行严格按照以下格式输出（必须使用方括号，功能点之间用逗号分隔）：**

该视角识别的EIF功能点：[功能点1, 功能点2, 功能点3]

如果没有EIF功能点，请输出：
该视角识别的EIF功能点：无"""

    merge_prompt = """你是一个IFPUG功能点分析专家。请综合以下三个视角的分析结果，得出最终的EIF功能点列表。

[需求文档]
{requirement_text}

[各视角分析结果]
用户视角分析：
{user_perspective}

系统视角分析：
{system_perspective}

IFPUG规则视角分析：
{ifpug_perspective}

[分析要求]
1. EIF必须同时满足以下所有条件：
   - 逻辑上独立且用户可识别的数据组
   - 被当前应用引用，但物理/逻辑上存在于当前应用之外
   - 不由当前应用进行维护（即只读，不增删改）

2. 需要排除的情况：
   - 数据由当前应用维护（有增删改操作）
   - 数据存储在应用边界内
   - 数据不是逻辑独立的
   - 不符合IFPUG规则的要求

请按以下步骤综合分析：
1. 汇总三个视角识别的所有功能点
2. 对每个功能点，检查三个视角的一致性
3. 去除重复项和明显不符合条件的项
4. 对有争议的功能点进行深入分析
5. 得出最终的EIF功能点列表

请输出：
1. 各视角关键发现：
   用户视角识别：[功能点列表]
   系统视角识别：[功能点列表]
   IFPUG规则视角识别：[功能点列表]

2. 一致性分析：
   - 三个视角都认同的：[功能点列表]
   - 两个视角认同的：[功能点列表及分析]
   - 仅一个视角认同的：[功能点列表及分析]

3. 争议功能点处理：
   [对有争议的功能点进行详细分析]

4. 综合结论：
   [总结性分析]

**【重要】请在最后一行严格按照以下格式输出（必须使用方括号，功能点之间用逗号分隔）：**

最终EIF功能点列表：[功能点1, 功能点2, 功能点3]

如果没有EIF功能点，请输出：
最终EIF功能点列表：无"""

    def generate_prompt(self, num_branches: int, current: str, method: str, **kwargs) -> str:
        """
        Generate a generate prompt for the language model.

        :param num_branches: The number of responses the prompt should ask the LM to generate.
        :type num_branches: int
        :param current: Intermediate solution.
        :type current: str
        :param method: Method for which the generate prompt is generated.
        :type method: str
        :param kwargs: Additional keyword arguments.
        :return: The generate prompt.
        :rtype: str
        :raise AssertionError: If the requested number of branches is not one.
        """
        assert num_branches == 1, "Branching should be done via multiple requests."
        
        # 添加调试日志
        logging.debug(f"Method: {method}")
        logging.debug(f"Current state: {kwargs}")
        
        if method.startswith("io"):
            return self.io_prompt.format(
                requirement_text=kwargs["requirement_text"]
            )
        elif method.startswith("cot"):
            return self.cot_prompt.format(
                requirement_text=kwargs["requirement_text"]
            )
        elif method.startswith("tot"):
            if current is None or current == "":
                return self.tot_prompt.format(
                    requirement_text=kwargs["requirement_text"]
                )
            return self.tot_improve_prompt.format(
                current=current,
                requirement_text=kwargs["requirement_text"]
            )
        elif method.startswith("got"):
            # 检查状态中的phase和perspective
            if "phase" in kwargs and kwargs["phase"] == "analysis" and "perspective" in kwargs:
                logging.debug(f"Using perspective prompt for {kwargs['perspective']}")
                return self.perspective_prompt.format(
                    perspective=kwargs["perspective"],
                    requirement_text=kwargs["requirement_text"]
                )
            elif "phase" in kwargs and kwargs["phase"] == "merge" and kwargs.get("merge_perspectives"):
                logging.debug("Using merge prompt")
                return self.merge_prompt.format(
                    requirement_text=kwargs["requirement_text"],
                    user_perspective=kwargs.get("user_perspective", ""),
                    system_perspective=kwargs.get("system_perspective", ""),
                    ifpug_perspective=kwargs.get("ifpug_perspective", "")
                )
            else:
                logging.debug("Using default got prompt")
                return self.got_prompt.format(
                    requirement_text=kwargs["requirement_text"]
                )

    def aggregation_prompt(self, state_dicts: List[Dict], **kwargs) -> str:
        """
        Generate an aggregation prompt for the language model.

        :param state_dicts: The thought states that should be aggregated.
        :type state_dicts: List[Dict]
        :param kwargs: Additional keyword arguments.
        :return: The aggregation prompt.
        :rtype: str
        """
        pass

    def improve_prompt(self, current: str, aggr1: str, aggr2: str, **kwargs) -> str:
        """
        Generate an improve prompt for the language model.

        :param current: Intermediate solution.
        :type current: str
        :param aggr1: Partially solution 1 before aggregation.
        :type aggr1: str
        :param aggr2: Partially solution 2 before aggregation.
        :type aggr2: str
        :param kwargs: Additional keyword arguments.
        :return: The improve prompt.
        :rtype: str
        """
        pass

    def validation_prompt(self, **kwargs) -> str:
        """
        Generate a validation prompt for the language model.

        :param kwargs: Additional keyword arguments.
        :return: The validation prompt.
        :rtype: str
        """
        pass

    def score_prompt(self, state_dicts: List[Dict], **kwargs) -> str:
        """
        Generate a score prompt for the language model.

        :param state_dicts: The thought states that should be scored,
                            if more than one, they should be scored together.
        :type state_dicts: List[Dict]
        :param kwargs: Additional keyword arguments.
        :return: The score prompt.
        :rtype: str
        """
        pass

class FunctionPointParser(parser.Parser):
    """
    FunctionPointParser provides the parsing of language model responses specific to the
    function point assessment example.

    Inherits from the Parser class and implements its abstract methods.
    """

    def extract_answer(self, text: str) -> List[str]:
        """
        从文本中提取EIF功能点列表。

        :param text: 包含答案的文本
        :type text: str
        :return: 提取出的EIF功能点列表
        :rtype: List[str]
        """
        logging.info(f"Extracting EIF from text (length: {len(text) if text else 0})")
        
        if not text:
            logging.warning("Empty text received for extraction")
            return []
        
        text = text.strip()
        
        # 特殊处理：如果是长文本（可能是完整的分析报告），优先查找最终结论
        if len(text) > 500:
            logging.info("Long text detected, searching for final conclusion markers")
            
            # 优先匹配带星号加粗的最终结论
            final_patterns = [
                r'\*\*最终EIF功能点列表\*\*[：:]\s*\[([^\]]+)\]',
                r'\*\*最终EIF功能点列表\*\*[：:]\s*([^\n]+)',
                r'最终EIF功能点列表[：:]\s*\[([^\]]+)\]',
                r'最终EIF功能点列表[：:]\s*([^\n]+)',
                r'最终.*?功能点.*?列表[：:]\s*\[([^\]]+)\]',
                r'\*?\*?EIF功能点列表\*?\*?[：:]\s*\[([^\]]+)\]',  # 支持 **EIF功能点列表**：[...]
                r'EIF功能点列表[：:]\s*([^\n]+)',  # 添加：支持无方括号格式
            ]
            
            for pattern in final_patterns:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    eif_text = match.group(1).strip()
                    logging.info(f"Found final conclusion with pattern: {pattern}")
                    # 检查是否为"无"
                    if eif_text in ["无", "无。", "None", "none"]:
                        logging.info(f"Detected '无' in final conclusion, returning empty list")
                        return []
                    eif_list = [self._clean_eif_name(item.strip()) for item in re.split(r'[,，、;；]', eif_text)]
                    eif_list = [item for item in eif_list if item and len(item) < 50]
                    if eif_list:
                        logging.info(f"Extracted EIF from final conclusion: {eif_list}")
                        return eif_list
            
            # 如果没找到"最终"标记，在文本末尾（最后 500 字符）查找列表格式
            text_tail = text[-500:]
            # 查找最后出现的列表格式（优先查找方括号格式）
            match = re.search(r'\[([A-Z][A-Z_,\s]+)\](?!.*\[)', text_tail, re.DOTALL)
            if match:
                eif_text = match.group(1).strip()
                logging.info("Found list in text tail")
                eif_list = [self._clean_eif_name(item.strip()) for item in eif_text.split(',')]
                eif_list = [item for item in eif_list if item and len(item) < 50]
                if eif_list:
                    logging.info(f"Extracted EIF from text tail: {eif_list}")
                    return eif_list
        
        # 首先尝试匹配带编号的列表格式（在"EIF功能点列表"标题后）
        # 格式：**EIF功能点列表：**\n1. **NAME** - 描述
        eif_list_match = re.search(r'EIF功能点列表[：:]\s*\*?\*?\s*\n((?:\d+\.\s*\*\*[^\*]+\*\*[^\n]*\n?)+)', text, re.DOTALL)
        if eif_list_match:
            list_section = eif_list_match.group(1)
            logging.info(f"Found numbered list section after EIF功能点列表")
            # 提取所有加粗的功能点名称
            pattern = r'\d+\.\s*\*\*([A-Z][A-Za-z_\s]+)\*\*'
            matches = re.findall(pattern, list_section)
            if matches:
                eif_list = [self._clean_eif_name(m.strip()) for m in matches]
                eif_list = [item for item in eif_list if item and 2 < len(item) < 50]
                if eif_list:
                    logging.info(f"Extracted EIF from numbered list after title: {eif_list}")
                    return eif_list
        
        # 尝试不同的答案格式模式（按优先级排序）
        patterns = [
            r'最终EIF功能点列表[：:]\s*\[([^\]]+)\]',
            r'最终EIF功能点列表[：:]\s*([^\n（]+)',
            r'改进后的EIF功能点列表[：:]\s*\[([^\]]+)\]',
            r'改进后的EIF功能点列表[：:]\s*([^\n（]+)',
            r'该视角识别的EIF功能点[：:]\s*\[([^\]]+)\]',
            r'该视角识别的EIF功能点[：:]\s*([^\n（]+)',
            r'\*?\*?EIF功能点列表\*?\*?[：:]\s*\[([^\]]+)\]',  # 支持 **EIF功能点列表**：[...]
            r'EIF功能点列表[：:]\s*\[([^\]]+)\]',
            r'EIF功能点列表[：:]\s*([^\n（]+)',  # 添加：支持无方括号格式（如"EIF功能点列表：无"）
            r'功能点如下[：:]\s*([^\n]+)',
            r'功能点[：:]\s*([^\n（]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                answer_text = match.group(1).strip()
                # 检查是否为"无"或空 - 如果是，直接返回空列表
                if answer_text in ["无", "无。", "None", "none"]:
                    logging.info(f"Detected '无' (no EIF), returning empty list")
                    return []
                # 检查是否只是格式标记（如 ** 等）
                if answer_text in ["", "**", "*"]:
                    continue  # 继续尝试其他模式
                # 分割功能点（按逗号、顿号或分号）
                eif_list = re.split(r'[,，、;；]', answer_text)
                # 清理每个功能点的空白字符和编号
                eif_list = [self._clean_eif_name(item.strip()) for item in eif_list if item.strip()]
                # 过滤掉明显不是功能点的项
                eif_list = [item for item in eif_list if item and len(item) > 0]
                if eif_list:
                    logging.info(f"Extracted EIF list: {eif_list}")
                    return eif_list
        
        # 如果没有找到标准格式，尝试简单场景：整个回答就是逗号分隔的功能点
        logging.warning(f"No standard EIF list format found, trying simple comma-separated extraction")
        
        # 去掉明显的描述性文字
        cleaned_text = re.sub(r'根据.*?如下[：:]?\s*', '', text)
        cleaned_text = re.sub(r'识别出.*?如下[：:]?\s*', '', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        # 检查是否为"无"
        if cleaned_text.lower() in ["无", "none", ""]:
            return []
        
        # 尝试按逗号分割（不按换行符分割，避免将整个文档切碎）
        if ',' in cleaned_text or '，' in cleaned_text:
            eif_list = re.split(r'[,，、;；]', cleaned_text)
            eif_list = [self._clean_eif_name(item.strip()) for item in eif_list if item.strip()]
            # 过滤掉太长的描述性文本（可能不是功能点名称）
            eif_list = [item for item in eif_list if item and len(item) < 50 and len(item) > 0]
            if eif_list:
                logging.info(f"Extracted EIF list (simple mode): {eif_list}")
                return eif_list
        
        # 如果只有一个词或短语，直接当作功能点
        if len(cleaned_text) < 50 and len(cleaned_text) > 0:
            eif_name = self._clean_eif_name(cleaned_text)
            if eif_name:
                logging.info(f"Extracted single EIF: [{eif_name}]")
                return [eif_name]
        
        # 尝试识别带编号和加粗的列表格式
        # 格式1：1. **JOB** - 描述  或  **JOB** - 描述（全大写或混合大小写）
        # 格式2：1. JOB - 描述（无加粗）
        logging.warning(f"Trying numbered/bold list extraction")
        
        # 先尝试加粗格式（优先）- 匹配大写字母或首字母大写+空格的组合
        # 例如：**EMPLOYEE SECURITY** 或 **Employee Security**
        # 改用贪婪匹配，确保能匹配完整的名称
        pattern = r'\d+\.\s*\*\*([A-Z][A-Za-z_\s]+)\*\*\s*[-–—]'
        matches = re.findall(pattern, text)
        if matches:
            eif_list = [self._clean_eif_name(m.strip()) for m in matches]
            # 过滤掉明显不是功能点的（太短或包含"列表"等关键词）
            # 注意：不要过滤掉纯英文的功能点名称，只过滤包含"列表"、"功能点"这类元信息的
            eif_list = [item for item in eif_list if item and 2 < len(item) < 50 and '列表' not in item and '功能点' not in item]
            if eif_list:
                logging.info(f"Extracted EIF from bold list: {eif_list}")
                return eif_list
        
        # 如果没找到，尝试无加粗的编号列表（在"EIF功能点列表"之后）
        eif_section = re.search(r'EIF功能点列表[：:](.*?)(?=\n\n|\Z)', text, re.DOTALL)
        if eif_section:
            section_text = eif_section.group(1)
            # 匹配：1. JOB - 描述  或  1. JOB（不带描述）
            pattern = r'\d+\.\s*([A-Z][A-Z_\s]+?)(?:\s*[-–—]|\s*\n|$)'
            matches = re.findall(pattern, section_text)
            if matches:
                eif_list = [self._clean_eif_name(m.strip()) for m in matches]
                eif_list = [item for item in eif_list if item and len(item) > 0 and len(item) < 50]
                if eif_list:
                    logging.info(f"Extracted EIF from numbered list: {eif_list}")
                    return eif_list
        
        # 如果完全没有找到，返回空列表
        logging.warning(f"No EIF list found in text: {text[:200]}...")
        return []
    
    def _clean_eif_name(self, name: str) -> str:
        """
        清理EIF功能点名称，去除编号、多余空格等。
        
        :param name: 原始功能点名称
        :type name: str
        :return: 清理后的名称
        :rtype: str
        """
        # 去除开头的编号（如 "1. "、"- "、"• " 等）
        name = re.sub(r'^\d+[\.\)、]\s*', '', name)
        name = re.sub(r'^[-•·]\s*', '', name)
        # 去除方括号
        name = re.sub(r'[\[\]]', '', name)
        # 去除多余空格
        name = ' '.join(name.split())
        return name

    def parse_generate_answer(self, state: Dict, texts: List[str]) -> List[Dict]:
        """
        Parse the response from the language model for a generate prompt.

        :param state: The thought state used to generate the prompt.
        :type state: Dict
        :param texts: The responses to the prompt from the language model.
        :type texts: List[str]
        :return: The new thought states after parsing the responses from the language model.
        :rtype: List[Dict]
        """
        new_states = []
        for text in texts:
            try:
                new_state = state.copy()
                
                # 保存原始回答
                new_state["current"] = text
                
                # 提取EIF功能点列表
                answer = self.extract_answer(text)
                new_state["final_answer"] = answer  # 现在是一个列表
                
                # 根据不同阶段存储分析结果
                if "perspective" in state:
                    # 视角分析阶段
                    perspective = state["perspective"]
                    new_state[f"{perspective}_analysis"] = text
                    # 将分析结果也存储到合并阶段会用到的键中
                    if perspective == "用户视角":
                        new_state["user_perspective"] = text
                    elif perspective == "系统视角":
                        new_state["system_perspective"] = text
                    elif perspective == "IFPUG规则视角":
                        new_state["ifpug_perspective"] = text
                elif "merge_perspectives" in state:
                    # 合并阶段
                    new_state["merged_analysis"] = text
                
                new_states.append(new_state)
            except Exception as e:
                logging.error(f"Could not parse answer: {text}. Error: {e}")
                # 发生错误时添加一个默认状态
                default_state = state.copy()
                default_state["current"] = text
                default_state["final_answer"] = []  # 默认为空列表
                default_state["parse_error"] = str(e)
                new_states.append(default_state)
        return new_states

    def parse_aggregation_answer(self, states: List[Dict], texts: List[str]) -> Union[Dict, List[Dict]]:
        """
        Parse the response from the language model for an aggregation prompt.

        :param states: The thought states used to generate the prompt.
        :type states: List[Dict]
        :param texts: The responses to the prompt from the language model.
        :type texts: List[str]
        :return: The new thought states after parsing the respones from the language model.
        :rtype: Union[Dict, List[Dict]]
        """
        pass

    def parse_improve_answer(self, state: Dict, texts: List[str]) -> Dict:
        """
        Parse the response from the language model for an improve prompt.

        :param state: The thought state used to generate the prompt.
        :type state: Dict
        :param texts: The responses to the prompt from the language model.
        :type texts: List[str]
        :return: The new thought state after parsing the responses from the language model.
        :rtype: Dict
        """
        pass

    def parse_validation_answer(self, state: Dict, texts: List[str]) -> bool:
        """
        Parse the response from the language model for a validation prompt.

        :param state: The thought state used to generate the prompt.
        :type state: Dict
        :param texts: The responses to the prompt from the language model.
        :type texts: List[str]
        :return: Whether the thought state is valid or not.
        :rtype: bool
        """
        pass

    def parse_score_answer(self, states: List[Dict], texts: List[str]) -> List[float]:
        """
        Parse the response from the language model for a score prompt.

        :param states: The thought states used to generate the prompt.
        :type states: List[Dict]
        :param texts: The responses to the prompt from the language model.
        :type texts: List[str]
        :return: The scores for the thought states.
        :rtype: List[float]
        """
        pass

def io() -> operations.GraphOfOperations:
    """
    Generates the Graph of Operations for the IO method.

    :return: Graph of Operations
    :rtype: GraphOfOperations
    """
    operations_graph = operations.GraphOfOperations()

    operations_graph.append_operation(operations.Generate(1, 1))
    operations_graph.append_operation(operations.Score(1, False, score_assessment))
    operations_graph.append_operation(operations.GroundTruth(test_eif_assessment))

    return operations_graph

def cot() -> operations.GraphOfOperations:
    """
    Generates the Graph of Operations for the CoT method.

    :return: Graph of Operations
    :rtype: GraphOfOperations
    """
    operations_graph = operations.GraphOfOperations()

    operations_graph.append_operation(operations.Generate(1, 1))
    operations_graph.append_operation(operations.Score(1, False, score_assessment))
    operations_graph.append_operation(operations.GroundTruth(test_eif_assessment))

    return operations_graph

def tot() -> operations.GraphOfOperations:
    """
    Generates the Graph of Operations for the ToT method.

    :return: Graph of Operations
    :rtype: GraphOfOperations
    """
    operations_graph = operations.GraphOfOperations()

    # 目前有问题，deepseek不支持试用参数n生成多个回复choices
    operations_graph.append_operation(operations.Generate(1, 1))
    operations_graph.append_operation(operations.Score(1, False, score_assessment))
    keep_best_1 = operations.KeepBestN(1, True)  # True: 选择最高分数
    operations_graph.append_operation(keep_best_1)

    for _ in range(3):
        operations_graph.append_operation(operations.Generate(1, 1))
        operations_graph.append_operation(operations.Score(1, False, score_assessment))
        keep_best_2 = operations.KeepBestN(1, True)  # True: 选择最高分数
        keep_best_2.add_predecessor(keep_best_1)
        operations_graph.append_operation(keep_best_2)
        keep_best_1 = keep_best_2

    operations_graph.append_operation(operations.KeepBestN(1, True))  # True: 选择最高分数
    operations_graph.append_operation(operations.GroundTruth(test_eif_assessment))

    return operations_graph

def got() -> operations.GraphOfOperations:
    """
    Generates the Graph of Operations for the GoT method.
    使用图结构来分析EIF判断问题：
    1. 从三个不同视角分析（用户视角、系统视角、IFPUG规则视角）
    2. 每个视角生成多个思路并选择最佳
    3. 合并和验证结果
    """
    operations_graph = operations.GraphOfOperations()

    # 1. 从三个不同视角进行分析
    perspectives = ["用户视角", "系统视角", "IFPUG规则视角"]
    perspective_results = []
    
    for perspective in perspectives:
        # 1.1 生成该视角的分析
        generate = operations.Generate(1, 1)
        # 将视角信息添加到初始状态中
        generate.initial_state = {
            "perspective": perspective,
            "phase": "analysis"
        }
        operations_graph.add_operation(generate)

        # 1.2 评分
        score = operations.Score(1, False, score_assessment)
        score.add_predecessor(generate)
        operations_graph.add_operation(score)
        
        # 1.3 保留最佳结果
        keep_best = operations.KeepBestN(1, True)
        keep_best.add_predecessor(score)
        operations_graph.add_operation(keep_best)
        
        perspective_results.append(keep_best)

    # 2. 合并三个视角的结果
    merge = operations.Generate(1, 1)
    # 设置合并阶段的状态
    merge.initial_state = {
        "phase": "merge",
        "merge_perspectives": True
    }
    for result in perspective_results:
        merge.add_predecessor(result)
    operations_graph.add_operation(merge)

    # 3. 评分和选择最终结果
    final_score = operations.Score(1, False, score_assessment)
    final_score.add_predecessor(merge)
    operations_graph.add_operation(final_score)

    final_keep = operations.KeepBestN(1, True)
    final_keep.add_predecessor(final_score)
    operations_graph.add_operation(final_keep)

    # 4. 验证
    operations_graph.append_operation(operations.GroundTruth(test_eif_assessment))

    return operations_graph

def run(data_ids: List[int], methods: List[Callable[[], operations.GraphOfOperations]], budget: float, lm_name: str) -> float:
    """
    Controller function that executes each specified method for each specified
    sample while the budget is not exhausted.

    :param data_ids: Indices of the sample to be run.
    :type data_ids: List[int]
    :param methods: List of functions to generate Graphs of Operations.
    :type methods: Each function generates a Graph of Operation.
    :param budget: Language model budget for the execution in dollars.
    :type budget: float
    :param lm_name: Name of the language model to be used.
    :type lm_name: str
    :return: Spent budget in dollars.
    :rtype: float
    """
    orig_budget = budget
    data_path = os.path.join(os.path.dirname(__file__), "eif_selection.csv")
    data = []
    with open(data_path, "r", encoding="gbk") as f:  # 使用 GBK 编码（文件实际编码）
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            # 新格式: doc_id, true_eif, requirement_text
            # true_eif 是逗号分隔的EIF功能点列表
            doc_id = int(row[0])
            true_eif_str = row[1].strip()
            requirement_text = row[2]
            
            # 将true_eif字符串解析为列表
            if true_eif_str and true_eif_str.lower() not in ["无", "none", ""]:
                true_eif_list = [item.strip() for item in re.split(r'[,，]', true_eif_str) if item.strip()]
            else:
                true_eif_list = []
            
            # 注意：data结构为 [doc_id, true_eif_list, requirement_text]
            # 这样data[1]就是功能点列表，data[2]就是需求文档
            data.append([doc_id, true_eif_list, requirement_text])

    if data_ids is None or len(data_ids) == 0:
        data_ids = list(range(len(data)))
    selected_data = [data[i] for i in data_ids]

    results_dir = os.path.join(os.path.dirname(__file__), "results")

    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    extra_info = f"{lm_name}_{'-'.join([method.__name__ for method in methods])}"
    folder_name = f"{extra_info}_{timestamp}"
    results_folder = os.path.join(results_dir, folder_name)
    os.makedirs(results_folder)

    config = {
        "data": selected_data,
        "methods": [method.__name__ for method in methods],
        "lm": lm_name,
        "budget": budget,
    }
    with open(os.path.join(results_folder, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    logging.basicConfig(
        filename=os.path.join(results_folder, "log.log"),
        filemode="w",
        format="%(name)s - %(levelname)s - %(message)s",
        level=logging.DEBUG,
        encoding="utf-8"
    )

    for method in methods:
        # create a results directory for the method
        os.makedirs(os.path.join(results_folder, method.__name__))

    for data in selected_data:
        logging.info(f"Running data {data[0]}: Ground truth EIF count {len(data[1])}, Requirement text length {len(data[2])}")
        if budget <= 0.0:
            logging.error(f"Budget has been depleted, stopping. Data {data[0]} has not been run.")
            break
        for method in methods:
            logging.info(f"Running method {method.__name__}")
            logging.info(f"Budget left: {budget}")
            if budget <= 0.0:
                logging.error(f"Budget has been depleted, stopping. Method {method.__name__} has not been run.")
                break

            lm = language_models.ChatGPT(
                os.path.join(
                    os.path.dirname(__file__),
                    "../../graph_of_thoughts/language_models/config.json",
                ),
                model_name=lm_name,
                cache=True,
            )
            
            # 设置用于评分的LLM（可选启用语义相似度判断）
            # 注意：启用会增加API调用成本，建议在评估阶段使用
            use_semantic = True  # 设置为True启用LLM语义相似度判断
            set_scoring_lm(lm, use_semantic=use_semantic)
            
            operations_graph = method()
            executor = controller.Controller(
                lm,
                operations_graph,
                FunctionPointPrompter(),
                FunctionPointParser(),
                {
                    "requirement_text": data[2],  # 需求文档 (data[1])
                    "ground_truth": data[1],  # EIF功能点列表 (data[2])
                    "current": "",
                    "method": method.__name__,
                },
            )
            try:
                executor.run()
            except Exception as e:
                logging.error(f"Exception: {e}")
            path = os.path.join(
                results_folder,
                method.__name__,
                f"{data[0]}.json",
            )
            executor.output_graph(path)
            budget -= lm.cost

    return orig_budget - budget

if __name__ == "__main__":
    """
    Input (x)   : 需求文档
    Output (y)  : EIF功能点列表
    Correct     : 计算预测列表和真实列表的相似度
    Input Example:
        需求文档：人力资源管理系统 - 职位信息管理模块...
    Output Example:
        [Job information, Employee information]
    """
    # 设置控制台日志输出
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),  # 控制台输出
            logging.FileHandler('experiment.log', encoding='utf-8')  # 文件输出
        ]
    )
    
    print("🚀 开始运行EIF功能点分析实验...")
    print("=" * 50)
    
    budget = 5
    samples = [0,1,2,3,4,5]  # 使用前两个样本进行测试
    approaches = [got]  # 先用简单方法测试

    print(f"📊 实验配置:")
    print(f"   - 预算: ${budget}")
    print(f"   - 样本数量: {len(samples)}")
    print(f"   - 方法: {[method.__name__ for method in approaches]}")
    print(f"   - 模型: r1-7b")
    print("=" * 50)


    spent = run(samples, approaches, budget, "qwen3-30b")

    print("=" * 50)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
    print(f"✅ 实验完成！")
    print(f"💰 花费: ${spent:.2f} / ${budget}")
    print(f"📁 结果保存在: results/ 目录")
    logging.info(f"Spent {spent} out of {budget} budget.") 