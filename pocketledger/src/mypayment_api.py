"""
Web API 后端 —— 为前端仪表板提供 REST 数据接口。
启动: python mypayment_api.py
访问: http://localhost:8765
"""

from __future__ import annotations

# ── MUST be called before any asyncio-using import ──
import asyncio
import sys
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from datetime import datetime
import shutil
import traceback

from fastapi import FastAPI, Query, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent))

from mypayment_clean import clean_data
from mypayment_metrics import (
    enrich_time_fields,
    compute_monthly_stats,
    classify_expenses, compute_financial_indicators,
    compute_health_score, compute_merchant_rfm,
    detect_anomalies, decompose_timeseries,
    forecast_expense, compute_holiday_stats,
    compute_social_transfers,
    compute_drill_month, compute_month_comparison,
    compute_category_monthly_trend,
    compute_association_rules,
    filter_dataframe, get_filter_options,
)
# ═══════════════════════════════════════════════════════════
# 初始化
# ═══════════════════════════════════════════════════════════

import threading

app = FastAPI(title="个人财务分析仪表板", version="1.0")

# ── 心跳保活机制 ──
_last_heartbeat: float = time.time()
_heartbeat_lock = threading.Lock()


@app.post("/api/heartbeat")
async def api_heartbeat():
    global _last_heartbeat
    with _heartbeat_lock:
        _last_heartbeat = time.time()
    return {"status": "ok"}


def _heartbeat_watcher():
    """后台线程：每 10 秒检查心跳，超过 25 秒无心跳则退出。"""
    time.sleep(15)  # 启动后给浏览器 15 秒连接时间
    while True:
        time.sleep(10)
        with _heartbeat_lock:
            gap = time.time() - _last_heartbeat
        if gap > 25:
            print(f"\n浏览器心跳超时 ({gap:.0f}s)，自动退出...")
            os._exit(0)

STATIC = Path(__file__).parent.parent / "static"
STATIC.mkdir(exist_ok=True)

# ── 预加载数据（服务启动时只做清洗 + 时间增强 + 分类，<2 秒） ──
print("加载数据...")
_df = clean_data(str(Path(__file__).resolve().parent.parent / "data" / "my_payment.csv"))
_df = enrich_time_fields(_df)
from mypayment_metrics import _ensure_category
_ensure_category(_df)
if len(_df) == 0:
    print("⚠️ 未找到账单数据，请通过网页上传账单文件")
_SUMMARY_CACHE: dict[str, Any] = {}  # 仅缓存轻量级 summary


def _refresh_summary():
    """刷新概要缓存（轻量，不含 Prophet / STL / Apriori）。"""
    global _SUMMARY_CACHE
    if len(_df) == 0:
        _SUMMARY_CACHE = {"financial": {"total_income":0,"total_expense":0,"net":0,"engel":0,"saving_rate":0,"cv":0,"top3_concentration":0,"diversity":0}, "health_score": {"total_score":"—","grade":"暂无数据"}, "row_count": 0, "date_range": "—", "monthly_income": {}, "monthly_expense": {}, "weekday_stats": {}}
        return
    from mypayment_metrics import classify_expenses, compute_financial_indicators, compute_health_score, compute_monthly_stats
    ms = compute_monthly_stats(_df)
    ce = classify_expenses(_df)
    fi = compute_financial_indicators(_df, ms["monthly_expense"], ce["category_amount"])
    hs = compute_health_score(fi["saving_rate"], fi["engel"], ms["monthly_expense"], cv=fi["cv"])
    # 月度收支数据（供前端资产趋势 + 星期统计）
    inc_dict = {str(k): round(float(v), 2) for k, v in ms["monthly_income"].items()}
    exp_dict = {str(k): round(float(v), 2) for k, v in ms["monthly_expense"].items()}
    from mypayment_metrics import compute_weekday_stats
    wds = compute_weekday_stats(_df)
    wd_dict = {}
    for d in wds.index:
        total = float(wds.at[d, "总支出"]) if pd.notna(wds.at[d, "总支出"]) else 0.0
        avg = float(wds.at[d, "平均单笔"]) if pd.notna(wds.at[d, "平均单笔"]) else 0.0
        cnt = int(wds.at[d, "交易笔数"]) if pd.notna(wds.at[d, "交易笔数"]) else 0
        wd_dict[d] = {"总支出": round(total, 2), "平均单笔": round(avg, 2), "交易笔数": cnt}
    _SUMMARY_CACHE = {
        "financial": fi,
        "health_score": hs,
        "row_count": len(_df),
        "date_range": f"{_df['order_time'].min().date()} 至 {_df['order_time'].max().date()}",
        "monthly_income": inc_dict,
        "monthly_expense": exp_dict,
        "weekday_stats": wd_dict,
    }


