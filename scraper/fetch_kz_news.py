#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""哈萨克斯坦每日要闻 - 新闻抓取模块
从哈通社(Kazinform)中文版 + 补充源抓取当日新闻
输出: JSON 列表 [{title, url, source, time, category, content}]
"""
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# ============ 信息源配置 ============
SOURCES = {
    "lenta": "https://cn.inform.kz/lenta",  # 所有新闻
    "president": "https://cn.inform.kz/category/section_s22796",  # 总统
    "government": "https://cn.inform.kz/category/section_s22798",  # 政府
    "parliament": "https://cn.inform.kz/category/section_s22801",  # 议会
    "international": "https://cn.inform.kz/category/section_s22880",  # 国际
    "economy": "https://cn.inform.kz/category/section_s22810",  # 经济
    "events": "https://cn.inform.kz/category/section_s25828",  # 事件
}


def fetch_html(url: str, timeout: int = 15) -> str:
    """抓取网页 HTML"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def parse_article_block(html: str) -> list:
    """从列表页 HTML 中提取文章 (title, url, time_str)

    真实结构: <div class="news-category__item">
      <a href="/news/xxx/" class="news-card">
        <time class="meta-date">08:32, 18 8月 2026</time>
        <h3 class="card-title">标题</h3>
    """
    articles = []
    # 按 news-card 块切分
    blocks = re.findall(
        r'<a href="(/news/[^"]+)"[^>]*class="news-card".*?'
        r'<time class="meta-date">([^<]+)</time>.*?'
        r'<h3[^>]*class="card-title[^"]*">\s*([^<]+?)\s*</h3>',
        html, flags=re.S
    )
    for rel_url, time_str, title in blocks:
        url = f"https://cn.inform.kz{rel_url}"
        title = re.sub(r'\s+', ' ', title).strip()
        time_str = time_str.strip()
        # 解析时间 "08:32, 18 8月 2026" → "2026-08-18 08:32"
        m = re.match(r'(\d{2}:\d{2}),\s*(\d{1,2})\s*(\d{1,2})月\s*(\d{4})', time_str)
        if m:
            hhmm, day, month, year = m.groups()
            iso_time = f"{year}-{int(month):02d}-{int(day):02d} {hhmm}"
        else:
            iso_time = time_str
        articles.append({
            "title": title,
            "url": url,
            "time": iso_time,
            "source": "哈通社",
        })
    return articles


def fetch_article_content(url: str) -> str:
    """抓取文章正文（从 article__content 提取完整段落）"""
    try:
        html = fetch_html(url)
        # 锚点：<div class="article__content"> ... </div>
        m = re.search(r'<div class="article__content">(.*?)</div>\s*</div>', html, flags=re.S)
        if not m:
            # 尝试宽松匹配到标签区域前
            m = re.search(r'<div class="article__content">(.*?)(?:<div class="article__tags"|$)', html, flags=re.S)
        if not m:
            return ""
        body_html = m.group(1)
        # 提取所有 <p> 段落
        paras = re.findall(r'<p[^>]*>(.*?)</p>', body_html, flags=re.S)
        texts = []
        for p in paras:
            # 去内嵌标签（链接、图片）
            p = re.sub(r'<[^>]+>', '', p)
            p = re.sub(r'\s+', ' ', p).strip()
            if p:
                texts.append(p)
        # 补充：如果 meta description 有开头（第一段），加到最前
        if texts:
            return "\n".join(texts[:10])
        return ""
    except Exception as e:
        print(f"  ⚠️ 详情页失败 {url}: {e}", file=sys.stderr)
        return ""


def collect_articles(max_per_source: int = 30) -> list:
    """从所有信息源收集当日文章"""
    all_articles = []
    seen_urls = set()
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    for name, url in SOURCES.items():
        try:
            html = fetch_html(url)
            arts = parse_article_block(html)
            # 只保留当天的（或昨天的凌晨的，避免跨日漏抓）
            kept = 0
            for a in arts:
                if a["url"] in seen_urls:
                    continue
                # 时间过滤：当天 或 昨天晚 22:00 后（考虑时区）
                try:
                    at = datetime.strptime(a["time"], "%Y-%m-%d %H:%M")
                    cutoff = today - timedelta(hours=20)  # 往前看20小时
                    if at < cutoff:
                        continue
                except ValueError:
                    pass
                seen_urls.add(a["url"])
                all_articles.append(a)
                kept += 1
                if kept >= max_per_source:
                    break
        except Exception as e:
            print(f"⚠️ 源 {name} 抓取失败: {e}", file=sys.stderr)

    print(f"📥 从 {len(SOURCES)} 个源收集到 {len(all_articles)} 条文章（去重后）")
    return all_articles


def enrich_with_content(articles: list, max_articles: int = 40) -> list:
    """为文章补充正文（最多抓 max_articles 篇详情）"""
    enriched = []
    for i, a in enumerate(articles):
        if i >= max_articles:
            break
        a["content"] = fetch_article_content(a["url"])
        time.sleep(0.3)  # 礼貌间隔，避免被限流
        enriched.append(a)
        if i % 5 == 0:
            print(f"  ...已抓 {i+1}/{min(len(articles), max_articles)} 篇详情")
    return enriched


def main():
    articles = collect_articles()
    print(f"\n=== 示例文章（前10条）===")
    for a in articles[:10]:
        print(f"  [{a['time']}] {a['title'][:50]}")
        print(f"    {a['url']}")

    if articles:
        # 抓取前几篇详情作为内容验证
        print(f"\n=== 验证详情抓取（前3篇）===")
        for a in articles[:3]:
            content = fetch_article_content(a["url"])
            print(f"  {a['title'][:40]}: {len(content)}字符")
            print(f"    {content[:120]}...")

    # 保存原始数据
    out = {
        "fetched_at": datetime.now().isoformat(),
        "count": len(articles),
        "articles": articles,
    }
    with open("/tmp/kz_articles_raw.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 原始数据已保存: /tmp/kz_articles_raw.json")


if __name__ == "__main__":
    main()
