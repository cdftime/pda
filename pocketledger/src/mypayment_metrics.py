"""
支付数据计算指标模块。

每个函数 = 纯数据计算，输入 DataFrame/Series，输出 dict。
无 matplotlib / plotly 依赖，可被 Notebook、FastAPI、CLI 复用。
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _load_keywords() -> tuple[dict[str, str], dict[str, str]]:
    """从 JSON 配置文件加载分类关键词；文件不存在时回退到内置默认值。"""
    _DEFAULT_COARSE: dict[str, list[str]] = {
        "餐饮": ["食堂", "餐厅", "饭店", "小吃", "奶茶", "咖啡", "麻辣烫", "火锅", "烧烤", "美团", "饿了么", "肯德基", "麦当劳", "水果", "面包", "早餐", "午餐", "晚餐", "鸡排", "鸡公煲", "炸鸡", "卤味饭", "拉面", "粉面", "煎饼", "包子", "瓦罐", "猪脚饭", "盒饭", "牛肉饭", "拌饭", "盖饭"],
        "交通出行": ["出行", "单车", "哈啰", "滴滴", "打车", "地铁", "公交", "火车", "飞机", "加油", "充电", "停车"],
        "购物娱乐": ["淘宝", "天猫", "京东", "拼多多", "唯品会", "Steam", "游戏", "影城", "电影", "KTV", "演出", "会员", "游戏充值"],
        "通讯网络": ["话费", "流量", "宽带", "中国移动", "中国联通", "中国电信"],
        "生活缴费": ["电费", "水费", "燃气", "物业", "房租", "还花呗", "信用卡"],
        "其他": [],
    }
    _DEFAULT_FINE: dict[str, list[str]] = {
        "共享单车": ["大哈出行", "杭州青奇", "街兔"],
        "学校食堂": ["华东交通大学合作食堂"],
        "外卖": ["美团", "饿了么"],
        "网购": ["淘宝", "天猫", "京东", "拼多多", "唯品会"],
        "游戏娱乐": ["原神", "Steam", "宽娱", "bili", "B站"],
        "话费充值": ["中国移动", "中国联通", "中国电信", "话费充值", "手机充值"],
        "交通出行": ["中铁网络", "恒达汽运", "公交", "地铁", "火车", "打车", "滴滴"],
        "超市零食": ["国莲超市", "赵一鸣", "校园超市", "零食", "量贩"],
        "餐饮小食": ["包子铺", "瓦罐汤", "鸡公煲", "猪脚饭", "麻辣", "火锅", "烧烤", "奶茶", "咖啡", "水果", "面包"],
        "其他": [],
    }

    config_path = Path(__file__).parent / "category_keywords.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        coarse = {k: "|".join(v) for k, v in cfg.get("coarse", _DEFAULT_COARSE).items()}
        fine = {k: "|".join(v) for k, v in cfg.get("fine", _DEFAULT_FINE).items()}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        coarse = {k: "|".join(v) for k, v in _DEFAULT_COARSE.items()}
        fine = {k: "|".join(v) for k, v in _DEFAULT_FINE.items()}
    return coarse, fine


CATEGORY_KEYWORDS, FINE_CATEGORY_KEYWORDS = _load_keywords()


# ═══════════════════════════════════════════════════════════════════════════════
# 0. 时间字段增强（清洗之后的第一步）
# ═══════════════════════════════════════════════════════════════════════════════

def enrich_time_fields(df: pd.DataFrame) -> pd.DataFrame:
    """为 DataFrame 添加时间派生列，返回修改后的 df（会原地修改）。"""
    if len(df) == 0:
        for col in ["year", "month", "year_month_str", "month_num", "weekday", "hour"]:
            if col not in df.columns:
                df[col] = pd.Series(dtype="object")
        return df
    df["year"] = df["order_time"].dt.year
    df["month"] = df["order_time"].dt.to_period("M")
    df["year_month_str"] = df["order_time"].dt.strftime("%Y-%m")
    df["month_num"] = df["order_time"].dt.month
    df["weekday"] = df["order_time"].dt.day_name()
    df["hour"] = df["order_time"].dt.hour
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 月度收支汇总
# ═══════════════════════════════════════════════════════════════════════════════

def compute_monthly_stats(df: pd.DataFrame) -> dict[str, Any]:
    """月度收入 / 支出 / 结余 / 环比 / 同比。

    Returns
    -------
    dict 包含:
        monthly_income   : Series (PeriodIndex)
        monthly_expense  : Series (PeriodIndex)
        monthly_balance  : DataFrame (收入, 支出, 结余)
        mom_change       : Series (环比 %)
        yoy_change       : Series (同比 %)
    """
    if len(df) == 0:
        es = pd.Series(dtype=float)
        return {"monthly_income": es, "monthly_expense": es, "monthly_balance": pd.DataFrame({"收入": es, "支出": es, "结余": es}), "mom_change": es, "yoy_change": es}
    income = df[df["in_out"] == "收入"].groupby("month")["order_amount"].sum()
    expense = df[df["in_out"] == "支出"].groupby("month")["order_amount"].sum()

    income.index = pd.PeriodIndex(income.index, freq="M")
    expense.index = pd.PeriodIndex(expense.index, freq="M")

    balance = (
        pd.concat([income.rename("收入"), expense.rename("支出")], axis=1)
        .fillna(0)
        .sort_index()
    )
    balance["结余"] = balance["收入"] - balance["支出"]

    # 环比 & 同比
    expense_str = expense.copy()
    expense_str.index = expense_str.index.astype(str)
    mom = expense_str.pct_change() * 100
    yoy = expense_str.pct_change(12) * 100

    return {
        "monthly_income": income,
        "monthly_expense": expense,
        "monthly_balance": balance,
        "mom_change": mom,
        "yoy_change": yoy,
    }


def compute_asset_trend(
    monthly_income: pd.Series | None = None,
    monthly_expense: pd.Series | None = None,
    monthly_balance: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """累计资产趋势（初始资产为 0）。

    可传入 monthly_income + monthly_expense，或直接传入 compute_monthly_stats 的 monthly_balance。
    """
    if monthly_balance is not None:
        cashflow = monthly_balance[["收入", "支出"]].copy()
    elif monthly_income is not None and monthly_expense is not None:
        cashflow = (
            pd.concat(
                [monthly_income.rename("收入"), monthly_expense.rename("支出")], axis=1
            )
            .fillna(0)
            .sort_index()
        )
    else:
        raise ValueError("请提供 (monthly_income, monthly_expense) 或 monthly_balance")
    cashflow["净现金流"] = cashflow["收入"] - cashflow["支出"]
    cashflow["资产"] = cashflow["净现金流"].cumsum()
    return cashflow


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 年度 Top 3 月份
# ═══════════════════════════════════════════════════════════════════════════════

def compute_yearly_top3(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """每年各指标的 Top 3 月份。"""
    if len(df) == 0:
        return {"top3_income": pd.DataFrame(), "top3_expense": pd.DataFrame(), "top3_balance": pd.DataFrame(), "top3_trans": pd.DataFrame()}
    monthly_full = (
        df.groupby(["year", "year_month_str"])
        .agg(
            收入=(
                "order_amount",
                lambda x: x[df.loc[x.index, "in_out"] == "收入"].sum(),
            ),
            支出=(
                "order_amount",
                lambda x: x[df.loc[x.index, "in_out"] == "支出"].sum(),
            ),
            交易次数=("order_amount", "count"),
        )
        .fillna(0)
        .reset_index()
    )
    monthly_full["结余"] = monthly_full["收入"] - monthly_full["支出"]

    def _top3(data: pd.DataFrame, col: str) -> pd.DataFrame:
        parts = []
        for year, grp in data.groupby("year"):
            t3 = grp.nlargest(3, col).copy()
            t3["年份"] = year
            parts.append(t3)
        return pd.concat(parts, ignore_index=True)

    return {
        "top3_income": _top3(monthly_full, "收入"),
        "top3_expense": _top3(monthly_full, "支出"),
        "top3_balance": _top3(monthly_full, "结余"),
        "top3_trans": _top3(monthly_full, "交易次数"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 星期 & 时段统计
# ═══════════════════════════════════════════════════════════════════════════════

WEEKDAY_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]
WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def compute_weekday_stats(df: pd.DataFrame) -> pd.DataFrame:
    """按星期统计支出。"""
    return (
        df[df["in_out"] == "支出"]
        .groupby("weekday")
        .agg(
            总支出=("order_amount", "sum"),
            平均单笔=("order_amount", "mean"),
            交易笔数=("order_amount", "count"),
        )
        .reindex(WEEKDAY_ORDER)
    )


def compute_hourly_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    """星期 × 小时 支出热力图数据（保证 0-23 小时列完整）。"""
    if len(df) == 0:
        return pd.DataFrame(0.0, index=WEEKDAY_ORDER, columns=range(24))
    pivot = (
        df[df["in_out"] == "支出"]
        .pivot_table(
            values="order_amount",
            index="weekday",
            columns="hour",
            aggfunc="sum",
            fill_value=0,
        )
        .reindex(WEEKDAY_ORDER)
    )
    # 确保 0-23 小时全部有列（凌晨无消费的时段也要显示）
    for h in range(24):
        if h not in pivot.columns:
            pivot[h] = 0.0
    return pivot.reindex(columns=sorted(pivot.columns))


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 消费分类（粗分类 & 细分类）
# 关键词由 _load_keywords() 从 category_keywords.json 加载，文件缺失时使用内置回退。
# ═══════════════════════════════════════════════════════════════════════════════


def _classify(text: str, keywords: dict[str, str]) -> str:
    text = text.lower()
    for cat, kw in keywords.items():
        if kw and pd.notna(text) and any(k in text for k in kw.split("|")):
            return cat
    return "其他"


def classify_expenses(df: pd.DataFrame) -> dict[str, Any]:
    """粗分类：为每条支出分配类别，返回汇总。"""
    df_exp = df[df["in_out"] == "支出"].copy()
    df_exp["category"] = df_exp.apply(
        lambda r: _classify(f"{r['goods']} {r['keeper']}", CATEGORY_KEYWORDS),
        axis=1,
    )
    amt = df_exp.groupby("category")["order_amount"].sum().sort_values(ascending=False)
    cnt = (
        df_exp.groupby("category")["order_amount"]
        .count()
        .rename("count")
        .sort_values(ascending=False)
    )
    return {
        "df_expense": df_exp,
        "category_amount": amt,
        "category_count": cnt,
    }


def classify_expenses_fine(df: pd.DataFrame) -> pd.DataFrame:
    """细分类：为每条支出分配细化类别，返回带 fine_category 列的支出 DataFrame。"""
    df_exp = df[df["in_out"] == "支出"].copy()
    df_exp["fine_category"] = df_exp.apply(
        lambda r: _classify(f"{r['goods']} {r['keeper']}", FINE_CATEGORY_KEYWORDS),
        axis=1,
    )
    return df_exp


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 财务健康指标
# ═══════════════════════════════════════════════════════════════════════════════

def compute_financial_indicators(
    df: pd.DataFrame,
    monthly_expense: pd.Series,
    category_amount: pd.Series,
) -> dict[str, float]:
    """计算 8 项财务指标。"""
    if len(df) == 0:
        return {"total_income": 0.0, "total_expense": 0.0, "net": 0.0, "engel": 0.0, "saving_rate": 0.0, "top3_concentration": 0.0, "cv": 0.0, "diversity": 0.0}
    """核心财务指标。"""
    total_income = df[df["in_out"] == "收入"]["order_amount"].sum()
    total_expense = df[df["in_out"] == "支出"]["order_amount"].sum()
    net = total_income - total_expense

    food = category_amount.get("餐饮", 0)
    engel = float(food / total_expense) if total_expense > 0 else 0.0
    saving_rate = float(net / total_income) if total_income > 0 else 0.0
    top3_conc = (
        float(category_amount.head(3).sum() / total_expense)
        if total_expense > 0
        else 0.0
    )
    cv = (
        float(monthly_expense.std() / monthly_expense.mean())
        if monthly_expense.mean() > 0 and len(monthly_expense) >= 2
        else 0.0
    )

    probs = category_amount / category_amount.sum()
    diversity = float(-np.sum(probs * np.log(probs + 1e-12)))

    return {
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "net": float(net),
        "engel": engel,
        "saving_rate": saving_rate,
        "top3_concentration": top3_conc,
        "cv": cv,
        "diversity": diversity,
    }


def compute_health_score(
    saving_rate: float,
    engel: float,
    monthly_expense: pd.Series,
    budget: float = 1500,
    cv: float | None = None,
) -> dict[str, Any]:
    """综合财务健康评分（0-100）。

    可传入 compute_financial_indicators 中已算好的 cv 避免重复计算。
    """

    def _score_saving(r: float) -> int:
        if r >= 0.3: return 100
        if r >= 0.2: return 80
        if r >= 0.1: return 60
        if r >= 0:   return 40
        return 20

    def _score_engel(r: float) -> int:
        if r <= 0.3: return 100
        if r <= 0.4: return 80
        if r <= 0.5: return 60
        if r <= 0.6: return 40
        return 20

    def _score_budget(dev: float) -> int:
        if dev <= 0.1: return 100
        if dev <= 0.2: return 80
        if dev <= 0.3: return 60
        if dev <= 0.5: return 40
        return 20

    def _score_cv(cv: float) -> int:
        if cv <= 0.2: return 100
        if cv <= 0.4: return 80
        if cv <= 0.6: return 60
        if cv <= 1.0: return 40
        return 20

    dev = ((monthly_expense - budget) / budget).abs().mean()
    if pd.isna(dev):
        dev = 1.0  # 无数据时默认 100% 偏差
    if cv is None:
        cv = float(
            monthly_expense.std() / monthly_expense.mean()
            if monthly_expense.mean() > 0
            else 0.0
        )

    s1, s2, s3, s4 = (
        _score_saving(saving_rate),
        _score_engel(engel),
        _score_budget(dev),
        _score_cv(cv),
    )
    total = s1 * 0.35 + s2 * 0.25 + s3 * 0.25 + s4 * 0.15

    if total >= 80:
        grade = "优秀，财务状态稳健"
    elif total >= 60:
        grade = "良好，有一定优化空间"
    elif total >= 40:
        grade = "一般，需要关注预算和支出结构"
    else:
        grade = "较差，建议尽快调整消费习惯"

    return {
        "total_score": round(total, 1),
        "grade": grade,
        "saving_rate": saving_rate,
        "engel": engel,
        "budget_deviation": float(dev),
        "expense_cv": cv,
        "sub_scores": {"saving": s1, "engel": s2, "budget": s3, "cv": s4},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 商户 RFM
# ═══════════════════════════════════════════════════════════════════════════════

def compute_merchant_rfm(df_expense: pd.DataFrame) -> dict[str, Any]:
    """商户 RFM 分析。

    Parameters
    ----------
    df_expense : 仅含支出行的 DataFrame，需有 category 列（先调 classify_expenses）。

    Returns
    -------
    dict 包含 rfm, top10_amount, top10_count
    """
    if len(df_expense) == 0:
        empty = pd.DataFrame(columns=["keeper", "recency", "frequency", "monetary"])
        return {"rfm": empty, "top10_amount": empty[["keeper", "monetary"]], "top10_count": empty[["keeper", "frequency"]]}
    now = df_expense["order_time"].max()
    rfm = (
        df_expense.groupby("keeper")
        .agg(
            recency=("order_time", lambda x: (now - x.max()).days),
            frequency=("order_time", "count"),
            monetary=("order_amount", "sum"),
        )
        .reset_index()
    )

    top10_amt = rfm.nlargest(10, "monetary")[
        ["keeper", "monetary"]
    ].reset_index(drop=True)
    top10_cnt = rfm.nlargest(10, "frequency")[
        ["keeper", "frequency"]
    ].reset_index(drop=True)

    return {
        "rfm": rfm,
        "top10_amount": top10_amt,
        "top10_count": top10_cnt,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 7. 异常大额消费检测
# ═══════════════════════════════════════════════════════════════════════════════

def detect_anomalies(
    df: pd.DataFrame, sigma: float = 3.0
) -> dict[str, Any]:
    """均值 + N*σ 异常检测。"""
    if len(df) == 0:
        return {"threshold": 0.0, "mean": 0.0, "std": 0.0, "count": 0, "anomalies": pd.DataFrame(columns=["order_time", "keeper", "goods", "order_amount"])}
    detail = df[df["in_out"] == "支出"]["order_amount"]
    mean_v = float(detail.mean())
    std_v = float(detail.std())
    threshold = mean_v + sigma * std_v

    anomalies = df[
        (df["in_out"] == "支出") & (df["order_amount"] > threshold)
    ][["order_time", "keeper", "goods", "order_amount"]].sort_values(
        "order_amount", ascending=False
    )

    return {
        "threshold": round(threshold, 2),
        "mean": round(mean_v, 2),
        "std": round(std_v, 2),
        "count": len(anomalies),
        "anomalies": anomalies.reset_index(drop=True),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 8. 时间序列分解
# ═══════════════════════════════════════════════════════════════════════════════

def decompose_timeseries(
    monthly_expense: pd.Series, period: int = 12
) -> dict[str, Any]:
    """STL 分解为趋势 / 季节 / 残差。"""
    if len(monthly_expense) < 12:
        return {"observed": [], "trend": [], "seasonal": [], "resid": [], "dates": []}
    from statsmodels.tsa.seasonal import seasonal_decompose

    ts = monthly_expense.sort_index()
    ts.index = ts.index.to_timestamp()
    dec = seasonal_decompose(ts, model="additive", period=period)

    def _to_records(s: pd.Series) -> list[dict]:
        return [
            {"date": str(idx.date()), "value": round(float(v), 2)}
            for idx, v in s.dropna().items()
        ]

    return {
        "observed": _to_records(dec.observed),
        "trend": _to_records(dec.trend),
        "seasonal": _to_records(dec.seasonal),
        "resid": _to_records(dec.resid),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Prophet 预测
# ═══════════════════════════════════════════════════════════════════════════════

def forecast_expense(
    monthly_expense: pd.Series, periods: int = 8
) -> dict[str, Any]:
    """Prophet 未来支出预测。"""
    if len(monthly_expense) < 2:
        return {"last_train_date": None, "forecast": [], "full_forecast_df": pd.DataFrame()}
    from prophet import Prophet

    df_p = monthly_expense.reset_index()
    df_p.columns = ["ds", "y"]
    df_p["ds"] = df_p["ds"].dt.to_timestamp()

    model = Prophet(yearly_seasonality=True, weekly_seasonality=False)
    model.fit(df_p)
    future = model.make_future_dataframe(periods=periods, freq="ME")
    forecast = model.predict(future)

    last_date = df_p["ds"].max()
    future_part = forecast[forecast["ds"] > last_date][
        ["ds", "yhat", "yhat_lower", "yhat_upper"]
    ]

    return {
        "last_train_date": str(last_date.date()),
        "forecast": [
            {
                "ds": str(r["ds"].date()),
                "yhat": round(float(r["yhat"]), 2),
                "yhat_lower": round(float(r["yhat_lower"]), 2),
                "yhat_upper": round(float(r["yhat_upper"]), 2),
            }
            for _, r in future_part.iterrows()
        ],
        "full_forecast_df": forecast,  # 供 notebook 绘图用
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 10. 节假日消费分析
# ═══════════════════════════════════════════════════════════════════════════════

def _build_holiday_map() -> dict[date, str]:
    """构建日期 → 节日名称映射（2023-2026）。"""
    hmap: dict[date, str] = {}

    chunjie = {
        2023: ("2023-01-21", "2023-01-27"),
        2024: ("2024-02-09", "2024-02-15"),
        2025: ("2025-01-28", "2025-02-03"),
        2026: ("2026-02-17", "2026-02-23"),
    }
    for s, e in chunjie.values():
        for d in pd.date_range(s, e):
            hmap[d.date()] = "春节"

    for y in [2023, 2024, 2025, 2026]:
        for day in range(1, 6):
            hmap[date(y, 5, day)] = "劳动节"
        for day in range(1, 8):
            hmap[date(y, 10, day)] = "国庆节"
        hmap[date(y, 1, 1)] = "元旦"
        hmap[date(y, 2, 14)] = "情人节"
        hmap[date(y, 6, 18)] = "618"
        hmap[date(y, 11, 11)] = "双十一"
        hmap[date(y, 12, 12)] = "双十二"

    for y, (m, d) in {2023: (4, 5), 2024: (4, 4), 2025: (4, 4), 2026: (4, 5)}.items():
        hmap[date(y, m, d)] = "清明节"
    for y, (m, d) in {2023: (6, 22), 2024: (6, 10), 2025: (5, 31), 2026: (6, 19)}.items():
        hmap[date(y, m, d)] = "端午节"
    for y, (m, d) in {2023: (9, 29), 2024: (9, 17), 2025: (10, 6), 2026: (9, 25)}.items():
        hmap[date(y, m, d)] = "中秋节"
    for y, (m, d) in {2023: (8, 22), 2024: (8, 10), 2025: (8, 29), 2026: (8, 19)}.items():
        hmap[date(y, m, d)] = "七夕"

    return hmap


def compute_holiday_stats(df: pd.DataFrame) -> dict[str, Any]:
    """节假日 vs 非节假日消费对比。"""
    if len(df) == 0:
        empty_h = {"周数": 0, "平均周总支出": 0.0, "平均交易笔数": 0.0, "平均日均支出": 0.0}
        return {"total_stats": {"节假日周": empty_h, "非节假日周": empty_h}, "per_holiday": []}
    hmap = _build_holiday_map()
    df = df.copy()
    df["date"] = df["order_time"].dt.date
    df["holiday_name"] = df["date"].map(hmap).fillna("非节日")
    df["year_week"] = df["order_time"].dt.strftime("%G-%V")

    weekly = (
        df[df["in_out"] == "支出"]
        .groupby("year_week")
        .agg(
            周总支出=("order_amount", "sum"),
            交易笔数=("order_amount", "count"),
            节日=(
                "holiday_name",
                lambda x: x[x != "非节日"].iloc[0]
                if (x != "非节日").any()
                else "非节日",
            ),
        )
        .reset_index()
    )
    weekly["日均支出"] = weekly["周总支出"] / 7
    weekly["是否节假日"] = weekly["节日"] != "非节日"

    hw = weekly[weekly["是否节假日"]]
    nhw = weekly[~weekly["是否节假日"]]

    total_stats = {
        "节假日周": {
            "周数": len(hw),
            "平均周总支出": round(float(hw["周总支出"].mean()), 2),
            "平均交易笔数": round(float(hw["交易笔数"].mean()), 2),
            "平均日均支出": round(float(hw["日均支出"].mean()), 2),
        },
        "非节假日周": {
            "周数": len(nhw),
            "平均周总支出": round(float(nhw["周总支出"].mean()), 2),
            "平均交易笔数": round(float(nhw["交易笔数"].mean()), 2),
            "平均日均支出": round(float(nhw["日均支出"].mean()), 2),
        },
    }

    per_holiday = (
        hw.groupby("节日")
        .agg(
            周数=("周总支出", "count"),
            平均周总支出=("周总支出", "mean"),
            平均交易笔数=("交易笔数", "mean"),
            平均日均支出=("日均支出", "mean"),
        )
        .reset_index()
    )

    return {
        "total_stats": total_stats,
        "per_holiday": per_holiday.to_dict(orient="records"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 11. 社交资金流向
# ═══════════════════════════════════════════════════════════════════════════════

def compute_social_transfers(df: pd.DataFrame) -> pd.DataFrame:
    """提取转账/红包数据，计算每人净盈余与总频次。"""
    tf = df[df["order_type"].str.contains("转账|红包", na=False)].copy()
    tf["keeper"] = tf["keeper"].str.strip()

    stats = (
        tf.groupby(["keeper", "in_out"])["order_amount"]
        .agg(["sum", "count"])
        .reset_index()
    )
    stats.columns = ["keeper", "in_out", "总金额", "频次"]

    net = stats.pivot(index="keeper", columns="in_out", values="总金额").fillna(0)
    net["盈余"] = net.get("收入", 0) - net.get("支出", 0)
    freq = stats.pivot(index="keeper", columns="in_out", values="频次").fillna(0)
    freq["总频次"] = freq.get("收入", 0) + freq.get("支出", 0)

    result = (
        pd.concat([net["盈余"], freq["总频次"]], axis=1)
        .reset_index()
    )
    result.columns = ["keeper", "盈余", "总频次"]
    return result[(result["盈余"] != 0) | (result["总频次"] != 0)].reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 12. 关联规则（可选，计算较重）
# ═══════════════════════════════════════════════════════════════════════════════

_association_cache: dict | None = None  # 缓存 classify_expenses_fine 结果


def compute_association_rules(
    df: pd.DataFrame,
    min_support: float = 0.05,
    min_confidence: float = 0.3,
    level: str = "merchant",
) -> dict[str, Any]:
    """关联规则挖掘（按周购物篮）。

    Parameters
    ----------
    level : str
        "merchant" = 商户级别（按 keeper 聚合，指导性最强）。
        "category" = 消费细分类别级别（粗粒度模式）。
        "goods"    = 商品级别（按 goods 字段聚合，发现具体商品共现）。

    需要 mlxtend 包。
    """
    if len(df) == 0:
        return {"count": 0, "rules": pd.DataFrame(columns=["antecedents","consequents","support","confidence","lift"])}
    from mlxtend.frequent_patterns import apriori, association_rules

    global _association_cache
    cache_key = f"{level}_{id(df)}"
    if _association_cache is not None and _association_cache.get("id") == cache_key:
        df_exp = _association_cache["data"]
        basket_key = _association_cache.get("basket_key", "")
    else:
        if level == "merchant":
            df_exp = df[df["in_out"] == "支出"].copy()
            basket_key = "keeper"
        elif level == "goods":
            df_exp = df[df["in_out"] == "支出"].copy()
            # 清洗 goods：去除转账备注/二维码收款等噪音
            df_exp["_goods_clean"] = (
                df_exp["goods"].astype(str)
                .str.replace(r"^转账备注[:：]\s*", "", regex=True)
                .str.replace(r"^收款方备注[:：]\s*", "", regex=True)
                .str.replace(r"^Weixin\w+", "", regex=True)
                .str.replace(r"\b[a-zA-Z0-9]{20,}\b", "", regex=True)
                .str.strip()
            )
            # 过滤空商品名
            df_exp = df_exp[df_exp["_goods_clean"] != ""]
            # 合并商户名+商品名作为购物篮项（更有辨识度）
            df_exp["_keeper_goods"] = (
                df_exp["keeper"].str.strip().str.slice(0, 15) + "·"
                + df_exp["_goods_clean"].str.strip().str.slice(0, 25)
            )
            basket_key = "_keeper_goods"
        else:
            df_exp = classify_expenses_fine(df)
            basket_key = "fine_category"
        _association_cache = {"id": cache_key, "data": df_exp, "basket_key": basket_key}

    df_exp["year"] = df_exp["order_time"].dt.year
    df_exp["week"] = df_exp["order_time"].dt.isocalendar().week.astype(int)
    df_exp["year_week"] = (
        df_exp["year"].astype(str) + "-W" + df_exp["week"].astype(str)
    )

    bk = _association_cache.get("basket_key", basket_key)
    basket = (
        df_exp.groupby(["year_week", bk])["order_amount"]
        .count()
        .unstack(fill_value=0)
        .astype(bool)
    )

    # 动态参数
    if level == "merchant":
        min_weeks, sup, conf, min_lift = 5, max(0.03, min_support), max(0.5, min_confidence), 2.5
        single_item_only = True
    elif level == "goods":
        min_weeks, sup, conf, min_lift = 3, max(0.02, min_support), max(0.35, min_confidence), 1.5
        single_item_only = True
    else:
        min_weeks, sup, conf, min_lift = 3, max(0.03, min_support), max(0.35, min_confidence), 1.2
        single_item_only = True

    # 过滤低频项
    freq_items = basket.sum()[basket.sum() >= min_weeks].index
    if len(freq_items) < 2:
        return {"count": 0, "rules": pd.DataFrame(columns=["antecedents","consequents","support","confidence","lift"])}
    basket = basket[freq_items]

    itemsets = apriori(basket, min_support=sup, use_colnames=True)
    if len(itemsets) < 2:
        return {"count": 0, "rules": pd.DataFrame(columns=["antecedents","consequents","support","confidence","lift"])}

    rules = association_rules(itemsets, metric="confidence", min_threshold=conf)
    rules = rules.replace([np.inf, -np.inf], np.nan).dropna(subset=["lift"])
    rules = rules[rules["lift"] > min_lift]

    if single_item_only:
        rules = rules[rules["antecedents"].apply(len) == 1]
        rules = rules[rules["consequents"].apply(len) == 1]

    rules = rules.sort_values("lift", ascending=False)

    rules["antecedents_str"] = rules["antecedents"].apply(lambda x: ", ".join(x))
    rules["consequents_str"] = rules["consequents"].apply(lambda x: ", ".join(x))

    return {
        "count": len(rules),
        "rules": rules.reset_index(drop=True),
    }
# ═══════════════════════════════════════════════════════════════════════════════
# 13. 筛选器 / 辅助 (Cell A)
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_category(df: pd.DataFrame) -> None:
    """如果 df 没有 category 列则就地补充。"""
    if "category" not in df.columns:
        df["category"] = df.apply(
            lambda r: _classify(f"{r.get('goods','')} {r.get('keeper','')}", CATEGORY_KEYWORDS),
            axis=1,
        )

def filter_dataframe(
    df: pd.DataFrame,
    years: list | None = None,
    months: list | None = None,
    categories: list | None = None,
    inout: str = "全部",
    amount_min: float | None = None,
    amount_max: float | None = None,
) -> dict[str, Any]:
    """按条件筛选 df，返回 df_view + df_expense_view。

    在 Notebook 中可修改变量后重跑 Cell A；
    在 API 中直接传入参数即可。
    """
    mask = pd.Series(True, index=df.index)
    if years:
        mask &= df["year"].isin(years)
    if months:
        mask &= df["month_num"].isin(months)
    if categories and "category" in df.columns:
        mask &= df["category"].fillna("其他").isin(categories)
    if amount_min is not None:
        mask &= df["order_amount"] >= amount_min
    if amount_max is not None:
        mask &= df["order_amount"] <= amount_max
    if inout == "仅支出":
        mask &= df["in_out"] == "支出"
    elif inout == "仅收入":
        mask &= df["in_out"] == "收入"

    df_view = df[mask].copy()
    df_expense_view = df_view[df_view["in_out"] == "支出"].copy()

    return {
        "df_view": df_view,
        "df_expense_view": df_expense_view,
        "count": len(df_view),
        "total_count": len(df),
        "income_sum": float(df_view[df_view["in_out"] == "收入"]["order_amount"].sum()),
        "expense_sum": float(df_view[df_view["in_out"] == "支出"]["order_amount"].sum()),
    }


def get_filter_options(df: pd.DataFrame) -> dict[str, list]:
    """返回筛选器的可选值列表（供前端填充下拉框）。"""
    if len(df) == 0:
        return {"years": [], "months": list(range(1, 13)), "categories": [], "amount_min": 0.0, "amount_max": 0.0}
    cats = sorted(df["category"].dropna().unique()) if "category" in df.columns else []
    return {
        "years": sorted(df["year"].dropna().unique().astype(int).tolist()),
        "months": list(range(1, 13)),
        "categories": cats,
        "amount_min": float(df["order_amount"].min()),
        "amount_max": float(df["order_amount"].max()),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 14. 月度钻取数据 (Cell B)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_drill_month(df: pd.DataFrame, ym: str) -> dict[str, Any]:
    """钻取单月数据：每日支出、分类金额、Top 5 商户、环比/同比。

    Returns
    -------
    dict 可直接喂给 plot_drill_month() 或序列化为 JSON。
    """
    if len(df) == 0 or not ym:
        return {"ym": ym or "", "curr_total": 0.0, "curr_count": 0, "curr_avg": 0.0, "prev_ym": "", "prev_total": None, "yoy_ym": "", "yoy_total": None, "daily": {}, "category_pie": {}, "top5_merchants": {}}
    _ensure_category(df)
    m_df = df[(df["year_month_str"] == ym) & (df["in_out"] == "支出")]
    year = int(ym[:4])
    month = int(ym[5:7])

    prev_ym = f"{year}-{month - 1:02d}" if month > 1 else f"{year - 1}-12"
    yoy_ym = f"{year - 1}-{month:02d}"

    prev_df = df[(df["year_month_str"] == prev_ym) & (df["in_out"] == "支出")]
    yoy_df = df[(df["year_month_str"] == yoy_ym) & (df["in_out"] == "支出")]

    daily = (
        m_df.groupby(m_df["order_time"].dt.day)["order_amount"]
        .sum()
        .to_dict()
    )
    cat_pie = (
        m_df.groupby("category")["order_amount"]
        .sum()
        .sort_values(ascending=False)
        .to_dict()
    )
    top5 = (
        m_df.groupby("keeper")["order_amount"]
        .sum()
        .nlargest(5)
        .to_dict()
    )

    curr_total = float(m_df["order_amount"].sum()) if len(m_df) > 0 else 0.0
    curr_count = len(m_df)
    curr_avg = curr_total / curr_count if curr_count > 0 else 0.0
    prev_total = float(prev_df["order_amount"].sum()) if len(prev_df) > 0 else None
    yoy_total = float(yoy_df["order_amount"].sum()) if len(yoy_df) > 0 else None

    return {
        "ym": ym,
        "curr_total": curr_total,
        "curr_count": curr_count,
        "curr_avg": round(curr_avg, 2),
        "prev_ym": prev_ym,
        "prev_total": prev_total,
        "yoy_ym": yoy_ym,
        "yoy_total": yoy_total,
        "daily": {str(k): round(float(v), 2) for k, v in daily.items()},
        "category_pie": {str(k): round(float(v), 2) for k, v in cat_pie.items()},
        "top5_merchants": {str(k): round(float(v), 2) for k, v in top5.items()},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 15. 分类月度趋势数据 (Cell C)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_category_monthly_trend(df_expense: pd.DataFrame) -> dict[str, Any]:
    """构建分类月度 pivot 表（金额 / 笔数 / 占比），供趋势图使用。"""
    cat_monthly = df_expense.pivot_table(
        index="year_month_str", columns="category",
        values="order_amount", aggfunc="sum", fill_value=0,
    )
    top_cats = cat_monthly.sum().nlargest(6).index.tolist()
    cat_monthly_top = cat_monthly[top_cats]
    cat_monthly_pct = cat_monthly_top.div(cat_monthly_top.sum(axis=1), axis=0) * 100
    cat_monthly_cnt = df_expense.pivot_table(
        index="year_month_str", columns="category",
        values="order_amount", aggfunc="count", fill_value=0,
    )[top_cats]

    def _to_records(df_p):
        return [
            {"month": idx, **{c: round(float(df_p.at[idx, c]), 2) for c in df_p.columns}}
            for idx in df_p.index
        ]

    return {
        "top_categories": top_cats,
        "amount": _to_records(cat_monthly_top),
        "count": _to_records(cat_monthly_cnt),
        "pct": _to_records(cat_monthly_pct),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 16. 月度对比数据 (Cell D)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_month_comparison(df: pd.DataFrame, ym_a: str, ym_b: str) -> dict[str, Any]:
    """两个月份的全维度对比数据。"""
    # 确保 category 列存在
    _ensure_category(df)

    def _stats(ym: str) -> dict:
        m = df[(df["year_month_str"] == ym) & (df["in_out"] == "支出")]
        cats = m.groupby("category")["order_amount"].sum().to_dict() if "category" in m.columns else {}
        return {
            "total": float(m["order_amount"].sum()),
            "count": len(m),
            "avg": round(float(m["order_amount"].mean()), 2) if len(m) > 0 else 0.0,
            "cats": cats,
            "daily": m.groupby(m["order_time"].dt.day)["order_amount"].sum().to_dict(),
            "top5": m.groupby("keeper")["order_amount"].sum().nlargest(5).to_dict(),
            "week": {d: float(m[m["weekday"] == d]["order_amount"].sum()) for d in WEEKDAY_ORDER},
        }

    sa = _stats(ym_a)
    sb = _stats(ym_b)
    diff = sa["total"] - sb["total"]
    pct = (diff / sb["total"] * 100) if sb["total"] > 0 else 0.0

    cat_diffs = {}
    for c in set(list(sa["cats"]) + list(sb["cats"])):
        cat_diffs[c] = round(sa["cats"].get(c, 0) - sb["cats"].get(c, 0), 2)
    top_cat_diffs = sorted(cat_diffs.items(), key=lambda x: -abs(x[1]))[:3]

    return {
        "ym_a": ym_a, "ym_b": ym_b,
        "a": sa, "b": sb,
        "diff": round(diff, 2),
        "diff_pct": round(pct, 2),
        "diff_label": "多花了" if diff > 0 else "少花了" if diff < 0 else "持平",
        "top_diff_categories": [{"name": c, "diff": d} for c, d in top_cat_diffs],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 17. 预警相关（多样性趋势 + 环比异常）
# ═══════════════════════════════════════════════════════════════════════════════

def compute_diversity_trend(df_expense: pd.DataFrame) -> list[dict]:
    """消费多样性香农熵月度趋势。熵值下降 = 消费越来越集中。"""
    if "category" not in df_expense.columns or "year_month_str" not in df_expense.columns:
        return []
    monthly = df_expense.pivot_table(
        index="year_month_str", columns="category",
        values="order_amount", aggfunc="sum", fill_value=0,
    )
    result = []
    for idx, row in monthly.iterrows():
        probs = row.values / row.sum()
        h = float(-np.sum(probs * np.log(probs + 1e-12)))
        result.append({"month": str(idx), "diversity": round(h, 4)})
    return result


def detect_mom_anomalies(
    df_expense: pd.DataFrame,
    threshold: float = 0.5,
) -> list[dict]:
    """环比异常检测：某分类比上月增长超过阈值的月份。

    Returns: [{month, category, mom_pct, current, previous}, ...] 按变化率降序。
    """
    monthly = df_expense.pivot_table(
        index="year_month_str", columns="category",
        values="order_amount", aggfunc="sum", fill_value=0,
    )
    mom = monthly.pct_change()
    alerts = []
    for cat in mom.columns:
        for idx in mom.index:
            val = float(mom.at[idx, cat])
            if pd.isna(val) or np.isinf(val) or val <= threshold:
                continue
            cur = float(monthly.at[idx, cat])
            prev_idx = monthly.index[monthly.index.get_loc(idx) - 1]
            prev_val = float(monthly.at[prev_idx, cat])
            alerts.append({
                "month": str(idx), "category": str(cat),
                "mom_pct": round(val * 100, 1),
                "current": round(cur, 2),
                "previous": round(prev_val, 2),
            })
    alerts.sort(key=lambda x: -x["mom_pct"])
    return alerts


# ═══════════════════════════════════════════════════════════════════════════════
# 18. 一站式汇总（API 仪表板端点一键调用）
# ═══════════════════════════════════════════════════════════════════════════════

def compute_summary_dashboard(
    df: pd.DataFrame, budget: float = 1500
) -> dict[str, Any]:
    """一次调用返回前端仪表板所需的全部数据。

    内部串行调用各 compute_* 函数，避免重复计算。
    """
    _ensure_category(df)
    ms = compute_monthly_stats(df)
    ce = classify_expenses(df)
    fi = compute_financial_indicators(df, ms["monthly_expense"], ce["category_amount"])
    hs = compute_health_score(
        fi["saving_rate"], fi["engel"], ms["monthly_expense"],
        budget=budget, cv=fi["cv"],
    )
    rfm = compute_merchant_rfm(ce["df_expense"])
    an = detect_anomalies(df)
    dc = decompose_timeseries(ms["monthly_expense"])
    fc = forecast_expense(ms["monthly_expense"])
    ho = compute_holiday_stats(df)
    st = compute_social_transfers(df)
    ct = compute_category_monthly_trend(ce["df_expense"])

    # 最近月份钻取 & 对比
    all_yms = sorted(df["year_month_str"].dropna().unique()) if len(df) > 0 else []
    last_ym = all_yms[-1] if all_yms else None
    prev_ym = all_yms[-7] if len(all_yms) > 7 else all_yms[0] if all_yms else None
    drill = compute_drill_month(df, last_ym) if last_ym else None
    comp = compute_month_comparison(df, last_ym, prev_ym) if last_ym and prev_ym else None

    # weekday_stats: fill NaN (from reindex on empty df) for JSON serialization
    wds = compute_weekday_stats(df).fillna(0)

    return {
        "filter_options": get_filter_options(df),
        "financial": fi,
        "health_score": hs,
        "monthly_income": ms["monthly_income"].to_dict(),
        "monthly_expense": ms["monthly_expense"].to_dict(),
        "mom_change": {
            str(k): round(float(v), 2) if not np.isnan(v) else None
            for k, v in ms["mom_change"].items()
        },
        "yoy_change": {
            str(k): round(float(v), 2) if not np.isnan(v) else None
            for k, v in ms["yoy_change"].items()
        },
        "weekday_stats": wds.to_dict(),
        "rfm_top10": rfm["top10_amount"].to_dict(orient="records"),
        "anomalies_count": an["count"],
        "anomalies_threshold": an["threshold"],
        "decompose": dc,
        "forecast": fc["forecast"],
        "holiday_stats": ho["total_stats"],
        "social_transfers": st.to_dict(orient="records"),
        "category_trend": ct,
        "drill_month": drill,
        "comparison": comp,
    }