_refresh_summary()
print(f"数据就绪：{len(_df)} 条记录")


# ═══════════════════════════════════════════════════════════
# 辅助：numpy/pandas → JSON 安全转换
# ═══════════════════════════════════════════════════════════

def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if np.isnan(v) or np.isinf(v) else v
    if isinstance(obj, float):
        return None if np.isnan(obj) or np.isinf(obj) else obj
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


# ═══════════════════════════════════════════════════════════
# 页面
# ═══════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/style.css")
async def style_css():
    return FileResponse(STATIC / "style.css", media_type="text/css")


@app.get("/app.js")
async def app_js():
    return FileResponse(STATIC / "app.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/api/refresh")
async def refresh():
    _refresh_summary()
    return {"status": "ok", "message": "概要数据已刷新"}


# ═══════════════════════════════════════════════════════════
# 核心 API
# ═══════════════════════════════════════════════════════════

@app.get("/api/dashboard")
async def api_dashboard():
    """完整仪表板（较重，按需调用）。"""
    from mypayment_metrics import compute_summary_dashboard
    return _json_safe(compute_summary_dashboard(_df))


@app.get("/api/summary")
async def api_summary():
    """概要：总收入/支出/结余 + 健康评分（启动即缓存，毫秒级响应）。"""
    return _json_safe(_SUMMARY_CACHE)


@app.get("/api/filter-options")
async def api_filter_options():
    return _json_safe(get_filter_options(_df))


@app.get("/api/filter")
async def api_filter(
    years: str = Query(None, description="逗号分隔，如 2024,2025"),
    months: str = Query(None, description="逗号分隔，如 1,2,3"),
    categories: str = Query(None, description="逗号分隔"),
    inout: str = Query("全部"),
    amount_min: float = Query(None),
    amount_max: float = Query(None),
):
    """筛选数据并返回汇总。"""
    years_list = [int(y) for y in years.split(",")] if years and years.strip() else None
    months_list = [int(m) for m in months.split(",")] if months and months.strip() else None
    cats_list = categories.split(",") if categories and categories.strip() else None
    result = filter_dataframe(
        _df,
        years=years_list,
        months=months_list,
        categories=cats_list,
        inout=inout,
        amount_min=amount_min,
        amount_max=amount_max,
    )
    # 不要返回整个 df，只返回汇总
    return _json_safe({
        "count": result["count"],
        "total_count": result["total_count"],
        "income_sum": result["income_sum"],
        "expense_sum": result["expense_sum"],
    })


# ── 月度数据 ──

