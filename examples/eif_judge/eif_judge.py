#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
功能点评估实验实现。
使用不同的提示工程方法（IO、COT、TOT、GOT）来判断功能点是否为EIF。
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

def test_eif_assessment(state: Dict) -> bool:
    """
    Function to test whether the final solution matches ground truth.

    :param state: Thought state that represents the final solution.
    :type state: Dict
    :return: Returns whether the solution matches the ground truth.
    :rtype: bool
    """
    try:
        # 优先使用final_answer，确保其为布尔类型
        if "final_answer" in state:
            prediction = state["final_answer"]  # 已经是布尔类型
        else:
            # 向后兼容，处理current
            prediction = state["current"].lower().strip() == "是"
        
        ground_truth = state["ground_truth"]  # 已经是布尔类型
        return prediction == ground_truth
    except:
        return False

def score_assessment(state: Dict) -> float:
    """
    Function to locally score the assessment that serves as a score.

    :param state: Thought state to be scored.
    :type state: Dict
    :return: Score (0 or 1).
    :rtype: float
    """
    try:
        # 优先使用final_answer，确保其为布尔类型
        if "final_answer" in state:
            prediction = state["final_answer"]  # 已经是布尔类型
        else:
            # 向后兼容，处理current
            prediction = state["current"].lower().strip() == "是"
            
        ground_truth = state["ground_truth"]  # 已经是布尔类型
        return 1.0 if prediction == ground_truth else 0.0
    except:
        return 0.0

