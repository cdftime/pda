"""
支付数据清洗模块。

提供 clean_data() 读取 data/my_payment.csv 并执行清洗。
合并预数据请使用 mypayment_merge.py。
"""

import pandas as pd
import numpy as np
from pathlib import Path
from tabulate import tabulate

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

UNIFIED_COLS = [
    "id", "order_time", "order_type", "keeper", "goods", "in_out",
    "order_amount", "payment_method", "status", "order_num", "keeper_num", "extra",
]


def clean_data(csv_path: str | None = None) -> pd.DataFrame:
    """读取 data/my_payment.csv，清洗后返回干净的 DataFrame。

    清洗步骤：
        1. 时间转换  |  2. 金额转换  |  3. goods 占位符
        4. 文本清洗  |  5. keeper前缀  |  6. 退款标记
        7. 去重      |  8. 重编 id    |  9. 时间派生 + 质量报告
    """
    if csv_path is None:
        csv_path = str(DATA_DIR / "my_payment.csv")

    if not Path(csv_path).exists():
        print(f"[清洗] {csv_path} 不存在，返回空 DataFrame")
        return pd.DataFrame(columns=UNIFIED_COLS)

    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str)

    # 1. 时间转换
    df["order_time"] = pd.to_datetime(df["order_time"], dayfirst=False, format="mixed", errors="coerce")

    # 2. 金额转换
    df["order_amount"] = (
        df["order_amount"].astype(str)
        .str.replace("\xa5", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    df["order_amount"] = pd.to_numeric(df["order_amount"], errors="coerce").fillna(0)
    df["signed_amount"] = df["order_amount"] * np.where(df["in_out"] == "支出", -1, 1)

    # 3. goods '/' → ''
    df["goods"] = df["goods"].fillna("").replace("/", "")

    # 4. 文本清洗
    for col in ["keeper", "goods", "extra", "payment_method", "order_type", "status"]:
        if col in df.columns:
            df[col] = df[col].astype(str).fillna("")
            df[col] = (
                df[col]
                .str.replace(r"[\n\r\t]+", " ", regex=True)
                .str.replace(r"\s+", " ", regex=True)
                .str.strip()
            )

    # 5. keeper "发给" 前缀
    df["keeper"] = df["keeper"].str.replace(r"^发给", "", regex=True).str.strip()

    # 6. 退款标记
    df["is_refund"] = (
        df["order_type"].str.contains("退款", na=False)
        | df["status"].str.contains("退款", na=False)
    )

    # 7. 去重 (仅对 order_num 非空的行去重，空订单号的行全部保留)
    is_na = df["order_num"].isna()
    str_val = df["order_num"].astype(str).str.strip()
    is_empty_str = str_val.isin(["", "nan", "NaN", "None", "NaT", "/"])
    mask_empty = is_na | is_empty_str
    df_empty = df[mask_empty]
    df_non_empty = df[~mask_empty]
    dup_count = int(df_non_empty["order_num"].duplicated().sum())
    if dup_count > 0:
        df_non_empty = df_non_empty.drop_duplicates(subset="order_num", keep="first")
    df = pd.concat([df_empty, df_non_empty], ignore_index=True)

    # 8. id
    df["id"] = pd.Series(range(1, len(df) + 1), dtype=str)

    # 9. 时间派生
    df["month"] = df["order_time"].dt.to_period("M")
    df["weekday"] = df["order_time"].dt.day_name()
    df["hour"] = df["order_time"].dt.hour

    # 10. 质量报告
    _print_report(df, dup_count)

    return df


def show_df(df, rows=10, start=0, cols=None, max_col_width=30):
    subset = df.iloc[start: start + rows].copy()
    if cols:
        subset = subset[cols]
    for col in subset.select_dtypes(include=["object", "string"]).columns:
        subset[col] = subset[col].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        subset[col] = subset[col].apply(lambda x: x[:max_col_width] + "..." if len(x) > max_col_width else x)
    print(tabulate(subset, headers="keys", tablefmt="psql", showindex=True))


def _print_report(df: pd.DataFrame, dup_count: int) -> None:
    na_time = int(df["order_time"].isna().sum())
    na_amount = int(df["order_amount"].isna().sum())
    refund_count = int(df["is_refund"].sum())
    goods_empty = int((df["goods"] == "").sum())
    has_time = df["order_time"].notna()
    date_min = df.loc[has_time, "order_time"].min()
    date_max = df.loc[has_time, "order_time"].max()

    print("========== 数据质量报告 ==========")
    print(f"总行数: {len(df)}")
    print(f"时间解析失败 (NaT): {na_time} 条")
    print(f"金额解析失败 (NaN): {na_amount} 条")
    print(f"退款交易标记: {refund_count} 条")
    print(f"goods为空（原'/'占位符）: {goods_empty} 条")
    print(f"重复order_num已删除: {dup_count} 条")
    print(f"日期范围: {date_min} 至 {date_max}")
    if "source" in df.columns:
        print(f"来源: {dict(df['source'].value_counts())}")
    print("==================================")


if __name__ == "__main__":
    df = clean_data()
    show_df(df, rows=5, start=100)
