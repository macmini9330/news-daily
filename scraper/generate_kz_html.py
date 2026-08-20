#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""哈萨克斯坦每日要闻 - HTML 生成模块

读取 /tmp/kz_articles_analyzed.json → 生成四板块日报 HTML
输出: /Users/liam/Documents/news-daily/kz/YYYY-MM-DD.html + index.html
"""
import json
import os
import re
from datetime import datetime

# 输出目录
BASE_DIR = os.path.expanduser("~/Documents/news-daily")
KZ_DIR = os.path.join(BASE_DIR, "kz")

SECTIONS = [
    {
        "id": "politics_domestic",
        "num": "一",
        "name": "政治新闻及分析（内政）",
        "icon": "🏛️",
    },
    {
        "id": "politics_foreign",
        "num": "二",
        "name": "政治新闻及分析（外交）",
        "icon": "🌍",
    },
    {
        "id": "finance",
        "num": "三",
        "name": "金融政策新闻及分析",
        "icon": "💰",
    },
    {
        "id": "mining",
        "num": "四",
        "name": "矿产资源进出口管制政策新闻及分析",
        "icon": "⛏️",
    },
]

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  background: #0d1117; color: #c9d1d9; line-height: 1.75; min-height: 100vh;
}
.container { max-width: 880px; margin: 0 auto; padding: 24px 20px 60px; }
.header { text-align: center; padding: 30px 0 18px; border-bottom: 1px solid #21262d; margin-bottom: 20px; }
.header h1 { font-size: 1.8em; font-weight: 700; color: #f0f6fc; margin-bottom: 10px; }
.header .meta { font-size: .95em; color: #8b949e; }
.header .nav-links { margin-top: 14px; font-size: .85rem; }
.header .nav-links a { color: #58a6ff; text-decoration: none; }
.header .nav-links a:hover { text-decoration: underline; }

.stats-bar { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin: 18px 0 6px; }
.stat-chip { padding: 5px 14px; background: #161b22; border: 1px solid #21262d; border-radius: 20px; font-size: .83rem; color: #8b949e; }

/* 板块标题 */
.doc-section { margin-top: 30px; }
.section-title {
  display: flex; align-items: center; gap: 10px;
  font-size: 1.15rem; font-weight: 700; color: #e6edf3;
  padding: 10px 16px; margin-bottom: 16px;
  background: #161b22; border: 1px solid #21262d; border-left: 4px solid #c0392b;
  border-radius: 8px;
}
.sec-seq {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 26px; height: 26px; background: #c0392b; color: #fff;
  border-radius: 6px; font-size: .85rem; font-weight: 700;
}
.section-title .count { font-size: .85rem; color: #8b949e; font-weight: 400; }

/* 单条 */
.item { padding: 14px 4px 10px; margin-bottom: 6px; border-bottom: 1px solid #161b22; border-left: 3px solid transparent; padding-left: 14px; }
.item-title { display: flex; align-items: flex-start; gap: 10px; font-size: 1.05rem; font-weight: 650; color: #e6edf3; margin-bottom: 6px; }
.item-title a { color: #e6edf3; text-decoration: none; }
.item-title a:hover { color: #58a6ff; }
.item-num {
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
  min-width: 34px; height: 30px; background: #c0392b40; color: #c0392b;
  border-radius: 6px; font-size: .9rem; font-weight: 700; margin-top: 2px;
}
.item-meta { font-size: .8rem; color: #8b949e; margin: 0 0 8px 44px; }
.item-meta .source-link { margin-left: 8px; }
.item-meta .source-link a { color: #58a6ff; text-decoration: none; }
.item-meta .source-link a:hover { text-decoration: underline; }

/* 摘要 */
.item-summary {
  margin: 8px 0 8px 44px; padding: 8px 14px;
  background: #161b22; border: 1px solid #21262d;
  border-radius: 0 6px 6px 0;
  font-size: .92rem; color: #d4d9e0;
}
.item-summary b { color: #58a6ff; }

/* 展开全文 */
.summary-toggle {
  margin: 6px 0 2px 44px; font-size: .82rem; color: #58a6ff;
  cursor: pointer; user-select: none; display: inline-block; padding: 2px 0;
}
.summary-toggle:hover { text-decoration: underline; }
.summary-toggle .arrow { display: inline-block; transition: transform 0.2s; margin-right: 4px; }
.summary-toggle.open .arrow { transform: rotate(90deg); }
.full-content {
  display: none;
  margin: 8px 0 4px 44px;
  font-size: .9rem; line-height: 1.85; color: #c9d1d9;
  background: #0d1117; border: 1px dashed #30363d;
  border-radius: 8px; padding: 12px 16px;
  white-space: pre-wrap;
}
.full-content.show { display: block; }

/* 要点 */
.item ul { margin: 6px 0 6px 44px; padding-left: 18px; }
.item ul li { margin-bottom: 6px; font-size: .93rem; }

/* 影响 */
.item-impact {
  margin: 10px 0 4px 44px; padding: 8px 14px;
  background: #f0b90b10; border-left: 3px solid #f0b90b;
  border-radius: 0 6px 6px 0;
}
.impact-label { font-weight: 700; color: #f0b90b; margin-right: 8px; }
.impact-text { color: #d4d9e0; font-size: .92rem; }

.empty { color: #8b949e; font-size: .9rem; padding: 12px 0 12px 44px; font-style: italic; }

.footer { text-align: center; color: #8b949e; font-size: .8rem; padding: 40px 0 0; border-top: 1px solid #21262d; margin-top: 40px; }
.footer a { color: #58a6ff; text-decoration: none; }

@media (max-width: 600px) {
  .item ul { margin-left: 8px; }
  .item-impact { margin-left: 8px; }
  .item-summary { margin-left: 8px; }
  .summary-toggle { margin-left: 8px; }
  .full-content { margin-left: 8px; }
  .item-meta { margin-left: 8px; }
}
"""


