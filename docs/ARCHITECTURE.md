# 架构与数据流详解

## 1. 系统总览

```
┌─────────────────────────────────────────────────────────────┐
│  cron (0 9 * * *) 每天 09:00 北京                          │
│    └─ run_daily.py ─────────────────────────────────────┐   │
│       │                                                 │   │
│       ├─ [1] fetch_kz_news.py   抓取阶段                │   │
│       │    中文版 lenta + 7 板块                        │   │
│       │    俄语版 lenta 分页 (7页×24条≈168条/天)        │   │
│       │    窗口过滤 [前日9:00, 当日9:00] 北京时间        │   │
│       │    时区转换: 阿斯塔纳 UTC+5 → 北京 UTC+8 (+3h)  │   │
│       │    输出: /tmp/kz_articles_raw.json              │   │
│       │                                                 │   │
│       ├─ [2] analyze_kz_news.py  LLM 分析阶段           │   │
│       │    阶段①: 俄语标题批量翻译→中文 + 四板块分类    │   │
│       │             + 中俄去重 (约170-220条→50-60条)    │   │
│       │    阶段②: 入选新闻抓详情页 → 俄语全文           │   │
│       │            LLM 翻译成中文全文 + 摘要+要点+影响  │   │
│       │    输出: /tmp/kz_articles_analyzed.json         │   │
│       │                                                 │   │
│       ├─ [3] generate_kz_html.py  HTML 生成阶段         │   │
│       │    生成 kz/YYYY-MM-DD.html (发布日命名)         │   │
│       │    更新 index.html (首页/往期列表/统计)         │   │
│       │                                                 │   │
│       └─ [4] git push → GitHub Pages 自动部署           │   │
└─────────────────────────────────────────────────────────────┘
```

## 2. 各模块职责

### 2.1 fetch_kz_news.py（抓取）

**信息源**：
- 中文版：`cn.inform.kz/lenta` + 总统/国际/政府/经济/议会/事件 6 板块（约 22-33 条/天，精选翻译）
- 俄语版：`www.inform.kz/ru/lenta` 分页（每页 24 条，约 7 页 = 168 条/天，全量）
- **为什么抓俄语版**：哈通社中文版只翻译约 13% 的新闻，俄语版才是全量（用户质疑「一个国家每天才这么几条？」后升级）

**时间窗口**（用户拍板：前一日 09:00 → 当日 09:00 北京时间）：
```python
CUTOFF_HOUR = 9
def window_bounds() -> tuple:
    now = datetime.now()
    end = datetime(now.year, now.month, now.day, CUTOFF_HOUR, 0)  # 今日 09:00 锚定
    start = end - timedelta(days=1)
    return start, end
```
- 双向过滤：`if at < start or at > end: continue`（只过滤起点会在下午手动跑时混入 9:00 后的新闻）
- 锚定「今日 9:00」而非「运行时刻-24h」：cron 延迟时窗口不漂移

**时区**：哈通社显示阿斯塔纳时间（UTC+5），北京 UTC+8。`parse_time()` 解析后统一 +3h 转北京时间，全链路（过滤+展示）一致。

**俄语版停页条件**：本页最早时间 < 窗口起点 且 page≥2（不能只判「含昨日」就停，会提前截断当天新闻）。

### 2.2 analyze_kz_news.py（LLM 分析）

两阶段设计（节省 token：不给无关新闻翻译全文）：

| 阶段 | 输入 | 输出 | token 成本 |
|------|------|------|-----------|
| ① 标题翻译+分类 | 全部标题（俄+中）| 四板块归属 + 中文标题 | 低（标题短）|
| ② 全文翻译+分析 | 入选新闻的详情页全文 | 中文全文 + 摘要 + 要点 + 影响 | 高（66条×~1000字）|

SECTIONS 结构（含短名，2026-08-20 用户要求目录排版优化后加入）：
```python
SECTIONS = [
    {"id": "politics_domestic", "num": "一", "name": "政治新闻及分析（内政）", "short": "内政", "icon": "🏛️"},
    {"id": "politics_foreign",  "num": "二", "name": "政治新闻及分析（外交）", "short": "外交", "icon": "🌍"},
    {"id": "finance",           "num": "三", "name": "金融政策新闻及分析",     "short": "金融", "icon": "💰"},
    {"id": "mining",            "num": "四", "name": "矿产资源进出口管制政策新闻及分析", "short": "矿产", "icon": "⛏️"},
]
```

### 2.3 generate_kz_html.py（HTML 生成）

- **日期规则**：文件名 = 发布日（运行日）。`date_str = datetime.now().strftime("%Y-%m-%d")`，页面标题「2026年8月20日日报」
- **window-bar**：详情页顶部时间范围说明条（北京时间）
- **toc 目录导航**：短名 chips + 锚点 `#sec-{id}` + 平滑滚动
- **索引页**：Hero + 统计卡 + 最新一期大卡 + 往期时间线 + 板块介绍网格
- **计数**：`hc.count('class="item"')`（旧结构用 `class="article"`），不能用 `count("展开全文")`（JS 按钮文本会虚高 +2）

### 2.4 run_daily.py（主流水线）

```python
# 伪代码
fetch()     → raw.json
analyze()   → analyzed.json
generate()  → HTML
git push    → Pages
```

## 3. 关键设计决策记录

| 决策 | 原因 |
|------|------|
| 抓俄语版全量 | 中文版只有 13% 内容（用户质疑后升级）|
| 窗口锚定今日 9:00 | cron 延迟不漂移，语义统一 |
| 时区统一北京时间 | 用户明确要求；哈通社 UTC+5 差 3 小时 |
| 日期=发布日 | 用户两次纠偏：要「今天就有今天的日报」|
| 目录短名 | 长名挤 chips 排版凌乱（用户投诉）|
| 全文必须中文 | 用户明确要求展开的是中文翻译 |
| git SSH over 443 | 国内直连 github.com 被墙，ssh.github.com:443 可用 |

## 4. 部署链路

1. 仓库：macmini9330/news-daily（Public，GitHub Pages 已开，main/root）
2. push 走 SSH：remote `git@github.com:macmini9330/news-daily.git`（~/.ssh/config 里 Host github.com → HostName ssh.github.com:443）
3. Pages 自动构建，约 30-60 秒
4. 验证：轮询 `https://macmini9330.github.io/news-daily/` 直到新特征出现
