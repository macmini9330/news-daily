# 哈萨克斯坦每日要闻（News Daily Digest）

哈萨克斯坦每日新闻自动日报系统。每天早上 09:00（北京时间）自动抓取哈通社（Kazinform）中俄双语新闻，LLM 按四大板块分类分析，生成深色主题 HTML 日报并部署到 GitHub Pages。

## 🔗 线上地址

- 首页：https://macmini9330.github.io/news-daily/
- 仓库：https://github.com/macmini9330/news-daily （Public）

## 📰 日报内容结构（用户拍板）

| 板块 | 短名 | 内容 |
|------|------|------|
| 政治新闻及分析（内政） | 内政 🏛️ | 哈国总统/政府/议会/内政 |
| 政治新闻及分析（外交） | 外交 🌍 | 国际关系/外交动态 |
| 金融政策新闻及分析 | 金融 💰 | 央行/汇率/金融政策 |
| 矿产资源进出口管制政策新闻及分析 | 矿产 ⛏️ | 矿产出口/资源管制 |

每条新闻：标题（含来源链接 ↗）+ 内容摘要 + ▸展开全文（中文翻译）+ 要点 + 影响分析。

## ⏰ 核心规则

- **运行时间**：每天 09:00（cron `0 9 * * *`）
- **抓取窗口**：前一日 09:00 → 当日 09:00（**北京时间**，哈通社阿斯塔纳时间 UTC+5 解析后 +3h）
- **日期命名**：文件名 = 页面标题 = 首页显示 = **发布日**（今天生成的日报就是「今天日报」）
- **详情页顶部**：时间范围说明条（如「本日报抓取新闻时间范围：2026年08月19日早9:00至2026年08月20日早9:00（北京时间）」）

## 🏗️ 架构

```
cron 09:00 → scraper/run_daily.py（主流水线）
    ↓
scraper/fetch_kz_news.py   抓取中文版 lenta+7板块 + 俄语版 lenta 分页（约 170-220 条/天）
    ↓
scraper/analyze_kz_news.py LLM 两阶段：①俄语标题批量翻译+四板块分类+去重
                           ②入选新闻抓详情→全文中文翻译→摘要+要点+影响
    ↓
scraper/generate_kz_html.py 生成 kz/YYYY-MM-DD.html + index.html（深色主题+目录导航）
    ↓
git push → GitHub Pages 自动部署
```

## 📁 目录结构

```
news-daily/
├── README.md              本文件
├── index.html             首页（自动生成）
├── scraper/
│   ├── run_daily.py       主流水线入口
│   ├── fetch_kz_news.py   抓取模块（窗口+时区过滤）
│   ├── analyze_kz_news.py LLM 分类分析模块
│   ├── generate_kz_html.py HTML 生成模块
│   └── convert_dark.py    旧版页面深色转换工具
├── kz/
│   └── YYYY-MM-DD.html    每日日报存档（自动生成）
└── docs/
    ├── ARCHITECTURE.md    架构与数据流详解
    ├── OPERATIONS.md      运维手册（窗口/时区/日期规则/踩坑速查）
    ├── CHANGELOG.md       变更日志（分任务归档）
    └── SOURCES.md         信息源清单
```

## 🚀 手动运行

```bash
cd ~/Documents/news-daily
python3 scraper/run_daily.py          # 完整流水线 + push
python3 scraper/run_daily.py --no-push  # 只生成不推送
```

## 📚 文档索引

- 架构详解：`docs/ARCHITECTURE.md`
- 运维手册（含踩坑）：`docs/OPERATIONS.md`
- 变更记录（分任务归档）：`docs/CHANGELOG.md`
- 信息源清单：`docs/SOURCES.md`

## ⚠️ 注意事项

- git push 走 SSH over 443（`ssh.github.com`），国内网络可用；HTTPS 直连 github.com 会被墙
- 完整流水线需 5-10 分钟（LLM 逐条翻译全文），必须后台运行
- 所有代码经验沉淀在 Hermes 技能 `news-daily-digest`（~/.hermes/skills/research/news-daily-digest/）
