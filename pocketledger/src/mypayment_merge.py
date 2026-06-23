"""
预数据合并模块 — 扫描 predata/ 下所有文件，统一映射后写入 data/my_payment.csv。

用法:
    python mypayment_merge.py              # 合并（去重追加）
    python mypayment_merge.py --dry-run     # 预览不写入
    python mypayment_merge.py --clean-start # 从零重建（不保留旧数据）
"""

import argparse
import glob
import hashlib
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREDATA_DIR = ROOT / "predata"
TARGET_CSV = ROOT / "data" / "my_payment.csv"

# ═══════════════════════════════════════════════════════════
# 统一列（与 my_payment.csv 匹配）
# ═══════════════════════════════════════════════════════════
COLS = [
    "id", "order_time", "order_type", "keeper", "goods", "in_out",
    "order_amount", "payment_method", "status", "order_num", "keeper_num", "extra", "source",
]


def find_all_predata_files() -> list[str]:
    """扫描 predata/ 返回所有可解析文件的路径列表。"""
    if not PREDATA_DIR.is_dir():
        return []
    files: list[str] = []
    for f in sorted(PREDATA_DIR.iterdir()):
        s = f.suffix.lower()
        if s == ".csv":
            files.append(str(f))
        elif s == ".xlsx":
            files.append(str(f))
    return files


# ═══════════════════════════════════════════════════════════
# 支付宝 CSV (GBK) → 统一列
# ═══════════════════════════════════════════════════════════

def _parse_alipay(path: str) -> pd.DataFrame:
    """支付宝 GBK CSV → 统一列 DataFrame。

    表头行检测：硬编码映射 13 列标准支付宝导出格式。
    前 23 行为元信息。
    """
    def _read_alipay_csv(filepath: str):
        """尝试 GBK → UTF-8-SIG → UTF-8 读取支付宝 CSV。"""
        for enc in ["gbk", "utf-8-sig", "utf-8"]:
            try:
                with open(filepath, "r", encoding=enc) as f:
                    lines = f.readlines()
                return lines, enc
            except (UnicodeDecodeError, UnicodeError):
                continue
        raise ValueError(f"无法解码文件: {filepath}")

    lines, _enc = _read_alipay_csv(path)

    start = 0
    for i, line in enumerate(lines):
        if "交易时间" in line and ("交易分类" in line or "交易对方" in line):
            start = i
            break

    raw = pd.read_csv(path, encoding=_enc, skiprows=start, dtype=str, on_bad_lines="skip")
    raw = raw.dropna(axis=1, how="all").dropna(axis=0, how="all")

    # ── 列名映射 ──
    col_map = {}
    for c in raw.columns:
        s = str(c).strip()
        if "交易时间" in s:
            col_map[c] = "order_time"
        elif "交易分类" in s:
            col_map[c] = "order_type"
        elif "交易对方" in s:
            col_map[c] = "keeper"
        elif "对方账号" in s:
            col_map[c] = "extra"
        elif "商品说明" in s:
            col_map[c] = "goods"
        elif "收/支" in s:
            col_map[c] = "in_out"
        elif s == "金额" or ("金额" in s and "元" not in s):
            col_map[c] = "order_amount_raw"
        elif "收/付款方式" in s or "支付方式" in s:
            col_map[c] = "payment_method"
        elif "交易状态" in s:
            col_map[c] = "status"
        elif "交易订单号" in s:
            col_map[c] = "order_num_1"
        elif "商家订单号" in s:
            col_map[c] = "order_num_2"
        elif "备注" in s:
            col_map[c] = "extra_raw"

    df = raw.rename(columns=col_map)

    # 合并订单号（优先交易订单号）
    o1 = df.get("order_num_1", pd.Series("", index=df.index)).fillna("").astype(str)
    o2 = df.get("order_num_2", pd.Series("", index=df.index)).fillna("").astype(str)
    df["order_num"] = o1.where(o1.str.strip() != "", o2).str.strip()

    # extra 合并：对方账号 & 备注
    if "extra_raw" in df.columns and "extra" in df.columns:
        df["extra"] = df["extra"].fillna("") + " | " + df["extra_raw"].fillna("")
    elif "extra_raw" in df.columns:
        df["extra"] = df["extra_raw"]

    # 金额去逗号
    if "order_amount_raw" in df.columns:
        df["order_amount"] = (
            df["order_amount_raw"].astype(str)
            .str.replace(",", "", regex=False).str.replace("\xa5", "", regex=False)
        )
        df = df.drop(columns=["order_amount_raw"])

    df["source"] = "支付宝"

    # 归一化 in_out
    if "in_out" in df.columns:
        df["in_out"] = df["in_out"].astype(str).str.strip().map({
            "支出": "支出",
            "收入": "收入",
            "不计收支": "不计收支",
        }).fillna("支出")

    return _pad_columns(df)


# ═══════════════════════════════════════════════════════════
# 微信 XLSX → 统一列
# ═══════════════════════════════════════════════════════════

