"""
Script to filter requirement documents using LLM.
Moves non-requirement documents to rubbish2/ folder.
"""

import os
import json
import shutil
import logging
import re
from pathlib import Path
from typing import Optional, List, Tuple
from openai import OpenAI

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('filter_requirements.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG_PATH = Path(__file__).parent.parent.parent / "graph_of_thoughts" / "language_models" / "config.json"
ROOT_DIR = Path(__file__).parent / "requirement fetch"
RUBBISH_DIR = ROOT_DIR / "rubbish2"

# Months to process
MONTHS_TO_PROCESS = [
    "2024-02",
    "2024-03", 
    "2024-05",
    "2024-06",
    "2024-08",
    "2024-10",
    "2024-11",
    "2024-12",
    "2025-01"
]


class RequirementFilter:
    """Filter requirement documents using LLM."""
    
    def __init__(self, model_key: str = "deepseek"):
        """Initialize the filter with LLM configuration."""
        self.model_key = model_key
        self.config = self._load_config()
        self.client = self._init_client()
        
    def _load_config(self) -> dict:
        """Load configuration from config.json."""
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _init_client(self) -> OpenAI:
        """Initialize OpenAI-compatible client."""
        model_config = self.config[self.model_key]
        return OpenAI(
            api_key=model_config["api_key"],
            base_url=model_config["base_url"]
        )
    
    def is_requirement_document(self, text: str) -> Tuple[bool, str]:
        """
        Use LLM to determine if the text is a valid requirement document.
        
        Returns:
            Tuple[bool, str]: (is_requirement, reason)
        """
        # Truncate text if too long (keep first 3000 chars for context)
        truncated_text = text[:3000] if len(text) > 3000 else text
        
        prompt = f"""请判断以下文本是否为软件需求文档。

软件需求文档的特征包括：
1. 包含需求背景、业务目标、功能描述等章节
2. 描述系统功能、业务流程、接口要求等
3. 包含明确的功能点或业务规则说明
4. 有结构化的需求描述（如功能列表、流程说明）

不是软件需求文档的情况：
1. 测试报告、测试确认单、UAT报告
2. 会议纪要、工作总结
3. 修数申请、数据修复单
4. 运维工单、故障处理记录
5. 纯配置变更、参数调整
6. 空白或内容过少（少于100字实质内容）
7. 审批流程单、流程确认单
8. 表格数据、报表样例

请仔细分析以下文本内容：
---
{truncated_text}
---

请按以下JSON格式回复（不要包含其他内容）：
{{"is_requirement": true/false, "reason": "简要说明判断理由"}}
"""
        
        try:
            model_config = self.config[self.model_key]
            response = self.client.chat.completions.create(
                model=model_config["model_id"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )
            
            result_text = response.choices[0].message.content.strip()
            logger.debug(f"LLM response: {result_text}")
            
            # Parse JSON response
            # Try to extract JSON from response (handle potential markdown code blocks)
            json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result.get("is_requirement", True), result.get("reason", "")
            else:
                logger.warning(f"Could not parse JSON from response: {result_text}")
                return True, "无法解析响应，默认保留"
                
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return True, f"LLM调用失败: {e}"  # Default to keeping the document


def find_requirement_files(month: str) -> List[Path]:
    """Find all requirement_text.txt files in a month folder."""
    month_dir = ROOT_DIR / month
    if not month_dir.exists():
        logger.warning(f"Month directory not found: {month_dir}")
        return []
    
    requirement_files = []
    for cr_dir in month_dir.iterdir():
        if cr_dir.is_dir() and cr_dir.name.startswith("CR"):
            req_file = cr_dir / "requirement_text.txt"
            if req_file.exists():
                requirement_files.append(req_file)
    
    return requirement_files


def move_to_rubbish(cr_folder: Path, month: str, reason: str):
    """Move a CR folder to rubbish2."""
    rubbish_month_dir = RUBBISH_DIR / month
    rubbish_month_dir.mkdir(parents=True, exist_ok=True)
    
    dest_dir = rubbish_month_dir / cr_folder.name
    
    # Handle if destination already exists
    if dest_dir.exists():
        logger.warning(f"Destination already exists, removing: {dest_dir}")
        shutil.rmtree(dest_dir)
    
    shutil.move(str(cr_folder), str(dest_dir))
    logger.info(f"Moved to rubbish2: {cr_folder.name} - Reason: {reason}")


def process_month(month: str, filter_obj: RequirementFilter, dry_run: bool = False):
    """Process all requirement files in a month."""
    logger.info(f"Processing month: {month}")
    
    requirement_files = find_requirement_files(month)
    logger.info(f"Found {len(requirement_files)} requirement files in {month}")
    
    moved_count = 0
    kept_count = 0
    
    for req_file in requirement_files:
        cr_folder = req_file.parent
        
        try:
            with open(req_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading {req_file}: {e}")
            continue
        
        # Check if content is too short or empty
        clean_content = content.strip()
        if len(clean_content) < 50:
            reason = "内容过短或空白"
            is_requirement = False
        else:
            is_requirement, reason = filter_obj.is_requirement_document(content)
        
        if is_requirement:
            logger.info(f"KEEP: {cr_folder.name} - {reason}")
            kept_count += 1
        else:
            logger.info(f"REMOVE: {cr_folder.name} - {reason}")
            if not dry_run:
                move_to_rubbish(cr_folder, month, reason)
            moved_count += 1
    
    return kept_count, moved_count


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Filter requirement documents using LLM')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Do not actually move files, just report what would be done')
    parser.add_argument('--model', default='deepseek',
                       choices=['qwen3-235b', 'qwen3-30b', 'deepseek'],
                       help='LLM model to use')
    parser.add_argument('--months', nargs='+', default=None,
                       help='Specific months to process (e.g., 2024-02 2024-03)')
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Starting requirement document filtering")
    logger.info(f"Model: {args.model}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 60)
    
    # Initialize filter
    filter_obj = RequirementFilter(model_key=args.model)
    
    # Determine which months to process
    months = args.months if args.months else MONTHS_TO_PROCESS
    
    total_kept = 0
    total_moved = 0
    
    for month in months:
        try:
            kept, moved = process_month(month, filter_obj, dry_run=args.dry_run)
            total_kept += kept
            total_moved += moved
        except Exception as e:
            logger.error(f"Error processing month {month}: {e}")
    
    logger.info("=" * 60)
    logger.info(f"Processing complete!")
    logger.info(f"Total kept: {total_kept}")
    logger.info(f"Total moved to rubbish2: {total_moved}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

