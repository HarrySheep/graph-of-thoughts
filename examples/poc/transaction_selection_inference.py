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
    Inference mode: Returns 1.0 to bypass ground truth check.
    """
    return 1.0

class FunctionPointPrompter(prompter.Prompter):
    """
    FunctionPointPrompter provides the generation of prompts specific to the
    function point assessment example for the language models.

    Inherits from the Prompter class and implements its abstract methods.
    """

    ei_got_prompt = """你是一个IFPUG功能点分析专家。请分析给定的需求文档，识别出其中所有可能的外部输入（EI）功能点。

[需求文档]
{requirement_text}

请按以下步骤分析：

1. 需求分解
- 识别文档中所有输入数据的场景
- 分析数据是否跨越应用边界进入系统
- 判断数据是用于维护ILF还是提供控制信息

2. 多路径验证
路径1：从用户视角
- 哪些业务操作涉及向系统输入数据
- 哪些输入对业务有独立的意义
- 用户是否可以识别这些输入

路径2：从系统视角
- 哪些输入会触发后台处理
- 哪些输入会更新内部数据（ILF）
- 哪些输入提供了控制指令

路径3：从IFPUG规则视角
- 检查是否满足EI定义（数据穿越边界进入、维护ILF或控制）
- 排除重复的或不完整的输入
- 确保输入是基本处理过程

3. 结果合并
- 综合各路径结果
- 去除重复和不符合条件的
- 得出最终的EI功能点列表

**【重要】请在最后一行严格按照以下格式输出（必须使用方括号，功能点之间用逗号分隔）：**

EI功能点列表：[功能点1, 功能点2, 功能点3]

如果没有EI功能点，请输出：
EI功能点列表：无"""

    eo_got_prompt = """你是一个IFPUG功能点分析专家。请分析给定的需求文档，识别出其中所有可能的外部输出（EO）功能点。

[需求文档]
{requirement_text}

请按以下步骤分析：

1. 需求分解
- 识别文档中所有输出数据的场景
- 分析数据是否跨越应用边界离开系统
- 判断输出是否经过计算、推导或更新了ILF

2. 多路径验证
路径1：从用户视角
- 哪些报表、通知或查询结果包含计算逻辑
- 哪些输出对业务有独立的意义
- 用户识别到的输出有哪些

路径2：从系统视角
- 哪些输出涉及数学运算或导出数据
- 哪些输出改变了系统状态（更新ILF）
- 区分简单的检索（EQ）和复杂的输出（EO）

路径3：从IFPUG规则视角
- 检查是否满足EO定义（数据穿越边界离开、包含计算/推导/ILF维护）
- 排除简单的直接检索（EQ）
- 确保输出是基本处理过程

3. 结果合并
- 综合各路径结果
- 去除重复和不符合条件的
- 得出最终的EO功能点列表

**【重要】请在最后一行严格按照以下格式输出（必须使用方括号，功能点之间用逗号分隔）：**

EO功能点列表：[功能点1, 功能点2, 功能点3]

如果没有EO功能点，请输出：
EO功能点列表：无"""

    eq_got_prompt = """你是一个IFPUG功能点分析专家。请分析给定的需求文档，识别出其中所有可能的外部查询（EQ）功能点。

[需求文档]
{requirement_text}

请按以下步骤分析：

1. 需求分解
- 识别文档中所有数据检索/查看的场景
- 分析数据是否跨越应用边界离开系统
- 确认处理逻辑是否仅为简单的检索（无复杂计算）

2. 多路径验证
路径1：从用户视角
- 哪些查询操作仅用于查看数据
- 哪些查询结果是直接从ILF/EIF提取的
- 用户识别到的查询有哪些

路径2：从系统视角
- 哪些输出不涉及内部数据的修改
- 哪些输出不包含复杂的数学运算或派生数据
- 区分EQ（简单检索）和EO（复杂输出）

路径3：从IFPUG规则视角
- 检查是否满足EQ定义（输入+输出组合、数据检索、不更新ILF、无派生数据）
- 确保查询是独立且用户可识别的

3. 结果合并
- 综合各路径结果
- 去除重复和不符合条件的
- 得出最终的EQ功能点列表

**【重要】请在最后一行严格按照以下格式输出（必须使用方括号，功能点之间用逗号分隔）：**

EQ功能点列表：[功能点1, 功能点2, 功能点3]

