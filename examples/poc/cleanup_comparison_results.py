import os
import argparse

def cleanup_comparison_results(root_dir: str, limit: int = None, dry_run: bool = False):
    """
    删除 requirement fetch 目录中的 comparison_result.json 文件。
    
    :param root_dir: 根目录路径
    :param limit: 限制删除的文件数量
    :param dry_run: 如果为True，只显示要删除的文件但不实际删除
    """
    deleted_count = 0
    
    for root, dirs, files in os.walk(root_dir):
        if limit and deleted_count >= limit:
            print(f"\n⏹️ 已达到限制数量 {limit}，停止删除")
            break
        
        if 'comparison_result.json' in files:
            file_path = os.path.join(root, 'comparison_result.json')
            rel_path = os.path.relpath(file_path, root_dir)
            
            if dry_run:
                print(f"🔍 [DRY RUN] 将删除: {rel_path}")
            else:
                try:
                    os.remove(file_path)
                    print(f"🗑️ 已删除: {rel_path}")
                except Exception as e:
                    print(f"❌ 删除失败 {rel_path}: {e}")
                    continue
            
            deleted_count += 1
    
    return deleted_count

def main():
    parser = argparse.ArgumentParser(description='删除 comparison_result.json 文件')
    parser.add_argument('--limit', type=int, default=None, help='限制删除的文件数量')
    parser.add_argument('--dry-run', action='store_true', help='只显示要删除的文件，不实际删除')
    args = parser.parse_args()
    
    base_dir = os.path.join(os.path.dirname(__file__), 'requirement fetch')
    
    print("=" * 60)
    print("🗑️ 清理 comparison_result.json 文件")
    print("=" * 60)
    
    if args.dry_run:
        print("⚠️ DRY RUN 模式 - 不会实际删除文件\n")
    
    if args.limit:
        print(f"📌 限制删除数量: {args.limit}\n")
    
    deleted_count = cleanup_comparison_results(base_dir, limit=args.limit, dry_run=args.dry_run)
    
    print("\n" + "=" * 60)
    if args.dry_run:
        print(f"✅ DRY RUN 完成，共发现 {deleted_count} 个文件可删除")
    else:
        print(f"✅ 清理完成，共删除 {deleted_count} 个文件")
    print("=" * 60)

if __name__ == "__main__":
    main()

