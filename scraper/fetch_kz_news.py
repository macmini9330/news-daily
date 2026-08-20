#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""哈萨克斯坦每日要闻 - 新闻抓取模块 v2

信息源:
1. 中文版 cn.inform.kz/lenta + 分板块（已有，约22条/天，精选翻译）
2. 俄语版 www.inform.kz/ru/lenta 分页（新增，约150条/天，全量）

输出: JSON 列表 [{title, url, source, lang, time, category, content}]
"""
import gzip
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# ============ 抓取时间窗口 ============
# 每日 09:00 运行，抓取前一日 09:00 → 当日 09:00 发布的新闻（精确 24 小时窗口）
CUTOFF_HOUR = 9  # 窗口边界小时


def window_bounds() -> tuple:
    """窗口 [起点, 终点]（北京时间）

    规则：日报日期 = 运行日；窗口终点 = 日报日期当日 09:00；起点 = 终点 - 24h。
    例如 8/20 生成 8/20 日报 → 窗口 = 8/19 09:00 ~ 8/20 09:00（北京时间）。
    """
    now = datetime.now()
    # 窗口终点 = 今日 09:00（北京时间）；若未到 9 点（凌晨），仍锚定今日 9 点
    end = datetime(now.year, now.month, now.day, CUTOFF_HOUR, 0)
    start = end - timedelta(days=1)
    return start, end


def window_start() -> datetime:
    """窗口起点（兼容旧调用）"""
    return window_bounds()[0]


def window_end() -> datetime:
    """窗口终点（北京时间 09:00）"""
    return window_bounds()[1]


# ============ 信息源配置 ============
SOURCES = {
    "lenta": "https://cn.inform.kz/lenta",  # 中文版所有新闻
    "president": "https://cn.inform.kz/category/section_s22796",  # 总统
    "government": "https://cn.inform.kz/category/section_s22798",  # 政府
    "parliament": "https://cn.inform.kz/category/section_s22801",  # 议会
    "international": "https://cn.inform.kz/category/section_s22880",  # 国际
    "economy": "https://cn.inform.kz/category/section_s22810",  # 经济
    "events": "https://cn.inform.kz/category/section_s25828",  # 事件
}

# 俄语月份名 → 数字
RU_MONTHS = {
    "Января": 1, "Февраля": 2, "Марта": 3, "Апреля": 4, "Мая": 5, "Июня": 6,
    "Июля": 7, "Августа": 8, "Сентября": 9, "Октября": 10, "Ноября": 11, "Декабря": 12,
}


def fetch_html(url: str, timeout: int = 20) -> str:
    """抓取网页 HTML（处理 gzip + 大页面）"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Encoding": "gzip",
        "Connection": "close",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(5_000_000)
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data.decode("utf-8", errors="ignore")


def parse_time(time_str: str) -> str:
    """解析时间字符串 → ISO 格式（**北京时间**）

    哈通社显示的是阿斯塔纳时间 (UTC+5)，北京时间 = UTC+8。
    因此解析后统一 +3 小时，保证窗口过滤与展示均为北京时间。
    中文: "08:32, 18 8月 2026" 俄语: "21:38, 18 Августа 2026"
    """
    time_str = time_str.strip()
    iso_str = None
    # 中文格式
    m = re.match(r'(\d{2}:\d{2}),\s*(\d{1,2})\s*(\d{1,2})月\s*(\d{4})', time_str)
    if m:
        hhmm, day, month, year = m.groups()
        iso_str = f"{year}-{int(month):02d}-{int(day):02d} {hhmm}"
    else:
        # 俄语格式
        m = re.match(r'(\d{2}:\d{2}),\s*(\d{1,2})\s+(\w+)\s+(\d{4})', time_str)
        if m:
            hhmm, day, month_name, year = m.groups()
            month = RU_MONTHS.get(month_name.capitalize())
            if month:
                iso_str = f"{year}-{month:02d}-{int(day):02d} {hhmm}"
    if iso_str:
        dt = datetime.strptime(iso_str, "%Y-%m-%d %H:%M")
        # 阿斯塔纳 UTC+5 → 北京 UTC+8
        dt = dt + timedelta(hours=3)
        return dt.strftime("%Y-%m-%d %H:%M")
    return time_str


def parse_article_block(html: str, base_url: str, lang: str) -> list:
    """从列表页 HTML 提取文章（支持中文版/俄语版）

    结构: <a href="/news/xxx/" class="news-card">
            <time class="meta-date">08:32, 18 8月 2026</time>
            <h3 class="card-title">标题</h3>
    """
    articles = []
    blocks = re.findall(
        r'<a href="(/news/[^"]+|/ru/[^"]+)"[^>]*class="news-card".*?'
        r'<time class="meta-date">([^<]+)</time>.*?'
        r'<h3[^>]*class="card-title[^"]*">\s*([^<]+?)\s*</h3>',
        html, flags=re.S
    )
    for rel_url, time_str, title in blocks:
        # 相对路径 → 绝对路径
        if rel_url.startswith("/ru/"):
            url = f"https://www.inform.kz{rel_url}"
        else:
            url = f"https://cn.inform.kz{rel_url}"
        title = re.sub(r'\s+', ' ', title).strip()
        articles.append({
            "title": title,
            "url": url,
            "time": parse_time(time_str),
            "lang": lang,
        })
    return articles


