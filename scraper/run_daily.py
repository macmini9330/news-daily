#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""哈萨克斯坦每日要闻 - 主流水线

一键执行: 抓取 → 分类分析 → 生成HTML → git推送 → Pages部署

用法: python3 scraper/run_daily.py [--no-push]
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

BASE_DIR = os.path.expanduser("~/Documents/news-daily")
SCRAPER_DIR = os.path.join(BASE_DIR, "scraper")


def run_step(name: str, cmd: list, timeout: int = 600) -> bool:
    """执行子步骤（analyze 阶段给 900s，LLM 逐条翻译耗时长）"""
    print(f"\n{'='*50}")
    print(f"▶️  {name}")
    print(f"{'='*50}")
    r = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True, timeout=timeout)
    if r.stdout:
        print(r.stdout[-2000:])
    if r.returncode != 0:
        print(f"❌ {name} 失败:")
        print(r.stderr[-2000:] if r.stderr else "无错误输出")
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-push", action="store_true", help="只生成不推送")
    args = parser.parse_args()

    print(f"🇰🇿 哈萨克斯坦每日要闻生成器")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 抓取
    if not run_step("抓取新闻", [sys.executable, os.path.join(SCRAPER_DIR, "fetch_kz_news.py")]):
        sys.exit(1)

    # 1.5 汇率（失败不阻断——首页汇率卡片可选显示）
    run_step("抓取汇率", [sys.executable, os.path.join(SCRAPER_DIR, "fetch_rates.py")], timeout=30)

    # 2. 分析（LLM 逐条翻译，221条实测需 15-25 分钟；1800s=30分钟上限）
    if not run_step("LLM 分类分析", [sys.executable, os.path.join(SCRAPER_DIR, "analyze_kz_news.py")], timeout=1800):
        sys.exit(1)

    # 3. 生成 HTML
    if not run_step("生成 HTML", [sys.executable, os.path.join(SCRAPER_DIR, "generate_kz_html.py")]):
        sys.exit(1)

    # 3.5 质量检查（通过才继续；失败终止 + 只通知管理员）
    today = datetime.now().strftime("%Y-%m-%d")
    qc = subprocess.run(
        [sys.executable, os.path.join(SCRAPER_DIR, "check_quality.py"), "--date", today],
        cwd=BASE_DIR, capture_output=True, text=True, timeout=30)
    if qc.stdout:
        print(qc.stdout)
    if qc.returncode != 0:
        reason = (qc.stdout or qc.stderr or "未知原因").strip()[-500:]
        print(f"\n🚫 日报质量检查未通过，终止流程（不推送、不发布）")
        print(f"   原因: {reason}")
        # 只通知管理员（其他人员静默）
        run_step("管理员告警", [sys.executable, os.path.join(SCRAPER_DIR, "push_daily.py"),
                                "--date", today, "--alert", reason], timeout=60)
        sys.exit(1)

    # 4. 推送（可选）
    if not args.no_push:
        if not run_step("git 提交推送", ["git", "add", "-A"]):
            # 没有新增内容也可能 add 失败，继续尝试 commit
            pass
        # commit + push
        r = subprocess.run(["git", "commit", "-m", f"daily news {datetime.now().strftime('%Y-%m-%d')}"],
                           cwd=BASE_DIR, capture_output=True, text=True, timeout=60)
        if r.returncode != 0 and "nothing to commit" not in r.stderr and "nothing to commit" not in r.stdout:
            print(f"⚠️ commit 输出: {r.stdout[:200]}{r.stderr[:200]}")
        r2 = subprocess.run(["git", "push", "origin", "main"],
                            cwd=BASE_DIR, capture_output=True, text=True, timeout=120)
        if r2.returncode != 0:
            print(f"❌ push 失败: {r2.stderr[:300]}")
            sys.exit(1)
        print(f"✅ 已推送到 GitHub Pages")

    # 4.5 飞书推送（可选，失败不阻断——独立缓冲机器人推送给指定人员）
    run_step("飞书推送", [sys.executable, os.path.join(SCRAPER_DIR, "push_daily.py")], timeout=60)

    print(f"\n🎉 完成! 访问 https://macmini9330.github.io/news-daily/")


if __name__ == "__main__":
    main()
