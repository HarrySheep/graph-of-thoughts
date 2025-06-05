#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
功能点评估实验实现。
使用不同的提示工程方法（IO、COT、TOT、GOT）来判断功能点是否为ILF。
"""

import os
import logging
import datetime
import json
import csv
from functools import partial
from typing import Dict, List, Callable, Union
from graph_of_thoughts import controller, language_models, operations, prompter, parser

def test_ilf_assessment(state: Dict) -> bool:
    """
    Function to test whether the final solution matches ground truth.

    :param state: Thought state that represents the final solution.
    :type state: Dict
    :return: Returns whether the solution matches the ground truth.
    :rtype: bool
    """
    try:
        prediction = state["current"].lower().strip() == "是"
        ground_truth = state["ground_truth"]
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
        prediction = state["current"].lower().strip() == "是"
        ground_truth = state["ground_truth"]
        return 1.0 if prediction == ground_truth else 0.0
    except:
        return 0.0

class FunctionPointPrompter(prompter.Prompter):
    """
    FunctionPointPrompter provides the generation of prompts specific to the
    function point assessment example for the language models.

    Inherits from the Prompter class and implements its abstract methods.
    """

    io_prompt = """你是一个IFPUG功能点分析专家。请判断给定的功能点是否构成内部逻辑文件（ILF）。
只需回答"是"或"否"。

[需求文档]
{requirement_text}

[候选功能点]
名称：{candidate_name}"""

    cot_prompt = """你是一个IFPUG功能点分析专家。请判断给定的功能点是否构成内部逻辑文件（ILF）。
请按照以下步骤进行分析：

1. 首先，判断是否是用户可识别的逻辑相关数据组
2. 然后，判断是否在应用边界内维护
3. 最后，判断是否通过应用的基本流程维护
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

    tot_prompt = """你是一个IFPUG功能点分析专家。请判断给定的功能点是否构成内部逻辑文件（ILF）。
请使用思维树方法进行分析：

[需求文档]
{requirement_text}

[候选功能点]
名称：{candidate_name}

请按以下格式输出：

1. 初步判断
   1.1 [第一印象]
   1.2 [可能的问题]

2. 深入分析
   2.1 数据组特征
       - [分析数据的逻辑相关性]
       - [分析用户可识别性]
   2.2 维护方式
       - [分析应用边界]
       - [分析维护流程]

3. 反向验证
   3.1 [考虑相反情况]
   3.2 [验证是否有遗漏]

4. 最终结论
   [是/否]"""

    got_prompt = """你是一个IFPUG功能点分析专家。请使用思维图方法判断给定的功能点是否构成内部逻辑文件（ILF）。

[需求文档]
{requirement_text}

[候选功能点]
名称：{candidate_name}

请按以下步骤分析：

1. 需求分解
- 识别关键数据实体
- 分析数据关系
- 标注维护方式

2. 多路径验证
路径1：从用户视角
- 数据组是否满足业务需求
- 用户是否能识别此数据组

路径2：从系统视角
- 数据是否在应用边界内
- 是否有完整的维护流程

路径3：从IFPUG规则视角
- 检查是否符合ILF定义
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
3. 提出改进的思路
4. 给出改进后的判断

最终答案：[是/否]"""

    perspective_prompt = """你是一个IFPUG功能点分析专家。请从{perspective}分析此功能点是否构成ILF：

[需求文档]
{requirement_text}

[候选功能点]
名称：{candidate_name}

分析思路：
1. ...
2. ...

最终答案：[是/否]"""

    merge_prompt = """你是一个IFPUG功能点分析专家。请综合以下三个视角的分析结果：

用户视角分析：{user_perspective}
系统视角分析：{system_perspective}
IFPUG规则视角分析：{ifpug_perspective}

请综合考虑：
1. 分析各视角的共识点
2. 处理可能的分歧
3. 权衡不同因素

最终答案：[是/否]"""

    def generate_prompt(self, num_branches: int, original: str, current: str, method: str, **kwargs) -> str:
        """
        Generate a generate prompt for the language model.

        :param num_branches: The number of responses the prompt should ask the LM to generate.
        :type num_branches: int
        :param original: Input text.
        :type original: str
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
    FunctionPointParser provides the parsing of language model reponses
    specific to the function point assessment example.

    Inherits from the Parser class and implements its abstract methods.
    """

    def parse_generate_answer(self, state: Dict, texts: List[str]) -> List[Dict]:
        """
        Parse the response from the language model for a generate prompt.

        :param state: The thought state used to generate the prompt.
        :type state: Dict
        :param texts: The responses to the prompt from the language model.
        :type texts: List[str]
        :return: The new thought states after parsing the respones from the language model.
        :rtype: List[Dict]
        """
        new_states = []
        for text in texts:
            try:
                # Extract the final answer (是/否)
                if "最终答案：" in text:
                    answer = text.split("最终答案：")[-1].strip()
                else:
                    answer = text.strip()
                
                new_state = state.copy()
                new_state["current"] = answer
                new_states.append(new_state)
            except Exception as e:
                logging.error(f"Could not parse step answer: {text}. Error: {e}")
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
    operations_graph.append_operation(operations.GroundTruth(test_ilf_assessment))

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
    operations_graph.append_operation(operations.GroundTruth(test_ilf_assessment))

    return operations_graph