@app.get("/api/asset-trend-full")
async def api_asset_trend_full():
    """包含转账/充值/提现的完整月度资产净流。

    Returns:
      months: [str]
      op_flow:  纯经营现金流 (收入-支出)
      total_flow: 总现金流 (含充值提现转账等不计收支项)
    """
    _df_copy = _df.copy()
    if "month" not in _df_copy.columns:
        from mypayment_metrics import enrich_time_fields
        _df_copy = enrich_time_fields(_df_copy)

    # Operating flow
    inc = _df_copy[_df_copy["in_out"] == "收入"].groupby("month")["order_amount"].sum()
    exp = _df_copy[_df_copy["in_out"] == "支出"].groupby("month")["order_amount"].sum()
    all_months = sorted(set(inc.index) | set(exp.index))
    op_flow_map = {str(m): round(float(inc.get(m, 0) - exp.get(m, 0)), 2) for m in all_months}

    # Neutral flow (充值为正/提现为负/零钱通转入正/转出负)
    neutral = _df_copy[_df_copy["in_out"].isin(["/", "不计收支", ""])].copy()
    neutral_flow_map: dict[str, float] = {}
    for _, r in neutral.iterrows():
        m = str(r["month"]) if pd.notna(r.get("month")) else None
        if not m:
            continue
        amt = float(r["order_amount"]) if pd.notna(r.get("order_amount")) else 0.0
        ot = str(r.get("order_type", ""))
        # 提现/转出 → 资金离开微信 → 负
        if any(kw in ot for kw in ["提现", "转出", "转帐", "转账"]):
            amt = -amt
        # 充值/转入 → 资金进入微信 → 正
        elif any(kw in ot for kw in ["充值", "转入", "收款", "红包"]):
            amt = +amt
        # 默认：看 keeper/goods 判断
        else:
            goods = str(r.get("goods", ""))
            keeper = str(r.get("keeper", ""))
            text = goods + keeper
            if any(kw in text for kw in ["充值", "转入", "收款"]):
                amt = +amt
            elif any(kw in text for kw in ["提现", "转出"]):
                amt = -amt
        neutral_flow_map[m] = neutral_flow_map.get(m, 0.0) + amt

    months = sorted(all_months)
    return _json_safe({
        "months": [str(m) for m in months],
        "op_flow": [op_flow_map.get(str(m), 0) for m in months],
        "total_flow": [op_flow_map.get(str(m), 0) + neutral_flow_map.get(str(m), 0) for m in months],
    })


@app.get("/api/monthly-expense")
async def api_monthly_expense():
    """月度支出时序（供图表渲染）。"""
    ms = compute_monthly_stats(_df)
    expense = ms["monthly_expense"]
    return _json_safe({
        "months": expense.index.astype(str).tolist(),
        "values": expense.values.tolist(),
        "mom_change": [float(v) if not (np.isnan(v) if isinstance(v, float) else False) else None for v in ms["mom_change"].values],
        "yoy_change": [float(v) if not (np.isnan(v) if isinstance(v, float) else False) else None for v in ms["yoy_change"].values],
    })


@app.get("/api/drill-month")
async def api_drill_month(ym: str = Query(None)):
    """钻取单月。不传则返回最新月。"""
    if ym is None:
        if len(_df) == 0:
            return _json_safe(compute_drill_month(_df, ""))
        ym = sorted(_df["year_month_str"].dropna().unique())[-1]
    return _json_safe(compute_drill_month(_df, ym))


@app.get("/api/compare-months")
async def api_compare_months(
    ym_a: str = Query(...), ym_b: str = Query(...),
):
    """两个月份对比。"""
    return _json_safe(compute_month_comparison(_df, ym_a, ym_b))


# ── 分类 ──

@app.get("/api/categories")
async def api_categories():
    """消费分类汇总。"""
    ce = classify_expenses(_df)
    return _json_safe({
        "amount": ce["category_amount"].to_dict(),
        "count": ce["category_count"].to_dict(),
        "monthly_trend": compute_category_monthly_trend(ce["df_expense"]),
    })


# ── 预测 ──

@app.get("/api/forecast")
async def api_forecast(periods: int = Query(8)):
    """Prophet 预测。"""
    ms = compute_monthly_stats(_df)
    return _json_safe(forecast_expense(ms["monthly_expense"], periods)["forecast"])


# ── 异常检测 ──

@app.get("/api/anomalies")
async def api_anomalies(sigma: float = Query(3.0)):
    """异常大额消费。"""
    result = detect_anomalies(_df, sigma)
    return _json_safe({
        "threshold": result["threshold"],
        "count": result["count"],
        "items": result["anomalies"].to_dict(orient="records"),
    })


# ── 节假日 ──

@app.get("/api/holidays")
async def api_holidays():
    return _json_safe(compute_holiday_stats(_df))


# ── 社交 ──

@app.get("/api/social")
async def api_social():
    result = compute_social_transfers(_df)
    return _json_safe(result.to_dict(orient="records"))


# ── 商户 ──