def _parse_wechat(path: str) -> pd.DataFrame:
    """微信 XLSX → 统一列 DataFrame。

    标准 11 列: 交易时间, 交易类型, 交易对方, 商品, 收/支, 金额(元), 支付方式, 当前状态, 交易单号, 商户单号, 备注
    前 17 行元信息。
    """
    raw = pd.read_excel(path, header=None, dtype=str)
    start = 0
    for i in range(len(raw)):
        row = raw.iloc[i].dropna().astype(str)
        if any("交易时间" in v for v in row) and any("交易类型" in v for v in row):
            start = i
            break

    df = pd.read_excel(path, skiprows=start, dtype=str)
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")

    col_map = {}
    for c in df.columns:
        s = str(c).strip()
        if "交易时间" in s:
            col_map[c] = "order_time"
        elif "交易类型" in s:
            col_map[c] = "order_type"
        elif "交易对方" in s:
            col_map[c] = "keeper"
        elif s == "商品":
            col_map[c] = "goods"
        elif "收/支" in s:
            col_map[c] = "in_out_raw"
        elif "金额" in s:
            col_map[c] = "order_amount_raw"
        elif "支付方式" in s:
            col_map[c] = "payment_method"
        elif "当前状态" in s:
            col_map[c] = "status"
        elif "交易单号" in s:
            col_map[c] = "order_num"
        elif "商户单号" in s:
            col_map[c] = "keeper_num"
        elif "备注" in s:
            col_map[c] = "extra"

    df = df.rename(columns=col_map)
    df["source"] = "微信"

    # in_out: "/" → 不计收支
    if "in_out_raw" in df.columns:
        df["in_out"] = df["in_out_raw"].astype(str).str.strip().map({
            "支出": "支出",
            "收入": "收入",
        }).fillna("不计收支")
        df = df.drop(columns=["in_out_raw"])

    if "order_amount_raw" in df.columns:
        df["order_amount"] = df["order_amount_raw"].astype(str).str.replace(",", "", regex=False)
        df = df.drop(columns=["order_amount_raw"])

    return _pad_columns(df)


# ═══════════════════════════════════════════════════════════
# 通用工具
# ═══════════════════════════════════════════════════════════

def _pad_columns(df: pd.DataFrame) -> pd.DataFrame:
    """补齐缺失列，返回无重复列的干净 DataFrame。"""
    for col in COLS:
        if col not in df.columns:
            df[col] = ""
    df = df[COLS].copy()
    df = df.loc[:, ~df.columns.duplicated()]
    return df


def _make_key(row: pd.Series) -> str:
    """生成去重键：时间|商户|金额。"""
    t = str(row.get("order_time", ""))[:19]
    k = str(row.get("keeper", ""))
    a = str(row.get("order_amount", ""))
    return f"{t}|{k}|{a}"


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def merge_predata(dry_run: bool = False, clean_start: bool = False) -> pd.DataFrame:
    """扫描 predata/ 下所有 CSV/XLSX → 统一映射 → 去重 → 写入 data/my_payment.csv。

    Parameters
    ----------
    dry_run : 仅预览不写入
    clean_start : 丢弃旧数据，从零重建
    """
    files = find_all_predata_files()
    if not files:
        print("[合并] predata/ 中没有文件，跳过")
        if TARGET_CSV.exists():
            return pd.read_csv(TARGET_CSV, encoding="utf-8-sig", dtype=str)
        return pd.DataFrame(columns=COLS)

    print(f"[合并] 发现 {len(files)} 个预数据文件")

    # 1) 解析所有文件
    parts: list[pd.DataFrame] = []
    total_success = 0
    for fpath in files:
        fname = Path(fpath).name
        suffix = Path(fpath).suffix.lower()
        try:
            if suffix == ".csv":
                df_part = _parse_alipay(fpath)
            elif suffix == ".xlsx":
                df_part = _parse_wechat(fpath)
            else:
                print(f"  [跳过] {fname} — 不支持 {suffix}")
                continue
            parts.append(df_part)
            total_success += len(df_part)
            print(f"  [OK] {fname}: {len(df_part):4d} 条")
        except Exception as e:
            print(f"  [失败] {fname}: {e}")

    if not parts:
        print("[合并] 所有文件解析失败，中止")
        return pd.DataFrame(columns=COLS)

    predata = pd.concat(parts, ignore_index=True)
    print(f"\n[合并] 解析完成: {total_success} 条 ({len(files)} 个文件)")

    # 2) 读旧数据
    main: pd.DataFrame
    if clean_start or not TARGET_CSV.exists():
        main = pd.DataFrame(columns=COLS)
        print("[合并] clean-start: 不保留旧数据")
    else:
        main = pd.read_csv(TARGET_CSV, encoding="utf-8-sig", dtype=str)
        # Ensure source column
        if "source" not in main.columns:
            main["source"] = "微信(旧)"
        main_source_count = len(main)
        print(f"[合并] 已有数据: {main_source_count} 条")

    # 3) 去重
    before = len(main) + len(predata)
    combined = pd.concat([main, predata], ignore_index=True)
    # Source-blind dedup: same time + keeper + amount → keep first
    combined["_key"] = combined.apply(_make_key, axis=1)
    combined = combined.drop_duplicates(subset="_key", keep="first").reset_index(drop=True)
    combined = combined.drop(columns=["_key"])
    removed = before - len(combined)
    print(f"[合并] 源 {before} → 去重 {removed} → 最终 {len(combined)} 条")

    # 4) 写入
    if not dry_run:
        out = combined[COLS].copy()
        # dedup columns if any duplicates
        out = out.loc[:, ~out.columns.duplicated()]
        out["id"] = range(1, len(out) + 1)
        out.to_csv(TARGET_CSV, index=False, encoding="utf-8-sig")
        print(f"[合并] 已写入 {TARGET_CSV} ({len(out)} 条, {len(out.columns)} 列)")

    return combined


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="predata/ → data/my_payment.csv")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--clean-start", action="store_true")
    args = parser.parse_args()
    merge_predata(dry_run=args.dry_run, clean_start=args.clean_start)