def collect_chinese() -> list:
    """抓取中文版（lenta + 板块，约22条）"""
    all_articles = []
    seen = set()
    cutoff = window_start()
    cutoff_end = window_end()
    for name, url in SOURCES.items():
        try:
            html = fetch_html(url)
            arts = parse_article_block(html, url, "zh")
            for a in arts:
                if a["url"] not in seen:
                    seen.add(a["url"])
                    # 时间过滤：只保留窗口内 [start, end]
                    try:
                        at = datetime.strptime(a["time"], "%Y-%m-%d %H:%M")
                        if at < cutoff or at > cutoff_end:
                            continue
                    except ValueError:
                        pass
                    a["source"] = "哈通社中文版"
                    all_articles.append(a)
        except Exception as e:
            print(f"  ⚠️ 中文源 {name} 失败: {e}", file=sys.stderr)
    return all_articles


def collect_russian(max_pages: int = 10) -> list:
    """抓取俄语版 lenta 分页（每页24条，翻页直到非当天）

    lenta 首页: https://www.inform.kz/ru/lenta
    分页:       https://www.inform.kz/ru/lenta/?page=2
    """
    all_articles = []
    seen = set()
    today = datetime.now()
    cutoff = window_start()
    cutoff_end = window_end()

    for page in range(1, max_pages + 1):
        url = "https://www.inform.kz/ru/lenta" if page == 1 else f"https://www.inform.kz/ru/lenta/?page={page}"
        try:
            html = fetch_html(url)
            arts = parse_article_block(html, url, "ru")
            if not arts:
                print(f"  ✅ 俄语版第{page}页无文章，停止翻页")
                break
            # 记录最早时间判断是否还属于当天
            newest = arts[0]["time"]
            oldest = arts[-1]["time"]
            print(f"  📄 俄语版第{page}页: {len(arts)}条 ({newest} ~ {oldest})")

            for a in arts:
                if a["url"] in seen:
                    continue
                seen.add(a["url"])
                # 时间过滤：只保留窗口内 [start, end]
                try:
                    at = datetime.strptime(a["time"], "%Y-%m-%d %H:%M")
                    if at < cutoff or at > cutoff_end:
                        continue
                except ValueError:
                    pass
                a["source"] = "哈通社俄语版"
                all_articles.append(a)

            # 判断是否翻完窗口：如果本页最早时间早于窗口起点 且已翻过至少2页
            try:
                oldest_dt = datetime.strptime(oldest, "%Y-%m-%d %H:%M")
                if oldest_dt < cutoff and page >= 2:
                    print(f"  ✅ 第{page}页已含窗口外新闻，停止翻页")
                    break
            except ValueError:
                break

            time.sleep(0.5)  # 礼貌间隔
        except Exception as e:
            print(f"  ⚠️ 俄语版第{page}页失败: {e}", file=sys.stderr)
            break

    return all_articles


def fetch_article_content(url: str, lang: str = "zh") -> str:
    """抓取文章正文（从 article__content 提取完整段落）"""
    try:
        html = fetch_html(url)
        m = re.search(r'<div class="article__content">(.*?)</div>\s*</div>', html, flags=re.S)
        if not m:
            m = re.search(r'<div class="article__content">(.*?)(?:<div class="article__tags"|$)', html, flags=re.S)
        if not m:
            return ""
        body_html = m.group(1)
        paras = re.findall(r'<p[^>]*>(.*?)</p>', body_html, flags=re.S)
        texts = []
        for p in paras:
            p = re.sub(r'<[^>]+>', '', p)
            p = re.sub(r'\s+', ' ', p).strip()
            if p:
                texts.append(p)
        if texts:
            return "\n".join(texts[:15])
        return ""
    except Exception as e:
        print(f"  ⚠️ 详情页失败 {url}: {e}", file=sys.stderr)
        return ""


def collect_articles() -> list:
    """主收集：中文版 + 俄语版"""
    print("📡 抓取中文版（精选翻译）...")
    zh_articles = collect_chinese()
    print(f"  → 中文版 {len(zh_articles)} 条")

    print("📡 抓取俄语版（全量分页）...")
    ru_articles = collect_russian()
    print(f"  → 俄语版 {len(ru_articles)} 条")

    # 合并（中文版优先，俄语版补充）
    seen_urls = {a["url"] for a in zh_articles}
    all_articles = list(zh_articles)
    for a in ru_articles:
        if a["url"] not in seen_urls:
            seen_urls.add(a["url"])
            all_articles.append(a)

    print(f"\n📥 总计 {len(all_articles)} 条（中文{len(zh_articles)} + 俄语{len(ru_articles)}）")
    return all_articles


def main():
    articles = collect_articles()

    print(f"\n=== 前 15 条 ===")
    for a in articles[:15]:
        print(f"  [{a['lang']}|{a['time']}] {a['title'][:50]}")
        print(f"    {a['url']}")

    # 保存原始数据（不含正文，正文在分析时按需抓取）
    out = {
        "fetched_at": datetime.now().isoformat(),
        "count": len(articles),
        "articles": [{k: v for k, v in a.items() if k != "content"} for a in articles],
    }
    with open("/tmp/kz_articles_raw.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 原始数据已保存: /tmp/kz_articles_raw.json（{len(articles)} 条）")


if __name__ == "__main__":
    main()