@app.get("/api/merchants")
async def api_merchants():
    ce = classify_expenses(_df)
    rfm = compute_merchant_rfm(ce["df_expense"])
    return _json_safe({
        "top10_amount": rfm["top10_amount"].to_dict(orient="records"),
        "top10_count": rfm["top10_count"].to_dict(orient="records"),
        "rfm": [
            {
                "keeper": r["keeper"],
                "recency": int(r["recency"]),
                "frequency": int(r["frequency"]),
                "monetary": float(r["monetary"]),
            }
            for _, r in rfm["rfm"].iterrows()
        ],
    })


# ── 关联规则 ──

@app.get("/api/association-rules")
async def api_association_rules(
    min_support: float = Query(0.05),
    min_confidence: float = Query(0.3),
    level: str = Query("merchant", description="merchant | category | goods"),
):
    result = compute_association_rules(_df, min_support, min_confidence, level=level)
    rules = result["rules"]
    top = rules.head(20)
    return _json_safe({
        "count": int(result["count"]),
        "level": level,
        "top20": [
            {
                "antecedents": ", ".join(r["antecedents"]),
                "consequents": ", ".join(r["consequents"]),
                "support": float(r["support"]),
                "confidence": float(r["confidence"]),
                "lift": float(r["lift"]),
            }
            for _, r in top.iterrows()
        ],
    })


# ── 时序分解 ──

@app.get("/api/decompose")
async def api_decompose():
    ms = compute_monthly_stats(_df)
    return _json_safe(decompose_timeseries(ms["monthly_expense"]))


@app.get("/api/income-balance")
async def api_income_balance():
    """月度收入结余数据（供双轴柱线图）。"""
    ms = compute_monthly_stats(_df)
    bal = ms["monthly_balance"]
    return _json_safe({
        "months": bal.index.astype(str).tolist(),
        "income": [round(float(v), 2) for v in bal["收入"].values],
        "expense": [round(float(v), 2) for v in bal["支出"].values],
        "balance": [round(float(v), 2) for v in bal["结余"].values],
    })


@app.get("/api/yearly-top3")
async def api_yearly_top3():
    """年度 Top 3 月份数据。"""
    from mypayment_metrics import compute_yearly_top3
    t3 = compute_yearly_top3(_df)
    def _df_to_records(df):
        return df.to_dict(orient="records")
    return _json_safe({
        "top3_income": _df_to_records(t3["top3_income"]),
        "top3_expense": _df_to_records(t3["top3_expense"]),
        "top3_balance": _df_to_records(t3["top3_balance"]),
        "top3_trans": _df_to_records(t3["top3_trans"]),
    })


@app.get("/api/health-dashboard")
async def api_health_dashboard():
    """财务健康仪表板完整数据。"""
    from mypayment_metrics import compute_monthly_stats, classify_expenses
    from mypayment_metrics import compute_financial_indicators, compute_health_score
    ms = compute_monthly_stats(_df)
    ce = classify_expenses(_df)
    fi = compute_financial_indicators(_df, ms["monthly_expense"], ce["category_amount"])
    hs = compute_health_score(fi["saving_rate"], fi["engel"], ms["monthly_expense"], cv=fi["cv"])
    return _json_safe({
        "indicators": fi,
        "health_score": hs,
        "monthly_expense": ms["monthly_expense"].to_dict(),
        "category_amount": ce["category_amount"].to_dict(),
    })


# ── 多样性趋势 + 环比异常 ──

@app.get("/api/diversity-trend")
async def api_diversity_trend():
    from mypayment_metrics import classify_expenses, compute_diversity_trend
    ce = classify_expenses(_df)
    return _json_safe(compute_diversity_trend(ce["df_expense"]))


@app.get("/api/mom-anomalies")
async def api_mom_anomalies(threshold: float = Query(0.5, ge=0.2, le=2.0)):
    from mypayment_metrics import classify_expenses, detect_mom_anomalies
    ce = classify_expenses(_df)
    return _json_safe(detect_mom_anomalies(ce["df_expense"], threshold))


# ── 热力图 ──

