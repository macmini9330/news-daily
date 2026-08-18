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
:root {
  --bg: #f5f6fa;
  --card: #ffffff;
  --text: #1a1a2e;
  --muted: #666;
  --accent: #1e5eff;
  --border: #e2e5ee;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 16px 60px;
}
.header {
  text-align: center;
  padding: 32px 20px;
  background: linear-gradient(135deg, #1e5eff, #6a5cff);
  border-radius: 16px;
  color: #fff;
  margin-bottom: 28px;
}
.header h1 { font-size: 24px; margin-bottom: 8px; }
.header .date { font-size: 15px; opacity: 0.9; }
.header .meta { font-size: 13px; opacity: 0.75; margin-top: 6px; }
.stats {
  display: flex;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 16px;
}
.stat {
  background: rgba(255,255,255,0.15);
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 13px;
}
.section {
  background: var(--card);
  border-radius: 14px;
  padding: 22px 24px;
  margin-bottom: 22px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  border: 1px solid var(--border);
}
.section h2 {
  font-size: 18px;
  padding-bottom: 12px;
  margin-bottom: 16px;
  border-bottom: 2px solid var(--accent);
  color: var(--accent);
}
.article {
  padding: 14px 0;
  border-bottom: 1px dashed var(--border);
}
.article:last-child { border-bottom: none; }
.article .title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 6px;
}
.article .title a {
  color: var(--text);
  text-decoration: none;
}
.article .title a:hover { color: var(--accent); }
.article .meta {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 8px;
}
.article .points {
  list-style: none;
  padding-left: 0;
}
.article .points li {
  font-size: 14px;
  padding-left: 18px;
  position: relative;
  margin-bottom: 4px;
}
.article .points li::before {
  content: "▸";
  color: var(--accent);
  position: absolute;
  left: 2px;
}
.article .impact {
  margin-top: 8px;
  font-size: 13px;
  color: #444;
  background: #f0f4ff;
  border-left: 3px solid var(--accent);
  padding: 8px 12px;
  border-radius: 0 8px 8px 0;
}
.article .impact b { color: var(--accent); }
.article .summary {
  margin-top: 8px;
  font-size: 14px;
  color: #333;
  background: #fafbfd;
  border: 1px solid var(--border);
  padding: 10px 14px;
  border-radius: 8px;
  line-height: 1.8;
}
.article .summary b { color: var(--accent); }
.summary-toggle {
  margin-top: 6px;
  font-size: 13px;
  color: var(--accent);
  cursor: pointer;
  user-select: none;
  display: inline-block;
  padding: 2px 0;
}
.summary-toggle:hover { text-decoration: underline; }
.summary-toggle .arrow {
  display: inline-block;
  transition: transform 0.2s;
  margin-right: 4px;
}
.summary-toggle.open .arrow { transform: rotate(90deg); }
.full-content {
  display: none;
  margin-top: 10px;
  font-size: 14px;
  line-height: 1.9;
  color: #333;
  background: #f7f8fa;
  border: 1px dashed var(--border);
  border-radius: 8px;
  padding: 12px 16px;
  white-space: pre-wrap;
}
.full-content.show { display: block; }
.source-link {
  font-size: 12px;
  color: var(--muted);
  margin-left: 8px;
}
.source-link a { color: var(--accent); text-decoration: none; }
.source-link a:hover { text-decoration: underline; }
.empty {
  color: var(--muted);
  font-size: 14px;
  padding: 12px 0;
  font-style: italic;
}
.footer {
  text-align: center;
  font-size: 12px;
  color: var(--muted);
  margin-top: 32px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
.footer a { color: var(--accent); text-decoration: none; }
"""


def esc(text: str) -> str:
    """HTML 转义"""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_daily_html(analyzed: dict, date_str: str) -> str:
    """生成单日日报 HTML"""
    sections = analyzed["sections"]
    total = sum(len(v) for v in sections.values())

    # 各板块统计
    stats_html = ""
    for sec in SECTIONS:
        cnt = len(sections.get(sec["id"], []))
        if cnt > 0:
            stats_html += f'<span class="stat">{sec["icon"]} {sec["name"].split("（")[0]} {cnt} 条</span>'

    # 各板块内容
    sections_html = ""
    for sec in SECTIONS:
        items = sections.get(sec["id"], [])
        sections_html += f'<div class="section"><h2>{sec["icon"]} {sec["num"]}、{esc(sec["name"])}</h2>\n'
        if not items:
            sections_html += '<div class="empty">今日暂无此类新闻</div>\n'
        else:
            for i, it in enumerate(items, 1):
                title = esc(it["title"])
                url = it["url"]
                time_s = it.get("time", "")[5:16].replace("-", "/")
                source = esc(it.get("source", ""))
                sections_html += f'<div class="article">\n'
                sections_html += f'<div class="title">{i}. <a href="{url}" target="_blank">{title}</a></div>\n'
                sections_html += f'<div class="meta">{source} · {time_s}<span class="source-link"><a href="{url}" target="_blank">来源链接 ↗</a></span></div>\n'
                if it.get("summary"):
                    sections_html += f'<div class="summary"><b>内容摘要：</b>{esc(it["summary"])}</div>\n'
                    if it.get("full_content"):
                        sections_html += f'<div class="summary-toggle" onclick="toggleContent(this)"><span class="arrow">▸</span>展开全文</div>\n'
                        sections_html += f'<div class="full-content">{esc(it["full_content"])}</div>\n'
                if it.get("points"):
                    sections_html += '<ul class="points">\n'
                    for p in it["points"]:
                        sections_html += f'<li>{esc(p)}</li>\n'
                    sections_html += '</ul>\n'
                if it.get("impact"):
                    sections_html += f'<div class="impact"><b>影响：</b>{esc(it["impact"])}</div>\n'
                sections_html += '</div>\n'
        sections_html += '</div>\n'

    # 日期显示
    d = datetime.strptime(date_str, "%Y-%m-%d")
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
<div class="header">
  <h1>🇰🇿 哈萨克斯坦每日要闻</h1>
  <div class="date">{date_display}</div>
  <div class="meta">数据来源：哈通社（Kazinform）等 · 自动生成 · 仅供研究参考</div>
  <div class="stats">{stats_html}</div>
</div>
{sections_html}
<div class="footer">
  <p>哈萨克斯坦每日要闻 · 由 Hermes 自动生成 · <a href="index.html">查看往期</a></p>
  <p>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
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
body {{ font-family: -apple-system, "PingFang SC", sans-serif; max-width: 700px; margin: 0 auto; padding: 40px 16px; background: #f5f6fa; color: #1a1a2e; }}
h1 {{ color: #1e5eff; margin-bottom: 8px; }}
.sub {{ color: #666; margin-bottom: 24px; }}
ul {{ list-style: none; padding: 0; }}
li {{ background: #fff; border: 1px solid #e2e5ee; border-radius: 10px; padding: 14px 18px; margin-bottom: 10px; }}
li a {{ color: #1a1a2e; text-decoration: none; font-size: 15px; }}
li a:hover {{ color: #1e5eff; }}
</style>
</head>
<body>
<h1>🇰🇿 哈萨克斯坦每日要闻</h1>
<div class="sub">每日更新 · 自动生成 · 涵盖内政/外交/金融/矿产资源四大板块</div>
<ul>
{rows}
</ul>
</body>
</html>
"""
    return html


def main():
    with open("/tmp/kz_articles_analyzed.json", encoding="utf-8") as f:
        analyzed = json.load(f)

    # 用新闻数据的日期（取所有新闻中出现最多的日期），避免凌晨跨日错位
    from collections import Counter
    date_counter = Counter()
    for sid, items in analyzed["sections"].items():
        for it in items:
            t = it.get("time", "")
            if len(t) >= 10:
                date_counter[t[:10]] += 1
    if date_counter:
        date_str = date_counter.most_common(1)[0][0]
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"📅 使用新闻日期: {date_str}（各日期计数: {dict(date_counter)}）")
    os.makedirs(KZ_DIR, exist_ok=True)

    # 生成单日页
    html = generate_daily_html(analyzed, date_str)
    daily_path = os.path.join(KZ_DIR, f"{date_str}.html")
    with open(daily_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 日报已生成: {daily_path}")

    # 统计今日条数
    total = sum(len(v) for v in analyzed["sections"].values())

    # 生成/更新索引页（读取已有历史）
    history = {}
    if os.path.exists(KZ_DIR):
        for fn in sorted(os.listdir(KZ_DIR)):
            if fn.endswith(".html") and fn != "index.html":
                d = fn[:-5]
                try:
                    datetime.strptime(d, "%Y-%m-%d")
                    history[d] = "当日"
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
