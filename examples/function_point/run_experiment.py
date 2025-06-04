#!/usr/bin/env python3

# Copyright (c) 2023 ETH Zurich.
#                    All rights reserved.
#
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# main author: Your Name

import os
import logging
from function_point import run, io, cot, tot, got

if __name__ == "__main__":
    """
    运行功能点评估实验。
    """
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # 实验配置
    budget = 5.0  # 预算（美元）
    samples = list(range(8))  # 使用所有8个示例
    approaches = [io, cot, tot, got]  # 使用所有方法
    model = "gpt-4"  # 使用GPT-4模型

    # 运行实验
    logger.info("开始运行功能点评估实验...")
    logger.info(f"使用模型: {model}")
    logger.info(f"预算: ${budget}")
    logger.info(f"样本数量: {len(samples)}")
    logger.info(f"方法数量: {len(approaches)}")

    try:
        spent = run(samples, approaches, budget, model)
        logger.info(f"实验完成！花费: ${spent:.2f}")
    except Exception as e:
        logger.error(f"实验运行出错: {str(e)}") 