def esc(text: str) -> str:
    """HTML 转义"""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_daily_html(analyzed: dict, news_date: str) -> str:
    """生成单日日报 HTML（news_date=新闻日期，用于页面显示）"""
    sections = analyzed["sections"]
    total = sum(len(v) for v in sections.values())

    # 各板块统计
    stats_html = ""
    for sec in SECTIONS:
        cnt = len(sections.get(sec["id"], []))
        if cnt > 0:
            stats_html += f'<span class="stat">{sec["icon"]} {sec["name"].split("（")[0]} {cnt} 条</span>'

    # 各板块内容（OpenClaw 深色风格）
    sections_html = ""
    for sec in SECTIONS:
        items = sections.get(sec["id"], [])
        sections_html += f'<div class="doc-section">\n'
        sections_html += f'<h2 class="section-title"><span class="sec-seq">{esc(sec["num"])}</span> {esc(sec["name"])} <span class="count">({len(items)} 条)</span></h2>\n'
        if not items:
            sections_html += '<div class="empty">今日暂无此类新闻</div>\n'
        else:
            for i, it in enumerate(items, 1):
                title = esc(it["title"])
                url = it["url"]
                time_s = it.get("time", "")[5:16].replace("-", "/")
                source = esc(it.get("source", ""))
                sections_html += f'<div class="item">\n'
                sections_html += f'<h3 class="item-title"><span class="item-num">{i}</span> <a href="{url}" target="_blank">{title}</a></h3>\n'
                sections_html += f'<div class="item-meta">{source} · {time_s}<span class="source-link"><a href="{url}" target="_blank">来源链接 ↗</a></span></div>\n'
                if it.get("summary"):
                    sections_html += f'<div class="item-summary"><b>摘要：</b>{esc(it["summary"])}</div>\n'
                    if it.get("full_content"):
                        sections_html += f'<div class="summary-toggle" onclick="toggleContent(this)"><span class="arrow">▸</span>展开全文</div>\n'
                        sections_html += f'<div class="full-content">{esc(it["full_content"])}</div>\n'
                if it.get("points"):
                    sections_html += '<ul>\n'
                    for p in it["points"]:
                        sections_html += f'<li>{esc(p)}</li>\n'
                    sections_html += '</ul>\n'
                if it.get("impact"):
                    sections_html += f'<div class="item-impact"><span class="impact-label">影响</span><span class="impact-text">{esc(it["impact"])}</span></div>\n'
                sections_html += '</div>\n'
        sections_html += '</div>\n'

    # 日期显示（用新闻日期）
    d = datetime.strptime(news_date, "%Y-%m-%d")
    date_display = f"{d.year}年{d.month}月{d.day}日"

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{date_display} - 哈萨克斯坦每日要闻</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🇰🇿 哈萨克斯坦每日要闻</h1>
    <div class="meta">📅 {date_display}</div>
    <div class="nav-links"><a href="index.html">← 返回首页</a></div>
  </div>

  <div class="stats-bar"><span class="stat-chip">共 {total} 条</span><span class="stat-chip">{len([s for s in SECTIONS if sections.get(s["id"])])} 板块</span><span class="stat-chip">哈通社</span></div>

{sections_html}
  <div class="footer">
    <p>哈萨克斯坦每日要闻 · 由 Hermes 自动生成 · 数据来源：哈通社（Kazinform）· 仅供研究参考</p>
    <p>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
  </div>
