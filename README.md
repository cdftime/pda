# 💎 PocketLedger — 个人财务分析系统

> 导入微信 / 支付宝账单，自动分类、清洗、可视化分析你的每一笔收支。

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.138-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Plotly](https://img.shields.io/badge/Plotly-29+-3F4F75?logo=plotly)](https://plotly.com/javascript/)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE)

---

## ✨ 功能一览

| 模块 | 功能 |
|---|---|
| 📊 **总览仪表盘** | 收支统计卡片（数字滚动动画）、月度支出柱状图、分类环形图、资产累积趋势、年度 Top3 排行 |
| 📈 **趋势分析** | 分类堆叠面积图、时段热力图、各品类趋势线、星期消费模式 |
| 🔍 **逐级钻取** | 年 → 季度 → 月 → 日，点击柱形逐层下钻 |
| ⚖️ **月份对比** | 任选两个月横向对比：分类柱状图、日消费曲线、差异摘要 |
| 🚨 **异常检测** | Shannon 熵多样性趋势、环比异常检测（可调阈值）、3-sigma 异常交易 |
| 🔮 **消费预测** | Prophet 时序预测（含置信区间）、STL 分解（趋势 / 季节 / 残差） |
| 🏪 **商户挖掘** | RFM 气泡图、Apriori 关联规则（商户 / 商品 / 品类三级）、节假日对比 |
| 👥 **社交转账** | 社交转账净流入/流出柱状图、资金流向 3D 散点图 |
| 🔎 **模糊搜索** | 全字段模糊搜索，分页浏览所有记录 |

## 🏗️ 技术架构

```
用户拖拽 .xlsx / .csv
        │
        ▼
┌─────────────────────────────────────────────┐
│           FastAPI 后端 (:8765)               │
│                                              │
│  mypayment_merge.py   账单合并 & 去重         │
│  mypayment_clean.py   10 步清洗流水线         │
│  mypayment_metrics.py 15+ 指标计算函数        │
│  category_keywords.json  关键词自动分类       │
│              │                               │
│       data/my_payment.csv                    │
└─────────────────────────────────────────────┘
        │ REST JSON
        ▼
┌─────────────────────────────────────────────┐
│         前端 static/ (Vanilla JS)            │
│                                              │
│  Plotly.js 29+ 交互图表                       │
│  Glassmorphism 玻璃拟态设计                    │
│  骨架屏加载 · Toast 提示 · 全屏展开            │
└─────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境要求

- **Windows**：无需安装任何东西（内置 Python 3.11）
- **Linux / macOS**：需系统自带 Python 3.9+

### 一键启动

**Windows** — 双击运行：

```
start\start.bat
```

**Linux / macOS** — 终端运行：

```bash
bash start/start.sh
```

启动脚本会自动：
1. 检测 / 安装 Python 依赖（离线 wheels → 清华镜像 → 中科大镜像 → PyPI）
2. 创建数据目录（`data/`、`predata/`、`logs/`）
3. 启动服务并打开浏览器

### 访问地址

```
http://127.0.0.1:8765
```

> 💡 关闭浏览器页面后，服务会在 25 秒内自动退出。

## 📂 项目结构

```
pocketledger/
├── src/
│   ├── mypayment_api.py          # FastAPI 主程序 (30+ API 端点)
│   ├── mypayment_clean.py        # 数据清洗 (10 步流水线)
│   ├── mypayment_merge.py        # 账单合并 (微信 XLSX + 支付宝 CSV)
│   ├── mypayment_metrics.py      # 指标计算引擎 (15+ 函数)
│   ├── clear_data.py             # 数据清除工具
│   └── category_keywords.json    # 分类关键词配置 (10 粗类 + 20 细类)
├── static/
│   ├── index.html                # 单页面应用
│   ├── style.css                 # Glassmorphism 样式
│   └── app.js                    # 前端逻辑 (Plotly 图表)
├── start/
│   ├── start.bat                 # Windows 启动脚本
│   ├── start.sh                  # Linux/macOS 启动脚本
│   └── requirements.txt          # Python 依赖清单
├── explain/
│   ├── architecture.html         # 完整架构文档 (Mermaid 图表)
│   └── diagrams.html             # 架构图概览
├── python/                       # 内置 CPython 3.11 (便携版)
├── wheels/                       # 离线 pip 包 (45 个 .whl)
├── data/                         # 主数据库 (my_payment.csv)
├── predata/                      # 待合并账单暂存
└── logs/                         # 合并日志
```

## 📊 数据流

```
微信 .xlsx + 支付宝 .csv
        │
        ▼  拖拽上传
   POST /api/upload → predata/
        │
        ▼  点击合并
   POST /api/merge-and-clean
        │
        ├─ mypayment_merge.py  ─ 解析 / 编码检测 / 去重
        ├─ mypayment_clean.py  ─ 10 步清洗流水线
        ├─ category_keywords   ─ 关键词自动分类
        └─ mypayment_metrics   ─ 指标计算
        │
        ▼
   data/my_payment.csv (13 列统一格式)
        │
        ▼  API JSON 响应
   Plotly 图表渲染
```

### 10 步清洗流水线

| 步骤 | 操作 |
|---|---|
| 1 | 时间字段转换 `pd.to_datetime` |
| 2 | 金额字段清洗（去 ¥/, → numeric） |
| 3 | `goods` 列 `/` 替换为空格 |
| 4 | 6 列文本清洗（`\n\r\t` → 空格） |
| 5 | `keeper` 列去除 "发给" 前缀 |
| 6 | 退款标记（识别 order_type/status 含"退款"） |
| 7 | 按 `order_num` 去重（非空才参与） |
| 8 | ID 重新编号 |
| 9 | 时间派生字段（month / weekday / hour） |
| 10 | 数据质量报告输出 |

## 🔧 API 端点

### 核心
| 方法 | 端点 | 说明 |
|---|---|---|
| GET | `/api/summary` | 总览统计数据 |
| GET | `/api/year-months` | 可用年月列表 |

### 仪表盘
| 方法 | 端点 | 说明 |
|---|---|---|
| GET | `/api/monthly-expense` | 月度支出趋势 |
| GET | `/api/categories` | 分类汇总 |
| GET | `/api/asset-trend-full` | 资产累积趋势 |
| GET | `/api/yearly-top3` | 年度 Top3 |

### 分析
| 方法 | 端点 | 说明 |
|---|---|---|
| GET | `/api/category-monthly-trend` | 分类月度趋势 |
| GET | `/api/drill-level` | 层级钻取 |
| GET | `/api/month-compare` | 两月对比 |
| GET | `/api/diversity-trend` | 多样性趋势 |
| GET | `/api/mom-anomalies` | 环比异常 |
| GET | `/api/forecast` | Prophet 预测 |
| GET | `/api/decompose` | STL 分解 |
| GET | `/api/anomalies` | 3-sigma 异常 |
| GET | `/api/holidays` | 节假日对比 |
| GET | `/api/merchants` | 商户 RFM |
| GET | `/api/association-rules` | 关联规则 |
| GET | `/api/social` | 社交转账 |
| GET | `/api/search` | 模糊搜索 |

### 上传 & 系统
| 方法 | 端点 | 说明 |
|---|---|---|
| POST | `/api/upload` | 上传账单文件 |
| GET | `/api/uploads` | 列出待合并文件 |
| DELETE | `/api/uploads/{name}` | 删除待合并文件 |
| POST | `/api/merge-and-clean` | 执行合并清洗 |
| POST | `/api/heartbeat` | 心跳保活 |
| GET | `/api/system-messages` | 系统消息 |

## 🎨 前端特性

- **Glassmorphism 设计** — 毛玻璃效果、渐变背景、CSS 变量主题
- **数字滚动动画** — cubic ease-out 缓动，800ms 从 0 滚到目标值
- **骨架屏加载** — 图表加载前显示占位骨架，提升感知性能
- **响应式布局** — CSS Grid + Flexbox，适配不同屏幕尺寸
- **全屏图表** — 点击图表可展开全屏查看
- **Toast 通知** — 操作反馈提示
- **指标解释弹窗** — 点击 ⓘ 图标查看指标说明

## 🗂️ 分类体系

基于关键词匹配的自动分类系统，配置文件：[category_keywords.json](src/category_keywords.json)

| 粗分类 (10 类) | 细分类 (20 类) |
|---|---|
| 🍜 餐饮 (80+ 关键词) | 外卖、茶饮咖啡、正餐… |
| 🚗 交通出行 (40+) | 共享出行、网约车… |
| 🛒 购物消费 (60+) | 超市便利、电商网购… |
| 🏠 生活日用 (40+) | — |
| 📡 通讯网络 (10) | 话费充值… |
| 🏘️ 居住缴费 (15) | — |
| 🏥 医疗健康 (15) | — |
| 📚 教育培训 (20) | — |
| 💸 转账红包 (5) | — |
| 📦 其他 | — |

> 💡 直接编辑 `category_keywords.json` 即可自定义分类规则，无需改代码。

## 📦 依赖

```
fastapi              # Web 框架
pandas + numpy       # 数据处理
openpyxl             # Excel 解析
prophet              # 时序预测 (Meta)
statsmodels          # STL 分解
mlxtend              # Apriori 关联规则
scikit-learn         # 机器学习
uvicorn              # ASGI 服务器
python-multipart     # 文件上传
tabulate             # 表格格式化
```

## 📖 更多文档

- [完整架构文档](explain/architecture.html) — 模块详解 + Mermaid 交互图
- [架构图概览](explain/diagrams.html) — 7 张核心架构图

## ⚠️ 注意事项

- 本项目为**本地单机**使用，数据存储在本地 CSV 文件中，不会上传到任何服务器
- 首次使用需上传微信 / 支付宝导出的账单文件，点击「合并入库」后数据才会进入系统
- 微信导出格式为 `.xlsx`，支付宝导出格式为 `.csv`（均支持 GBK / UTF-8 编码自动检测）
- 关闭浏览器页面后，后端服务会自动退出，不会常驻后台

---

<p align="center">
  <sub>Built with ❤️ · FastAPI + Plotly.js · Offline-capable</sub>
</p>