class FunctionPointPrompter(prompter.Prompter):
    """
    FunctionPointPrompter provides the generation of prompts specific to the
    function point assessment example for the language models.

    Inherits from the Prompter class and implements its abstract methods.
    """

    io_prompt = """你是一个IFPUG功能点分析专家。请判断给定的功能点是否构成外部接口文件（EIF）。
只需回答"是"或"否"。

[需求文档]
{requirement_text}

[候选功能点]
名称：{candidate_name}"""

    cot_prompt = """你是一个IFPUG功能点分析专家。请判断给定的功能点是否构成外部接口文件（EIF）。
请按照以下步骤进行分析：

1. 首先，判断是否逻辑上独立且用户可识别
2. 然后，判断是否被当前应用引用，但物理/逻辑上存在于当前应用之外
3. 最后，判断是否不由当前应用进行维护（即只读，不增删改）
4. 根据以上分析，得出最终结论

[需求文档]
{requirement_text}

[候选功能点]
名称：{candidate_name}

请按以下格式输出：
思考过程：
1. [分析第一个条件]
2. [分析第二个条件]
3. [分析第三个条件]
4. [得出结论]

最终答案：[是/否]"""

    tot_prompt = """你是一个IFPUG功能点分析专家。请判断给定的功能点是否构成外部接口文件（EIF）。

[需求文档]
{requirement_text}

[候选功能点]
名称：{candidate_name}

请按以下方法分析候选功能点是否为EIF功能点：

1. 初步判断
   1.1 [第一印象]
   1.2 [可能的问题]

2. 深入分析
   2.1 数据组特征
       - [分析数据是否逻辑上独立]
       - [分析用户可识别性]
   2.2 数据位置与访问方式
       - [分析数据是否存在于应用边界之外]
       - [分析应用是否仅引用（读取）该数据，不进行维护]

3. 反向验证
   3.1 [考虑相反情况]
   3.2 [验证是否有遗漏]

4. 最终结论
   [是/否]"""

    got_prompt = """你是一个IFPUG功能点分析专家。请判断给定的功能点是否构成外部接口文件（EIF）。

[需求文档]
{requirement_text}

[候选功能点]
名称：{candidate_name}

请按以下步骤分析：

1. 需求分解
- 识别关键数据实体
- 分析数据关系
- 标注数据来源和访问方式

2. 多路径验证
路径1：从用户视角
- 数据组是否满足业务需求
- 用户是否能识别此数据组

路径2：从系统视角
- 数据是否存在于应用边界之外
- 应用是否仅引用（读取）该数据，不进行增删改操作

路径3：从IFPUG规则视角
- 检查是否符合EIF定义
- 验证是否满足所有条件

3. 结果合并
- 综合各路径结果
- 处理可能的冲突
- 得出最终判断

最终答案：[是/否]"""

    tot_improve_prompt = """你是一个IFPUG功能点分析专家。基于之前的分析结果进行改进：

之前的判断：{current}

[需求文档]
{requirement_text}

[候选功能点]
名称：{candidate_name}

请基于之前的判断进行改进：
1. 分析之前判断的优点
2. 找出可能的问题或遗漏
3. 重新检查EIF的三个关键条件
4. 给出改进后的判断

最终答案：[是/否]"""

    perspective_prompt = """你是一个IFPUG功能点分析专家。请从{perspective}分析此功能点是否构成EIF。

[需求文档]
{requirement_text}

[候选功能点]
名称：{candidate_name}

[分析视角说明]
用户视角 - 关注：
- 数据组是否逻辑上独立且用户可识别
- 数据组是否能满足特定的业务需求
- 数据组对用户是否有实际业务价值

系统视角 - 关注：
- 数据是否物理/逻辑上存在于当前应用之外
- 应用是否仅引用（读取）该数据，不进行增删改操作
- 数据是否由其他应用或系统维护

IFPUG规则视角 - 关注：
- 是否满足EIF的所有必要条件（逻辑独立、外部存储、只读引用）
- 是否存在反例或例外情况
- 是否符合IFPUG的最佳实践

[分析步骤]
1. 仔细审视候选功能点的构成要素
2. 列举支持和反对的具体证据
3. 考虑是否存在反例或特殊情况
4. 给出该视角下的最终判断

[输出格式]
分析过程：
1. 构成要素分析：
   [详细分析内容]

2. 支持证据：
   - [列出具体支持证据]

3. 反对证据：
   - [列出具体反对证据]

4. 特殊情况考虑：
   [分析是否存在反例或特殊情况]

5. 结论：
   [总结性分析]

该视角的判断：[是/否]"""

    merge_prompt = """你是一个IFPUG功能点分析专家。请综合以下三个视角的分析结果，判断此功能点是否构成EIF。

[需求文档]
{requirement_text}

[候选功能点]
名称：{candidate_name}

[各视角分析结果]
用户视角分析：
{user_perspective}

系统视角分析：
{system_perspective}

IFPUG规则视角分析：
{ifpug_perspective}

[分析要求]
1. 必须同时满足以下所有条件才能判定为EIF：
   - 逻辑上独立且用户可识别的数据组
   - 被当前应用引用，但物理/逻辑上存在于当前应用之外
   - 不由当前应用进行维护（即只读，不增删改）

2. 存在以下任一情况就不能判定为EIF：
   - 数据由当前应用维护（有增删改操作）
   - 数据存储在应用边界内
   - 数据不是逻辑独立的
   - 不符合IFPUG规则的要求

请按以下步骤综合分析：
1. 分别总结各视角的关键发现
2. 检查是否满足所有必要条件
3. 检查是否存在任何排除条件
4. 权衡不同视角的观点
5. 得出最终判断

请输出：
1. 各视角关键发现：
   用户视角：[关键发现]
   系统视角：[关键发现]
   IFPUG规则视角：[关键发现]

2. 必要条件检查：
   - 逻辑上独立且用户可识别：[是/否] - [理由]
   - 存在于应用边界之外：[是/否] - [理由]
   - 仅引用不维护（只读）：[是/否] - [理由]

3. 排除条件检查：
   [列出发现的任何排除条件]

4. 综合分析：
   [详细的权衡分析]

最终判断：[是/否]"""

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
                requirement_text=kwargs["requirement_text"],
                candidate_name=kwargs["candidate_name"]
            )
        elif method.startswith("cot"):
            return self.cot_prompt.format(
                requirement_text=kwargs["requirement_text"],
                candidate_name=kwargs["candidate_name"]
            )
        elif method.startswith("tot"):
            if current is None or current == "":
                return self.tot_prompt.format(
                    requirement_text=kwargs["requirement_text"],
                    candidate_name=kwargs["candidate_name"]
                )
            return self.tot_improve_prompt.format(
                current=current,
                requirement_text=kwargs["requirement_text"],
                candidate_name=kwargs["candidate_name"]
            )
        elif method.startswith("got"):
            # 检查状态中的phase和perspective
            if "phase" in kwargs and kwargs["phase"] == "analysis" and "perspective" in kwargs:
                logging.debug(f"Using perspective prompt for {kwargs['perspective']}")
                return self.perspective_prompt.format(
                    perspective=kwargs["perspective"],
                    requirement_text=kwargs["requirement_text"],
                    candidate_name=kwargs["candidate_name"]
                )
            elif "phase" in kwargs and kwargs["phase"] == "merge" and kwargs.get("merge_perspectives"):
                logging.debug("Using merge prompt")
                return self.merge_prompt.format(
                    requirement_text=kwargs["requirement_text"],
                    candidate_name=kwargs["candidate_name"],
                    user_perspective=kwargs.get("user_perspective", ""),
                    system_perspective=kwargs.get("system_perspective", ""),
                    ifpug_perspective=kwargs.get("ifpug_perspective", "")
                )
            else:
                logging.debug("Using default got prompt")
                return self.got_prompt.format(
                    requirement_text=kwargs["requirement_text"],
                    candidate_name=kwargs["candidate_name"]
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

    def extract_answer(self, text: str) -> str:
        """
        从文本中提取答案（是/否）。

        :param text: 包含答案的文本
        :type text: str
        :return: 提取出的答案（是/否）
        :rtype: str
        """
        # 尝试不同的答案格式
        patterns = [
            r'最终判断：\[是/否\]',  # 标准格式
            r'最终判断：.*?(?:是|否)',  # 带任意字符的格式
            r'该视角的判断：\[是/否\]',  # 视角分析格式
            r'该视角的判断：.*?(?:是|否)',  # 带任意字符的视角分析格式
            r'最终答案：\[是/否\]',  # 另一种标准格式
            r'最终答案：.*?(?:是|否)',  # 带任意字符的另一种格式
            r'判断：.*?(?:是|否)',  # 简单格式
            r'结论：.*?(?:是|否)',  # 结论格式
            r'\*\*(?:是|否)\*\*',  # Markdown加粗格式
            r'最终判断：\*\*(?:是|否)\*\*',  # 带加粗的最终判断格式
            r'(?:是|否)'  # 最简单的格式（最后尝试）
        ]
        
        # 去除所有换行符，便于匹配
        text = text.replace('\n', ' ')
        
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                # 提取匹配文本中的"是"或"否"
                answer = re.search(r'(?:是|否)', match.group())
                if answer:
                    return answer.group()
        
        # 如果没有找到任何匹配，返回默认值
        logging.warning(f"No answer found in text: {text}")
        return "否"  # 默认返回否

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
                
                # 提取答案并转换为布尔类型
                answer = self.extract_answer(text)
                new_state["final_answer"] = (answer == "是")
                
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
                default_state["final_answer"] = False  # 默认为否
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
    data_path = os.path.join(os.path.dirname(__file__), "eif_samples.csv")
    data = []
    with open(data_path, "r", encoding="gbk") as f:  # 使用 GBK 编码
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            data.append([int(row[0]), row[1], row[2], row[3] == "TRUE"])

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
        logging.info(f"Running data {data[0]}: {data[1]}")
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
            operations_graph = method()
            executor = controller.Controller(
                lm,
                operations_graph,
                FunctionPointPrompter(),
                FunctionPointParser(),
                {
                    "requirement_text": data[2],
                    "candidate_name": data[1],
                    "ground_truth": data[3],
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
    Input (x)   : 需求文档和候选功能点名称
    Output (y)  : 判断结果（是/否）
    Correct     : y == 标准答案
    Input Example:
        需求文档：人力资源管理系统 - 职位信息管理模块...
        候选功能点：Job information
    Output Example:
        是
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
    
    print("🚀 开始运行功能点评估实验...")
    print("=" * 50)
    
    budget = 5
    samples = [0,1,2,3,4,5,6,7,8,9]  # 只使用第一个样本进行测试
    approaches = [tot]  # 使用所有方法进行测试

    print(f"📊 实验配置:")
    print(f"   - 预算: ${budget}")
    print(f"   - 样本数量: {len(samples)}")
    print(f"   - 方法: {[method.__name__ for method in approaches]}")
    print(f"   - 模型: qwen3-235b")
    print("=" * 50)


    spent = run(samples, approaches, budget, "qwen3-235b")

    print("=" * 50)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
    print(f"✅ 实验完成！")
    print(f"💰 花费: ${spent:.2f} / ${budget}")
    print(f"📁 结果保存在: results/ 目录")
    logging.info(f"Spent {spent} out of {budget} budget.") 