@app.get("/api/hourly-heatmap")
async def api_hourly_heatmap():
    """星期 × 小时 热力图数据。"""
    from mypayment_metrics import compute_hourly_heatmap, WEEKDAY_LABELS
    pivot = compute_hourly_heatmap(_df)
    return _json_safe({
        "weekday_labels": WEEKDAY_LABELS,
        "hours": [int(h) for h in pivot.columns],
        "data": [[float(pivot.iloc[i, j]) for j in range(len(pivot.columns))] for i in range(len(pivot))],
    })


# ── 模糊搜索 ──

@app.get("/api/search")
async def api_search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
):
    """模糊搜索：匹配 keeper / goods / order_type / category / order_num。
    返回分页结果 + 汇总统计。
    """
    import re
    pattern = re.escape(q)
    # Build mask across text columns
    mask = pd.Series(False, index=_df.index)
    for col in ["keeper", "goods", "order_type", "category", "order_num", "order_time"]:
        if col in _df.columns:
            mask |= _df[col].astype(str).str.contains(pattern, case=False, na=False, regex=True)
    # Also search year_month_str
    if "year_month_str" in _df.columns:
        mask |= _df["year_month_str"].astype(str).str.contains(pattern, case=False, na=False)
    # Also search order_amount / signed_amount for exact number match
    try:
        amt = float(q.replace("¥", "").replace(",", "").replace(" ", ""))
        mask |= (_df["order_amount"] - amt).abs() < 0.01
    except ValueError:
        pass

    result = _df[mask].sort_values("order_time", ascending=False)
    total = len(result)
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    page_data = result.iloc[offset : offset + page_size]

    # Summary
    inc = float(page_data[page_data["in_out"] == "收入"]["order_amount"].sum())
    exp = float(page_data[page_data["in_out"] == "支出"]["order_amount"].sum())

    records = []
    for _, row in page_data.iterrows():
        records.append({
            "id": int(row["id"]) if pd.notna(row.get("id")) else None,
            "time": str(row["order_time"]) if pd.notna(row.get("order_time")) else "",
            "type": str(row.get("order_type", "")),
            "keeper": str(row.get("keeper", "")),
            "goods": str(row.get("goods", "")),
            "in_out": str(row.get("in_out", "")),
            "amount": float(row["order_amount"]),
            "category": str(row.get("category", "")),
            "is_refund": bool(row.get("is_refund", False)),
        })

    return _json_safe({
        "query": q,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "page_income": inc,
        "page_expense": exp,
        "records": records,
    })


# ── 系统消息 ──

@app.get("/api/system-messages")
async def api_system_messages():
    """读取最近合并日志，供首页消息列展示。"""
    from pathlib import Path as P
    logs = []
    log_dir = Path(__file__).parent.parent / "logs"
    if log_dir.is_dir():
        for f in sorted(log_dir.glob("*.log"), reverse=True)[:1]:
            with open(f, encoding="utf-8") as fh:
                lines = fh.readlines()
            for line in lines:
                line = line.strip()
                if not line: continue
                level = "INFO"
                for lv in ["ERROR", "WARN", "INFO"]:
                    if f"[{lv}]" in line: level = lv; break
                ts = line[1:9] if line.startswith("[") else ""
                msg = line[line.find("] ", line.find("] ") + 2) + 2:] if "] " in line else line
                logs.append({"time": ts, "level": level, "message": msg[:120]})
    # Return last 15 messages, newest first
    return logs[-15:][::-1]


# ── 年份列表 ──

@app.get("/api/year-months")
async def api_year_months():
    if len(_df) == 0:
        return _json_safe({"years": [], "year_months": []})
    return _json_safe({
        "years": sorted(_df["year"].dropna().unique().astype(int).tolist()),
        "year_months": sorted(_df["year_month_str"].dropna().unique().tolist()),
    })


# ── 多级钻取（全部 → 年 → 季度 → 月）──

