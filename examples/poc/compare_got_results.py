import os
import sys
import json
import re
from typing import List, Dict, Optional

# 添加项目根目录到路径，以便导入 graph_of_thoughts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# LLM相关配置
_LLM_INSTANCE = None
_USE_LLM_SEMANTIC = True

def init_llm(model_name: str = "deepseek", use_semantic: bool = True):
    """
    初始化用于语义比较的LLM实例。
    
    :param model_name: 模型名称
    :param use_semantic: 是否启用LLM语义比较
    """
    global _LLM_INSTANCE, _USE_LLM_SEMANTIC
    
    if use_semantic:
        try:
            from graph_of_thoughts import language_models
            config_path = os.path.join(
                os.path.dirname(__file__),
                "../../graph_of_thoughts/language_models/config.json"
            )
            _LLM_INSTANCE = language_models.ChatGPT(config_path, model_name=model_name, cache=True)
            _USE_LLM_SEMANTIC = True
            print(f"✅ LLM语义比较已启用 (模型: {model_name})")
        except Exception as e:
            print(f"⚠️ 无法初始化LLM，回退到字符串相似度: {e}")
            _USE_LLM_SEMANTIC = False
    else:
        _USE_LLM_SEMANTIC = False
        print("ℹ️ 使用字符串相似度比较（未启用LLM）")

def normalize_name(name: str) -> str:
    """
    标准化功能点名称，用于比较。
    """
    name = name.lower().strip()
    name = ' '.join(name.split())
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'（[^）]*）', '', name)
    return name.strip()

def string_similarity(s1: str, s2: str) -> float:
    """
    计算两个字符串的相似度（基于Jaccard相似度）。
    """
    if not s1 or not s2:
        return 0.0
    
    set1 = set(s1)
    set2 = set(s2)
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0

def llm_semantic_similarity(name1: str, name2: str) -> float:
    """
    使用LLM判断两个功能点名称的语义相似度。
    
    :param name1: 第一个功能点名称
    :param name2: 第二个功能点名称
    :return: 相似度分数 (0.0 - 1.0)
    """
    global _LLM_INSTANCE
    
    if _LLM_INSTANCE is None:
        return string_similarity(normalize_name(name1), normalize_name(name2))
    
    prompt = f"""你是一个IFPUG功能点分析专家。请判断以下两个功能点名称是否指代同一个或非常相似的功能点。

功能点1: {name1}
功能点2: {name2}

请分析：
1. 它们是否指代相同或相似的数据/功能？
2. 考虑同义词、缩写、中英文翻译等因素
3. 只要核心语义相同即可，不需要完全字面匹配

请直接回答相似度分数（0.0到1.0之间的小数）：
- 1.0: 完全相同的功能点
- 0.8-0.9: 高度相似，很可能是同一个功能点
- 0.5-0.7: 中等相似，有一定关联
- 0.0-0.4: 不相似或不相关

只需要回答一个数字，格式如：0.85"""

    try:
        response = _LLM_INSTANCE.query(prompt, num_responses=1)
        texts = _LLM_INSTANCE.get_response_texts(response)
        
        if texts and len(texts) > 0:
            text = texts[0].strip()
            match = re.search(r'(\d+\.?\d*)', text)
            if match:
                score = float(match.group(1))
                return max(0.0, min(1.0, score))
    except Exception as e:
        print(f"    ⚠️ LLM调用失败: {e}")
    
    # 回退到字符串相似度
    return string_similarity(normalize_name(name1), normalize_name(name2))

def get_similarity(name1: str, name2: str) -> float:
    """
    获取两个名称的相似度，根据配置选择LLM或字符串方法。
    """
    if _USE_LLM_SEMANTIC and _LLM_INSTANCE:
        return llm_semantic_similarity(name1, name2)
    else:
        return string_similarity(normalize_name(name1), normalize_name(name2))

