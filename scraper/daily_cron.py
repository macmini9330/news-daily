#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""哈萨克斯坦每日要闻 - cron 封装脚本（no_agent 模式）

用途：cron 直接执行此脚本，无需 LLM 参与，彻底消除跑偏。
- 运行 run_daily.py 完整流水线（抓取→分析→生成→push）
- 成功：stdout 输出简短中文摘要（各板块条数+链接），由 cron 投递到飞书
- 失败：stdout 输出错误信息，cron 投递错误告警

用法: python3 scraper/daily_cron.py
"""
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timedelta

# 板块名从 sections.py 读取（单一来源，勿在此重复定义）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from sections import SECTIONS
    SECTION_NAMES = {s["id"]: s["short"] for s in SECTIONS}
except ImportError:
    # 兜底（理论上不会发生，sections.py 与 daily_cron.py 同目录）
    SECTION_NAMES = {
        "politics_domestic": "内政",
        "politics_foreign": "外交",
        "finance": "金融",
        "mining": "矿产",
    }

BASE_DIR = os.path.expanduser("~/Documents/news-daily")
SCRAPER_DIR = os.path.join(BASE_DIR, "scraper")
PAGES_URL = "https://macmini9330.github.io/news-daily/"


def run_pipeline() -> bool:
    """运行完整流水线，返回是否成功"""
    r = subprocess.run(
        [sys.executable, os.path.join(SCRAPER_DIR, "run_daily.py")],
        cwd=BASE_DIR, capture_output=True, text=True, timeout=900,  # 15 分钟上限
    )
    if r.returncode == 0:
        return True
    # 失败：输出错误信息
    print(f"❌ 日报生成失败（exit {r.returncode}）")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    stderr_tail = (r.stderr or "")[-800:]
    stdout_tail = (r.stdout or "")[-800:]
    if stderr_tail.strip():
        print(f"\n错误详情:\n{stderr_tail}")
    if stdout_tail.strip():
        print(f"\n输出末尾:\n{stdout_tail}")
    return False


def build_summary() -> str:
    """从分析结果构建投递摘要"""
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    # 窗口：前一日 09:00 → 当日 09:00（北京时间），与 fetch.window_bounds 一致
    prev_day = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        with open("/tmp/kz_articles_analyzed.json", encoding="utf-8") as f:
            data = json.load(f)
        sections = data.get("sections", {})
        parts = []
        total = 0
        for sid, name in SECTION_NAMES.items():
            cnt = len(sections.get(sid, []))
            total += cnt
            parts.append(f"{name}{cnt}")
        # 日期规则：发布日 = 运行日
        return (
            f"📰 哈萨克斯坦每日要闻（{today_str} 日报）已生成 ✅\n"
            f"共 {total} 条：{' / '.join(parts)}\n"
            f"涵盖：{prev_day} 9:00 → {today_str} 9:00（北京时间）\n"
            f"查看: {PAGES_URL}"
        )
    except Exception as e:
        return f"⚠️ 日报已生成，但摘要读取失败: {e}\n查看: {PAGES_URL}"


def main():
    # no_agent 模式：stdout 全文投递，只输出最终结果（摘要或错误），不输出过程日志
    ok = run_pipeline()
    if ok:
        print(build_summary())
    # 失败时 run_pipeline 已输出错误，非零退出触发告警
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(f"❌ 日报 cron 异常: {traceback.format_exc()}")
        sys.exit(1)