@app.get("/api/drill-level")
async def api_drill_level(
    level: str = Query("all", description="all | year | quarter | month"),
    year: int = Query(None),
    quarter: int = Query(None, ge=1, le=4),
    month: int = Query(None, ge=1, le=12),
):
    """多级钻取：汇总全部 → 某年 → 某年某季 → 某年某月。"""
    if len(_df) == 0:
        return _json_safe({"level": "all", "label": "无数据", "income": 0, "expense": 0, "count": 0, "avg": 0, "categories": {}, "daily": {}, "top5": {}, "next_level": None, "next_groups": []})
    df_part = _df.copy()

    # 逐级过滤
    if level in ("year", "quarter", "month") and year is not None:
        df_part = df_part[df_part["year"] == year]
    if level in ("quarter", "month") and quarter is not None:
        df_part = df_part[df_part["month_num"].between(quarter * 3 - 2, quarter * 3)]
    if level == "month" and month is not None:
        df_part = df_part[df_part["month_num"] == month]

    # 汇总支出
    exp_df = df_part[df_part["in_out"] == "支出"]
    inc_total = float(df_part[df_part["in_out"] == "收入"]["order_amount"].sum())
    exp_total = float(exp_df["order_amount"].sum())

    # 按下一级分组（供钻取菜单）
    next_level = {"all": "year", "year": "quarter", "quarter": "month", "month": None}[level]
    groups = []
    if next_level == "year":
        groups = (
            exp_df.groupby("year")["order_amount"]
            .sum().sort_index().reset_index()
            .rename(columns={"year": "key", "order_amount": "total"})
        )
        groups["key"] = groups["key"].astype(int)
    elif next_level == "quarter":
        exp_df_copy = exp_df.copy()
        exp_df_copy["q"] = ((exp_df_copy["month_num"] - 1) // 3 + 1).astype(int)
        groups = (
            exp_df_copy.groupby("q")["order_amount"]
            .sum().reset_index()
            .rename(columns={"q": "key", "order_amount": "total"})
        )
    elif next_level == "month" or level == "month":
        # 月度：下一级是 month，或者当前就是 month 级别（显示月度柱状图）
        groups = (
            exp_df.groupby("month_num")["order_amount"]
            .sum().reset_index()
            .rename(columns={"month_num": "key", "order_amount": "total"})
        )

    # 分类
    cats = exp_df.groupby("category")["order_amount"].sum().to_dict()

    # 每日支出（仅月级有）
    daily = {}
    if level == "month":
        daily_series = exp_df.groupby(exp_df["order_time"].dt.day)["order_amount"].sum()
        daily = {str(k): round(float(v), 2) for k, v in daily_series.items()}

    return _json_safe({
        "level": level,
        "year": year,
        "quarter": quarter,
        "month": month,
        "label": f"{year or ''}{' Q'+str(quarter) if quarter else ''}{'/'+str(month) if month else '全部'}".strip().strip("/") or "全部",
        "income": inc_total,
        "expense": exp_total,
        "count": len(exp_df),
        "avg": round(exp_total / len(exp_df), 2) if len(exp_df) > 0 else 0,
        "categories": cats,
        "daily": daily,
        "top5": exp_df.groupby("keeper")["order_amount"].sum().nlargest(5).to_dict(),
        "next_level": next_level,
        "next_groups": groups.to_dict(orient="records") if isinstance(groups, pd.DataFrame) else [],
    })


# ── 数据上传 + 合并 + 清洗 ──

PREDATA_DIR = Path(__file__).parent.parent / "predata"
PREDATA_DIR.mkdir(exist_ok=True)
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
TARGET_CSV = Path(__file__).parent.parent / "data" / "my_payment.csv"


def _write_log(message: str, level: str = "INFO") -> None:
    """写入日志到 logs/merge_{date}.log。"""
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = LOGS_DIR / f"merge_{today}.log"
    ts = datetime.now().strftime("%H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] [{level}] {message}\n")


@app.get("/api/uploads")
async def api_list_uploads():
    """列出 predata/ 中的文件。"""
    files = []
    if PREDATA_DIR.is_dir():
        for f in sorted(PREDATA_DIR.iterdir()):
            if f.suffix.lower() in (".csv", ".xlsx", ".xls"):
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })
    return files


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """拖拽上传 CSV / XLSX 文件到 predata/。"""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".xlsx", ".xls"):
        return JSONResponse(
            {"error": f"不支持的文件类型: {suffix}，仅支持 .csv / .xlsx"},
            status_code=400,
        )

    dest = PREDATA_DIR / file.filename
    # 如果同名文件已存在，加时间戳后缀
    if dest.exists():
        stem = Path(file.filename).stem
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = PREDATA_DIR / f"{stem}_{ts}{suffix}"

    try:
        content = await file.read()
        with open(dest, "wb") as f:
            f.write(content)
        _write_log(f"上传成功: {file.filename} → {dest.name} ({len(content)} bytes)")
        return {"status": "ok", "filename": dest.name, "size": len(content)}
    except Exception as e:
        _write_log(f"上传失败: {file.filename} — {e}", "ERROR")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/api/uploads/{filename}")