def calculate_semantic_similarity(predicted: List[str], ground_truth: List[str], 
                                   similarity_threshold: float = 0.5,
                                   verbose: bool = False) -> Dict:
    """
    计算预测的功能点列表和真实答案的语义相似度。
    使用精确匹配 + 模糊/语义匹配相结合的方法。
    """
    if not ground_truth and not predicted:
        return {
            "f1_score": 1.0,
            "precision": 1.0,
            "recall": 1.0,
            "exact_matches": [],
            "fuzzy_matches": [],
            "unmatched_predicted": [],
            "unmatched_ground_truth": []
        }
    if not ground_truth or not predicted:
        return {
            "f1_score": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "exact_matches": [],
            "fuzzy_matches": [],
            "unmatched_predicted": predicted if predicted else [],
            "unmatched_ground_truth": ground_truth if ground_truth else []
        }
    
    # 标准化所有名称
    pred_normalized = [(normalize_name(p), p) for p in predicted]
    truth_normalized = [(normalize_name(t), t) for t in ground_truth]
    
    # 精确匹配
    pred_norm_set = set(p[0] for p in pred_normalized)
    truth_norm_set = set(t[0] for t in truth_normalized)
    
    exact_match_norms = pred_norm_set & truth_norm_set
    exact_matches = []
    
    for norm in exact_match_norms:
        pred_orig = next((p[1] for p in pred_normalized if p[0] == norm), None)
        truth_orig = next((t[1] for t in truth_normalized if t[0] == norm), None)
        if pred_orig and truth_orig:
            exact_matches.append({
                "predicted": pred_orig,
                "ground_truth": truth_orig,
                "score": 1.0
            })
    
    # 语义/模糊匹配
    unmatched_pred = [(norm, orig) for norm, orig in pred_normalized if norm not in exact_match_norms]
    unmatched_truth = [(norm, orig) for norm, orig in truth_normalized if norm not in exact_match_norms]
    
    fuzzy_score = 0.0
    matched_truth_origs = set()
    fuzzy_matches = []
    
    for pred_norm, pred_orig in unmatched_pred:
        max_similarity = 0.0
        best_match_orig = None
        
        if verbose:
            print(f"    🔍 匹配 '{pred_orig}'...")
        
        for truth_norm, truth_orig in unmatched_truth:
            if truth_orig in matched_truth_origs:
                continue
            
            # 使用LLM或字符串相似度
            similarity = get_similarity(pred_orig, truth_orig)
            
            if verbose:
                print(f"       vs '{truth_orig}': {similarity:.2f}")
            
            if similarity > max_similarity:
                max_similarity = similarity
                best_match_orig = truth_orig
        
        if max_similarity >= similarity_threshold and best_match_orig:
            fuzzy_score += max_similarity
            matched_truth_origs.add(best_match_orig)
            fuzzy_matches.append({
                "predicted": pred_orig,
                "ground_truth": best_match_orig,
                "score": round(max_similarity, 2)
            })
            if verbose:
                print(f"       ✓ 匹配: {pred_orig} ↔ {best_match_orig} ({max_similarity:.2f})")
    
    # 未匹配的项
    final_unmatched_pred = [orig for norm, orig in unmatched_pred 
                           if orig not in [m["predicted"] for m in fuzzy_matches]]
    final_unmatched_truth = [orig for norm, orig in unmatched_truth 
                            if orig not in matched_truth_origs]
    
    # 计算F1分数
    total_matches = len(exact_matches) + fuzzy_score
    precision = total_matches / len(predicted) if predicted else 0
    recall = total_matches / len(ground_truth) if ground_truth else 0
    
    if precision + recall == 0:
        f1_score = 0.0
    else:
        f1_score = 2 * (precision * recall) / (precision + recall)
    
    return {
        "f1_score": round(f1_score, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "exact_matches": exact_matches,
        "fuzzy_matches": fuzzy_matches,
        "unmatched_predicted": final_unmatched_pred,
        "unmatched_ground_truth": final_unmatched_truth
    }

def calculate_match_score(got_count, expert_count):
    """简单的数量比较分数"""
    if got_count == 0 and expert_count == 0:
        return 1.0
    if got_count == 0 or expert_count == 0:
        return 0.0
    return min(got_count, expert_count) / max(got_count, expert_count)

def process_directory(directory_path, verbose: bool = False):
    got_file_path = os.path.join(directory_path, 'got_selection_result.json')
    expert_file_path = os.path.join(directory_path, 'functions_cleaned.json')

    if not (os.path.exists(got_file_path) and os.path.exists(expert_file_path)):
        return

    try:
        # Read GOT results
        with open(got_file_path, 'r', encoding='utf-8') as f:
            got_data = json.load(f)
            got_ilf_list = got_data.get('ILF', [])
            got_eif_list = got_data.get('EIF', [])

        # Read Expert results
        with open(expert_file_path, 'r', encoding='utf-8') as f:
            expert_data = json.load(f)
            expert_ilf_list = []
            expert_eif_list = []
            for item in expert_data:
                f_type = item.get('functionType')
                f_name = item.get('functionName', '')
                if f_type == 'ILF':
                    expert_ilf_list.append(f_name)
                elif f_type == 'EIF':
                    expert_eif_list.append(f_name)

        print(f"\n📁 处理: {os.path.basename(os.path.dirname(directory_path))}/{os.path.basename(directory_path)}")
        
        # Calculate semantic similarity
        if verbose:
            print("  📊 ILF比较:")
        ilf_similarity = calculate_semantic_similarity(got_ilf_list, expert_ilf_list, verbose=verbose)
        
        if verbose:
            print("  📊 EIF比较:")
        eif_similarity = calculate_semantic_similarity(got_eif_list, expert_eif_list, verbose=verbose)

        # Calculate simple count-based scores
        ilf_count_score = calculate_match_score(len(got_ilf_list), len(expert_ilf_list))
        eif_count_score = calculate_match_score(len(got_eif_list), len(expert_eif_list))

        result = {
            "summary": {
                "got_ILF_count": len(got_ilf_list),
                "expert_ILF_count": len(expert_ilf_list),
                "got_EIF_count": len(got_eif_list),
                "expert_EIF_count": len(expert_eif_list),
                "ilf_count_match_score": round(ilf_count_score, 2),
                "eif_count_match_score": round(eif_count_score, 2),
                "ilf_semantic_f1": ilf_similarity["f1_score"],
                "eif_semantic_f1": eif_similarity["f1_score"],
                "use_llm_semantic": _USE_LLM_SEMANTIC
            },
            "ILF_comparison": {
                "got_list": got_ilf_list,
                "expert_list": expert_ilf_list,
                "semantic_metrics": {
                    "f1_score": ilf_similarity["f1_score"],
                    "precision": ilf_similarity["precision"],
                    "recall": ilf_similarity["recall"]
                },
                "exact_matches": ilf_similarity["exact_matches"],
                "fuzzy_matches": ilf_similarity["fuzzy_matches"],
                "unmatched_predicted": ilf_similarity["unmatched_predicted"],
                "unmatched_ground_truth": ilf_similarity["unmatched_ground_truth"]
            },
            "EIF_comparison": {
                "got_list": got_eif_list,
                "expert_list": expert_eif_list,
                "semantic_metrics": {
                    "f1_score": eif_similarity["f1_score"],
                    "precision": eif_similarity["precision"],
                    "recall": eif_similarity["recall"]
                },
                "exact_matches": eif_similarity["exact_matches"],
                "fuzzy_matches": eif_similarity["fuzzy_matches"],
                "unmatched_predicted": eif_similarity["unmatched_predicted"],
                "unmatched_ground_truth": eif_similarity["unmatched_ground_truth"]
            }
        }

        # Write result
        result_file_path = os.path.join(directory_path, 'comparison_result.json')
        with open(result_file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        
        # Print summary
        print(f"   ILF: GOT={len(got_ilf_list)}, Expert={len(expert_ilf_list)}, F1={ilf_similarity['f1_score']:.3f} (P={ilf_similarity['precision']:.2f}, R={ilf_similarity['recall']:.2f})")
        print(f"   EIF: GOT={len(got_eif_list)}, Expert={len(expert_eif_list)}, F1={eif_similarity['f1_score']:.3f} (P={eif_similarity['precision']:.2f}, R={eif_similarity['recall']:.2f})")
        
        # Print match details
        if ilf_similarity["exact_matches"]:
            print(f"   ILF精确匹配({len(ilf_similarity['exact_matches'])}): {[m['predicted'] for m in ilf_similarity['exact_matches']]}")
        if ilf_similarity["fuzzy_matches"]:
            ilf_fuzzy_strs = [f"{m['predicted']} ↔ {m['ground_truth']} ({m['score']})" for m in ilf_similarity['fuzzy_matches']]
            print(f"   ILF语义匹配({len(ilf_similarity['fuzzy_matches'])}): {ilf_fuzzy_strs}")
        if ilf_similarity["unmatched_predicted"]:
            print(f"   ILF未匹配(GOT): {ilf_similarity['unmatched_predicted']}")
        if ilf_similarity["unmatched_ground_truth"]:
            print(f"   ILF未匹配(Expert): {ilf_similarity['unmatched_ground_truth']}")
            
        if eif_similarity["exact_matches"]:
            print(f"   EIF精确匹配({len(eif_similarity['exact_matches'])}): {[m['predicted'] for m in eif_similarity['exact_matches']]}")
        if eif_similarity["fuzzy_matches"]:
            eif_fuzzy_strs = [f"{m['predicted']} ↔ {m['ground_truth']} ({m['score']})" for m in eif_similarity['fuzzy_matches']]
            print(f"   EIF语义匹配({len(eif_similarity['fuzzy_matches'])}): {eif_fuzzy_strs}")
        if eif_similarity["unmatched_predicted"]:
            print(f"   EIF未匹配(GOT): {eif_similarity['unmatched_predicted']}")
        if eif_similarity["unmatched_ground_truth"]:
            print(f"   EIF未匹配(Expert): {eif_similarity['unmatched_ground_truth']}")

    except Exception as e:
        print(f"❌ Error processing {directory_path}: {e}")
        import traceback
        traceback.print_exc()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='GOT vs Expert 功能点语义比较')
    parser.add_argument('--use-llm', action='store_true', help='使用LLM进行语义比较（更精确但有API成本）')
    parser.add_argument('--model', type=str, default='deepseek', help='LLM模型名称')
    parser.add_argument('--verbose', action='store_true', help='显示详细的匹配过程')
    args = parser.parse_args()
    
    base_dir = os.path.join(os.path.dirname(__file__), 'requirement fetch')
    
    print("=" * 70)
    print("🔍 GOT vs Expert 功能点语义比较")
    print("=" * 70)
    
    # 初始化LLM（如果启用）
    init_llm(model_name=args.model, use_semantic=args.use_llm)
    
    processed_count = 0
    
    # Walk through the directory
    for root, dirs, files in os.walk(base_dir):
        if 'got_selection_result.json' in files and 'functions_cleaned.json' in files:
            process_directory(root, verbose=args.verbose)
            processed_count += 1
    
    print("\n" + "=" * 70)
    print(f"✅ 处理完成，共处理 {processed_count} 个目录")
    if _USE_LLM_SEMANTIC and _LLM_INSTANCE:
        print(f"💰 LLM API成本: ${_LLM_INSTANCE.cost:.4f}")
    print("=" * 70)

if __name__ == "__main__":
    main()