如果没有EQ功能点，请输出：
EQ功能点列表：无"""

    def generate_prompt(self, num_branches: int, current: str, method: str, **kwargs) -> str:
        """
        Generate a generate prompt for the language model.
        """
        assert num_branches == 1, "Branching should be done via multiple requests."
        
        logging.debug(f"Method: {method}")
        logging.debug(f"Current state: {kwargs}")
        
        function_type = kwargs.get("function_type", "EI") # Default to EI if not specified
        
        # Support for CoT/IO/ToT which don't use the 'got' prefix check in the original logic but rely on fallthrough or specific handling
        if method.startswith("got") or method.startswith("cot") or method.startswith("io") or method.startswith("tot"):
            if "phase" in kwargs and kwargs["phase"] == "merge":
                # Ensure merge prompt matches function type if needed, or use generic one
                # For simplicity, using one generic merge prompt but injecting function_type could be better
                # But here we will just return the specific GOT prompt for the type if not in specific sub-phases
                # Wait, merge needs the perspectives. Providing a generic merge logic for now.
                 return self.merge_prompt.format(
                    requirement_text=kwargs["requirement_text"],
                    user_perspective=kwargs.get("user_perspective", ""),
                    system_perspective=kwargs.get("system_perspective", ""),
                    ifpug_perspective=kwargs.get("ifpug_perspective", "")
                ).replace("EIF", function_type) # Simple string replacement to adapt prompt
            
            elif "phase" in kwargs and kwargs["phase"] == "analysis":
                 return self.perspective_prompt.format(
                    perspective=kwargs["perspective"],
                    requirement_text=kwargs["requirement_text"]
                ).replace("EIF", function_type)

            else:
                # Top level GOT prompt
                if function_type == "EI":
                    return self.ei_got_prompt.format(requirement_text=kwargs["requirement_text"])
                elif function_type == "EO":
                    return self.eo_got_prompt.format(requirement_text=kwargs["requirement_text"])
                elif function_type == "EQ":
                    return self.eq_got_prompt.format(requirement_text=kwargs["requirement_text"])
                else:
                    return self.got_prompt.format(requirement_text=kwargs["requirement_text"]) # Fallback to EIF/Original

        return ""

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
        从文本中提取功能点列表 (Generic for EI/EO/EQ/EIF/ILF).

        :param text: 包含答案的文本
        :type text: str
        :return: 提取出的功能点列表
        :rtype: List[str]
        """
        logging.info(f"Extracting Function Points from text (length: {len(text) if text else 0})")
        
        if not text:
            logging.warning("Empty text received for extraction")
            return []
        
        text = text.strip()
        
        # Generic patterns for diverse types
        final_patterns = [
            r'\*\*最终[A-Z]*功能点列表\*\*[：:]\s*\[([^\]]+)\]',
            r'\*\*最终[A-Z]*功能点列表\*\*[：:]\s*([^\n]+)',
            r'最终[A-Z]*功能点列表[：:]\s*\[([^\]]+)\]',
            r'最终[A-Z]*功能点列表[：:]\s*([^\n]+)',
            r'最终.*?功能点.*?列表[：:]\s*\[([^\]]+)\]',
            r'\*?\*?[A-Z]*功能点列表\*?\*?[：:]\s*\[([^\]]+)\]',  
            r'[A-Z]*功能点列表[：:]\s*([^\n]+)',
            r'[A-Z]*功能点列表[：:]\s*\[([^\]]+)\]',
        ]

        if len(text) > 500:
             logging.info("Long text detected, searching for final conclusion markers")
             for pattern in final_patterns:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    fp_text = match.group(1).strip()
                    logging.info(f"Found final conclusion with pattern: {pattern}")
                    # Check for "None"
                    if fp_text in ["无", "无。", "None", "none"]:
                        logging.info(f"Detected '无' in final conclusion, returning empty list")
                        return []
                    fp_list = [self._clean_name(item.strip()) for item in re.split(r'[,，、;；]', fp_text)]
                    fp_list = [item for item in fp_list if item and len(item) < 80] # Increased len limit slightly
                    if fp_list:
                         logging.info(f"Extracted FP from final conclusion: {fp_list}")
                         return fp_list

        
        # Fallback to patterns
        for pattern in final_patterns:
            match = re.search(pattern, text)
            if match:
                answer_text = match.group(1).strip()
                if answer_text in ["无", "无。", "None", "none"]:
                     return []
                if answer_text in ["", "**", "*"]:
                     continue
                fp_list = re.split(r'[,，、;；]', answer_text)
                fp_list = [self._clean_name(item.strip()) for item in fp_list if item.strip()]
                if fp_list:
                    logging.info(f"Extracted FP list: {fp_list}")
                    return fp_list

        # Attempt numbered list extraction
        pattern_list = r'\d+\.\s*\*\*([A-Z][A-Za-z_\s]+)\*\*'
        matches = re.findall(pattern_list, text)
        if matches:
             fp_list = [self._clean_name(m.strip()) for m in matches]
             fp_list = [item for item in fp_list if item and 2 < len(item) < 80 and '列表' not in item]
             if fp_list:
                 logging.info(f"Extracted FP from bold list: {fp_list}")
                 return fp_list
                 
        return []

    def _clean_name(self, name: str) -> str:
        """
        清理功能点名称。
        """
        name = re.sub(r'^\d+[\.\)、]\s*', '', name)
        name = re.sub(r'^[-•·]\s*', '', name)
        name = re.sub(r'[\[\]]', '', name)
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
    # operations_graph.append_operation(operations.GroundTruth(test_eif_assessment)) # Inference mode

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

    # 4. 验证 - Inference mode: No ground truth check
    # operations_graph.append_operation(operations.GroundTruth(test_eif_assessment))

    return operations_graph

def got_ei() -> operations.GraphOfOperations: return got()
def got_eo() -> operations.GraphOfOperations: return got()
def got_eq() -> operations.GraphOfOperations: return got()

def cot_ei() -> operations.GraphOfOperations: return cot()
def cot_eo() -> operations.GraphOfOperations: return cot()
def cot_eq() -> operations.GraphOfOperations: return cot()

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