async def api_delete_upload(filename: str):
    """删除 predata/ 中的某个文件。"""
    fpath = PREDATA_DIR / filename
    if not fpath.exists():
        return JSONResponse({"error": "文件不存在"}, status_code=404)
    try:
        fpath.unlink()
        _write_log(f"删除 predata 文件: {filename}")
        return {"status": "ok"}
    except Exception as e:
        _write_log(f"删除失败: {filename} — {e}", "ERROR")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/merge-and-clean")
async def api_merge_and_clean():
    """合并 predata/ → data/my_payment.csv，带事务回滚 + 日志。

    流程:
      1. 备份当前 CSV → data/my_payment_backup.csv
      2. 尝试执行 merge + clean + write_back
      3. 成功则删除备份，失败则从备份回滚
      4. 无论成败都写日志到 logs/
    """
    backup_path = TARGET_CSV.parent / "my_payment_backup.csv"
    start_time = datetime.now()

    try:
        # 1. 备份
        if TARGET_CSV.exists():
            shutil.copy2(TARGET_CSV, backup_path)
            _write_log(f"备份完成: {backup_path.name} ({TARGET_CSV.stat().st_size} bytes)")

        # 2. 合并（mypayment_merge 扫描 predata/ 并写入 CSV）
        from mypayment_merge import merge_predata
        old_df = pd.read_csv(TARGET_CSV, encoding="utf-8-sig", dtype=str) if TARGET_CSV.exists() else pd.DataFrame()
        old_count = len(old_df)

        merged = merge_predata(dry_run=False, clean_start=False)
        new_count = len(merged)
        elapsed = (datetime.now() - start_time).total_seconds()
        added = new_count - old_count

        # 3. 成功 → 删备份 + 清空 predata
        if backup_path.exists():
            backup_path.unlink()
        # 清空 predata/ 下所有文件（避免下次合并时重复扫描）
        predata_cleared = 0
        for pf in sorted(PREDATA_DIR.glob("*")):
            if pf.is_file():
                pf.unlink()
                predata_cleared += 1
        if predata_cleared > 0:
            _write_log(f"已清空 predata/: {predata_cleared} 个文件")
        # 重新加载数据到内存 + 刷新缓存
        global _df
        from mypayment_clean import clean_data
        _df = clean_data(str(TARGET_CSV))
        _df = enrich_time_fields(_df)
        from mypayment_metrics import _ensure_category
        _ensure_category(_df)
        _refresh_summary()
        _write_log(
            f"合并成功: {old_count}→{new_count} 条 (+{added}), 耗时 {elapsed:.1f}s"
        )

        return {
            "status": "ok",
            "old_count": old_count,
            "new_count": new_count,
            "added": added,
            "elapsed_seconds": round(elapsed, 1),
            "date_range": f"{_df['order_time'].min()} ~ {_df['order_time'].max()}",
            "sources": _df["source"].value_counts().to_dict() if "source" in _df.columns else {},
        }

    except Exception as e:
        # 4. 失败 → 回滚
        traceback_str = traceback.format_exc()
        _write_log(f"合并失败: {e}\n{traceback_str}", "ERROR")

        if backup_path.exists():
            shutil.copy2(backup_path, TARGET_CSV)
            backup_path.unlink()
            _write_log("回滚完成: 已恢复原始数据", "WARN")

        return JSONResponse(
            {
                "status": "error",
                "message": str(e),
                "detail": traceback_str.split("\n")[-3],
                "rollback": "已自动回滚到合并前的数据",
            },
            status_code=500,
        )


