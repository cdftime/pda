"""
清除所有使用数据 — 将账单、日志、上传文件、缓存一次性清空。

用法:
    python clear_data.py              # 清除所有（需确认）
    python clear_data.py --yes        # 跳过确认，直接清除
    python clear_data.py --dry-run    # 仅预览，不实际删除
"""

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 需要清理的目标
CLEANUP = [
    # (路径, 名称, 清理方式)
    (ROOT / "data" / "my_payment.csv", "账单 CSV", "file"),
    (ROOT / "predata", "待合并账单目录", "dir_content"),
    (ROOT / "logs", "合并日志目录", "dir_content"),
    (ROOT / "__pycache__", "项目 Python 缓存", "dir"),
    (ROOT.parent / "__pycache__", "根目录 Python 缓存", "dir_optional"),
    (ROOT / "data" / "my_payment_backup.csv", "备份 CSV (如有)", "file_optional"),
]

STATIC_FILES = [
    # 数据文件夹本身保留，只清内容
    ROOT / "data",
    ROOT / "predata",
    ROOT / "logs",
]


def clear(dry_run: bool = False) -> None:
    removed = 0
    kept = 0

    for path, label, mode in CLEANUP:
        if mode == "file":
            if path.exists():
                size = path.stat().st_size
                if not dry_run:
                    path.unlink()
                print(f"  {'[模拟] ' if dry_run else ''}🗑  {label}: {path.name} ({size:,} bytes)")
                removed += 1
            else:
                kept += 1

        elif mode == "file_optional":
            if path.exists():
                size = path.stat().st_size
                if not dry_run:
                    path.unlink()
                print(f"  {'[模拟] ' if dry_run else ''}🗑  {label}: {path.name} ({size:,} bytes)")
                removed += 1

        elif mode == "dir":
            if path.exists():
                if not dry_run:
                    shutil.rmtree(path)
                print(f"  {'[模拟] ' if dry_run else ''}🗑  {label}: {path.name}/")
                removed += 1
            else:
                kept += 1

        elif mode == "dir_optional":
            if path.exists():
                if not dry_run:
                    shutil.rmtree(path)
                print(f"  {'[模拟] ' if dry_run else ''}🗑  {label}: {path.name}/")
                removed += 1

        elif mode == "dir_content":
            if path.is_dir():
                files = list(path.glob("*"))
                for f in files:
                    if f.is_file():
                        size = f.stat().st_size
                        if not dry_run:
                            f.unlink()
                        print(f"  {'[模拟] ' if dry_run else ''}🗑  {label}: {f.name} ({size:,} bytes)")
                        removed += 1
                if not files:
                    kept += 1
            else:
                kept += 1

    # 确保空目录存在
    for d in STATIC_FILES:
        d.mkdir(parents=True, exist_ok=True)

    print()
    if dry_run:
        print(f"📋 预览完成: 将删除 {removed} 项")
    elif removed > 0:
        print(f"✅ 已清除 {removed} 项使用数据")
        print(f"   保留 {kept} 个空目录 (data/ predata/ logs/)")
    else:
        print("💤 没有需要清除的数据")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清除 PocketLedger 所有使用数据")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过确认，直接清除")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际删除")
    args = parser.parse_args()

    print("PocketLedger · 数据清理")
    print("=" * 40)

    # 统计
    total_files = 0
    for path, _, mode in CLEANUP:
        if mode == "file" or mode == "file_optional":
            total_files += 1 if path.exists() else 0
        elif mode == "dir" or mode == "dir_optional":
            total_files += 1 if path.exists() else 0
        elif mode == "dir_content":
            total_files += len(list(path.glob("*"))) if path.is_dir() else 0

    if total_files == 0:
        print("💤 没有需要清除的数据")
    else:
        if args.dry_run:
            clear(dry_run=True)
        elif args.yes:
            clear()
        else:
            print(f"\n将清除以下内容:")
            csv = ROOT / "data" / "my_payment.csv"
            if csv.exists():
                print(f"  📄 账单数据: {csv.name} ({csv.stat().st_size:,} bytes)")
            log_files = list((ROOT / "logs").glob("*.log"))
            if log_files:
                print(f"  📋 操作日志: {len(log_files)} 个文件")
            predata_files = list((ROOT / "predata").glob("*"))
            if predata_files:
                print(f"  📂 待合并文件: {len(predata_files)} 个")
            pycache = ROOT / "__pycache__"
            if pycache.exists():
                print(f"  🐍 Python 缓存: __pycache__/")

            print(f"\n⚠️  此操作不可逆！")
            ans = input("确认清除? (输入 yes 确认): ").strip()
            if ans.lower() == "yes":
                clear()
            else:
                print("已取消")