</div>
<script>
function toggleContent(el) {{
el.classList.toggle('open');
var content = el.nextElementSibling;
if (content && content.classList.contains('full-content')) {{
  content.classList.toggle('show');
  var arrow = el.querySelector('.arrow');
  el.innerHTML = content.classList.contains('show')
    ? '<span class="arrow">▸</span>收起全文'
    : '<span class="arrow">▸</span>展开全文';
}}
}}
</script>
</body>
</html>
"""
    return html


def generate_index(history: dict) -> str:
    """生成往期索引页（history: {date_str: count}）"""
    rows = ""
    for date_str, cnt in sorted(history.items(), reverse=True):
        d = datetime.strptime(date_str, "%Y-%m-%d")
        display = f"{d.year}年{d.month}月{d.day}日"
        rows += f'<li><a href="kz/{date_str}.html">{display}</a>（{cnt} 条）</li>\n'

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>哈萨克斯坦每日要闻</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; background: #0d1117; color: #c9d1d9; line-height: 1.75; min-height: 100vh; }}
.container {{ max-width: 880px; margin: 0 auto; padding: 24px 20px 60px; }}
.header {{ text-align: center; padding: 30px 0 18px; border-bottom: 1px solid #21262d; margin-bottom: 28px; }}
.header h1 {{ font-size: 1.8em; font-weight: 700; color: #f0f6fc; margin-bottom: 10px; }}
.header .sub {{ color: #8b949e; font-size: .95em; }}
.list-section {{ margin-top: 10px; }}
ul {{ list-style: none; padding: 0; }}
li {{ background: #161b22; border: 1px solid #21262d; border-radius: 10px; padding: 14px 18px; margin-bottom: 10px; transition: border-color .2s; }}
li:hover {{ border-color: #58a6ff; }}
li a {{ color: #e6edf3; text-decoration: none; font-size: 15px; }}
li a:hover {{ color: #58a6ff; }}
li .count {{ color: #8b949e; font-size: .85rem; }}
.footer {{ text-align: center; color: #8b949e; font-size: .8rem; padding: 40px 0 0; border-top: 1px solid #21262d; margin-top: 40px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🇰🇿 哈萨克斯坦每日要闻</h1>
    <div class="sub">每日更新 · 自动生成 · 涵盖内政/外交/金融/矿产资源四大板块</div>
  </div>
  <div class="list-section">
    <ul>
    {rows}
    </ul>
  </div>
  <div class="footer">
    <p>哈萨克斯坦每日要闻 · 由 Hermes 自动生成 · 数据来源：哈通社（Kazinform）· 仅供研究参考</p>
  </div>
</div>
</body>
</html>
"""
    return html


def main():
    with open("/tmp/kz_articles_analyzed.json", encoding="utf-8") as f:
        analyzed = json.load(f)

    # 文件名用「运行日」（发布日），避免跨日覆盖
    date_str = datetime.now().strftime("%Y-%m-%d")

    # 页面标题用「新闻日期」（取所有新闻中出现最多的日期）
    from collections import Counter
    date_counter = Counter()
    for sid, items in analyzed["sections"].items():
        for it in items:
            t = it.get("time", "")
            if len(t) >= 10:
                date_counter[t[:10]] += 1
    if date_counter:
        news_date = date_counter.most_common(1)[0][0]
    else:
        news_date = date_str
    print(f"📅 文件名日期: {date_str}（发布日）| 页面新闻日期: {news_date}（各日期: {dict(date_counter)}）")
    os.makedirs(KZ_DIR, exist_ok=True)

    # 生成单日页
    html = generate_daily_html(analyzed, news_date)
    daily_path = os.path.join(KZ_DIR, f"{date_str}.html")
    with open(daily_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 日报已生成: {daily_path}")

    # 统计今日条数
    total = sum(len(v) for v in analyzed["sections"].values())

    # 生成/更新索引页（读取已有历史，从每个 HTML 统计真实条数）
    history = {}
    if os.path.exists(KZ_DIR):
        for fn in sorted(os.listdir(KZ_DIR)):
            if fn.endswith(".html") and fn != "index.html":
                d = fn[:-5]
                try:
                    datetime.strptime(d, "%Y-%m-%d")
                    # 统计该期实际条数（展开全文个数 = 有全文的条数）
                    try:
                        with open(os.path.join(KZ_DIR, fn), encoding="utf-8") as hf:
                            hc = hf.read()
                        cnt = hc.count("展开全文")
                        history[d] = str(cnt) if cnt > 0 else "?"
                    except Exception:
                        history[d] = "?"
                except ValueError:
                    pass
    history[date_str] = str(total)

    index_html = generate_index(history)
    index_path = os.path.join(BASE_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"✅ 索引页已更新: {index_path}（{len(history)} 期）")


if __name__ == "__main__":
    main()
