#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""哈萨克斯坦每日要闻 - 日报质量检查

在生成 HTML 后、飞书推送前执行。检查不通过 → exit 1（阻止推送）。

用法: python3 scraper/check_quality.py [--date 2026-08-24]
"""
import argparse
import os
import re
import sys
from datetime import datetime

BASE_DIR = os.path.expanduser("~/Documents/news-daily")


def check(date_str: str) -> tuple:
    """日报质量检查，返回 (是否通过, 问题列表)"""
    issues = []
    kz_file = os.path.join(BASE_DIR, "kz", f"{date_str}.html")

    # 1. 文件存在
    if not os.path.exists(kz_file):
        return False, [f"❌ 当日 HTML 不存在: kz/{date_str}.html"]

    size = os.path.getsize(kz_file)
    if size < 5000:
        issues.append(f"⚠️ 文件过小: {size/1024:.0f}KB（正常应 100KB+）")

    with open(kz_file, encoding="utf-8") as f:
        html = f.read()

    # 2. 板块条数检查
    counts = re.findall(r"\((\d+)\s*条\)", html)
    if not counts:
        issues.append("❌ 未找到板块条数标记")
    else:
        total = sum(int(c) for c in counts)
        if total == 0:
            issues.append("❌ 日报内容为空（0 条）")
        elif total > 300:
            issues.append(f"⚠️ 条数异常多: {total}（正常 30-180）")

    # 3. 空标题检查
    titles = re.findall(r'class="item-title"[^>]*>(.*?)</h3>', html, re.S)
    empty = [t for t in titles if not t.strip()]
    if empty:
        issues.append(f"❌ {len(empty)} 个空标题")

    # 4. 乱码检查
    bad = html.count("\ufffd")
    if bad > 10:
        issues.append(f"⚠️ 检测到 {bad} 个乱码字符")

    # 5. 标题完整性检查（截断的标题如 '...' 结尾可能是 LLM 截断）
    truncated = len(re.findall(r"[^\n]{1,10}\.\.\.</a>", html))
    if truncated > 10:
        issues.append(f"⚠️ {truncated} 个标题疑似截断")

    if issues:
        return False, issues
    return True, ["✅ 全部检查通过"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    ok, results = check(args.date)
    for r in results:
        print(r)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