def tot() -> operations.GraphOfOperations:
    """
    Generates the Graph of Operations for the ToT method.

    :return: Graph of Operations
    :rtype: GraphOfOperations
    """
    operations_graph = operations.GraphOfOperations()

    operations_graph.append_operation(operations.Generate(1, 20))
    operations_graph.append_operation(operations.Score(1, False, score_assessment))
    keep_best_1 = operations.KeepBestN(1, False)
    operations_graph.append_operation(keep_best_1)

    for _ in range(3):
        operations_graph.append_operation(operations.Generate(1, 20))
        operations_graph.append_operation(operations.Score(1, False, score_assessment))
        keep_best_2 = operations.KeepBestN(1, False)
        keep_best_2.add_predecessor(keep_best_1)
        operations_graph.append_operation(keep_best_2)
        keep_best_1 = keep_best_2

    operations_graph.append_operation(operations.KeepBestN(1, False))
    operations_graph.append_operation(operations.GroundTruth(test_ilf_assessment))

    return operations_graph

def got() -> operations.GraphOfOperations:
    """
    Generates the Graph of Operations for the GoT method.
    使用图结构来分析ILF判断问题：
    1. 从三个不同视角分析（用户视角、系统视角、IFPUG规则视角）
    2. 每个视角生成多个思路
    3. 合并和验证结果
    """
    operations_graph = operations.GraphOfOperations()

    # 1. 首先从三个视角分别分析
    sub_analyses = []
    perspectives = ["用户视角", "系统视角", "IFPUG规则视角"]
    
    for perspective in perspectives:
        # 1.1 选择特定视角
        sub_analysis = operations.Selector(
            lambda thoughts, p=perspective: [
                thought for thought in thoughts 
                if thought.state.get("perspective") == p
            ]
        )
        operations_graph.add_operation(sub_analysis)

        # 1.2 从该视角生成多个分析
        generate = operations.Generate(1, 5)  # 每个视角生成5个思路
        generate.add_predecessor(sub_analysis)
        operations_graph.add_operation(generate)

        # 1.3 评分并保留最佳
        score = operations.Score(1, False, score_assessment)
        score.add_predecessor(generate)
        operations_graph.add_operation(score)
        
        keep_best = operations.KeepBestN(1, False)
        keep_best.add_predecessor(score)
        operations_graph.add_operation(keep_best)

        sub_analyses.append(keep_best)

    # 2. 合并三个视角的结果
    aggregate = operations.Aggregate(3)  # 生成3个合并方案
    for analysis in sub_analyses:
        aggregate.add_predecessor(analysis)
    operations_graph.add_operation(aggregate)

    # 3. 验证和改进合并结果
    validate_improve = operations.ValidateAndImprove(1, True, 3)
    validate_improve.add_predecessor(aggregate)
    operations_graph.add_operation(validate_improve)

    # 4. 最终评分和验证
    final_score = operations.Score(1, False, score_assessment)
    final_score.add_predecessor(validate_improve)
    operations_graph.add_operation(final_score)

    keep_best_final = operations.KeepBestN(1, False)
    keep_best_final.add_predecessor(final_score)
    operations_graph.add_operation(keep_best_final)

    operations_graph.append_operation(operations.GroundTruth(test_ilf_assessment))

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
    data_path = os.path.join(os.path.dirname(__file__), "ilf_samples.csv")
    data = []
    with open(data_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            data.append([int(row[0]), row[1], row[2], row[3] == "True"])

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
    budget = 5
    samples = [0]  # 只使用第一个样本进行测试
    approaches = [io, cot, tot, got]  # 使用所有方法进行测试

    spent = run(samples, approaches, budget, "gpt-4")

    logging.info(f"Spent {spent} out of {budget} budget.") 