@app.post("/api/clear-data")
async def api_clear_data():
    """清除所有账单数据、日志、上传文件、缓存，保留空目录结构。"""
    from pathlib import Path
    import shutil

    ROOT = Path(__file__).resolve().parent.parent
    targets = [
        (ROOT / "data" / "my_payment.csv", "账单 CSV"),
        (ROOT / "data" / "my_payment_backup.csv", "备份 CSV"),
        (ROOT / "predata", "待合并文件"),
        (ROOT / "logs", "操作日志"),
        (ROOT / "__pycache__", "项目缓存"),
        (ROOT.parent / "__pycache__", "根目录缓存"),
    ]

    removed = []
    try:
        for path, label in targets:
            if label in ("待合并文件", "操作日志"):
                if path.is_dir():
                    for f in list(path.glob("*")):
                        if f.is_file():
                            f.unlink()
                            removed.append(f"{label}: {f.name}")
            elif path.is_dir():
                shutil.rmtree(path)
                removed.append(label)
            elif path.is_file():
                path.unlink()
                removed.append(label)

        # 确保空目录存在
        for d in [ROOT / "data", ROOT / "predata", ROOT / "logs"]:
            d.mkdir(parents=True, exist_ok=True)

        # 重置内存数据
        global _df
        from mypayment_clean import clean_data
        _df = clean_data(str(TARGET_CSV))
        _df = enrich_time_fields(_df)
        from mypayment_metrics import _ensure_category
        _ensure_category(_df)
        _refresh_summary()

        return {"status": "ok", "removed": removed}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn, webbrowser, socket as _socket, subprocess as _sp, time as _time

    PORT = 8765

    # ── Cleanup: kill any stale process holding our port ──
    def _is_port_in_use(port):
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', port))
            s.close()
            return result == 0
        except Exception:
            return False

    if _is_port_in_use(PORT):
        print(f"[INFO] 端口 {PORT} 被占用，正在释放...")
        if sys.platform == "win32":
            try:
                # Find and kill the process using our port
                out = _sp.check_output(
                    f'netstat -ano | findstr ":{PORT}" | findstr "LISTENING"',
                    shell=True, text=True, timeout=5
                )
                for line in out.strip().split('\n'):
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        try:
                            _sp.run(f'taskkill /F /PID {pid}', shell=True,
                                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=5)
                            print(f"  已终止旧进程 PID:{pid}")
                        except Exception:
                            pass
            except Exception:
                pass
        else:
            try:
                _sp.run(f"fuser -k {PORT}/tcp", shell=True,
                        stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=5)
            except Exception:
                pass
        # Wait for port to release (max 10s)
        for _ in range(20):
            _time.sleep(0.5)
            if not _is_port_in_use(PORT):
                break
        if _is_port_in_use(PORT):
            print(f"[FAIL] 无法释放端口 {PORT}，请手动关闭占用程序后重试")
            sys.exit(1)

    threading.Thread(target=_heartbeat_watcher, daemon=True).start()
    print(f"\n  仪表板地址: http://127.0.0.1:8765")
    print(f"  关闭浏览器页面后 25 秒内自动释放进程\n")

    def _open_browser():
        _time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8765")

    threading.Thread(target=_open_browser, daemon=True).start()

    # Embedded Python 3.11 on Windows can hit socketpair 10013 on first
    # event-loop creation. A short sleep + retry almost always resolves it.
    if sys.platform == "win32":
        _time.sleep(0.3)
        for _retry in range(3):
            try:
                uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning", loop="none")
                break
            except (PermissionError, OSError) as _e:
                msg = str(_e)
                if "10013" in msg or "套接字" in msg or "socket" in msg.lower():
                    print(f"  [RETRY] asyncio init failed, retrying in 1s...")
                    _time.sleep(1)
                else:
                    raise
        else:
            print("  [FATAL] Failed to initialize asyncio after 3 attempts.")
            sys.exit(1)
    else:
        uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning", loop="none")
