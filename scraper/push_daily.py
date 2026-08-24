#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""哈萨克斯坦每日要闻 - 飞书日报推送模块

功能：日报生成后，通过独立飞书应用机器人（缓冲机器人）向指定人员推送消息卡片。
设计目标（用户拍板）：
- 方案 A：独立自建应用机器人（非 Hermes 主 bot），权限隔离
- 卡片样式：interactive 消息卡片，内容=文字通知 + 「打开日报」按钮（跳转首页）
- 目标人员：由 FEISHU_PUSH_OPEN_IDS 配置（逗号分隔的 open_id 列表）
- 未配置时静默跳过（不阻断日报流水线）

配置（~/.hermes/.env 或环境变量）：
- FEISHU_PUSH_APP_ID     新机器人应用的 App ID
- FEISHU_PUSH_APP_SECRET 新机器人应用的 App Secret
- FEISHU_PUSH_OPEN_IDS   接收人 open_id 列表（逗号分隔），如 "ou_xxx1,ou_xxx2"

用法：python3 scraper/push_daily.py [--date 2026-08-24] [--homepage https://...]
"""
import json
import os
import sys
import urllib.request
from datetime import datetime

# ============ 配置读取 ============
def load_env():
    """读取 ~/.hermes/.env 中的配置（不污染环境变量）"""
    env = {}
    env_path = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def get_config():
    env = load_env()
    app_id = env.get("FEISHU_PUSH_APP_ID", "")
    app_secret = env.get("FEISHU_PUSH_APP_SECRET", "")
    open_ids = [x.strip() for x in env.get("FEISHU_PUSH_OPEN_IDS", "").split(",") if x.strip()]
    return app_id, app_secret, open_ids


# ============ 飞书 API ============
def get_tenant_token(app_id: str, app_secret: str) -> str:
    """获取 tenant_access_token（2 小时有效）"""
    payload = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    if data.get("code") != 0:
        raise RuntimeError(f"获取 token 失败: {data.get('msg')}")
    return data["tenant_access_token"]


def send_card(token: str, open_id: str, card_content: dict) -> dict:
    """发送消息卡片到指定用户（单聊）"""
    payload = json.dumps({
        "receive_id": open_id,
        "msg_type": "interactive",
        "content": json.dumps(card_content, ensure_ascii=False),
    }).encode()
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


# ============ 卡片构造 ============
def build_card(date_display: str, total: int, counts: dict, homepage_url: str) -> dict:
    """构造日报卡片（文字通知 + 打开日报按钮）"""
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📰 哈萨克斯坦每日要闻日报"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**{date_display}日报** 已更新 📌\n\n"
                        f"今日共 **{total} 条** 要闻"
                        f"（内政 {counts.get('politics_domestic', 0)} · "
                        f"外交 {counts.get('politics_foreign', 0)} · "
                        f"金融 {counts.get('finance', 0)} · "
                        f"矿产 {counts.get('mining', 0)}）\n\n"
                        f"点击下方按钮查看完整内容："
                    ),
                },
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "📖 打开日报"},
                        "type": "primary",
                        "url": homepage_url,
                    }
                ],
            },
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": f"由 Hermes 自动推送 · {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
                ],
            },
        ],
    }


# ============ 主流程 ============
def main():
    # 1. 配置检查（未配置 → 静默跳过，不阻断流水线）
    app_id, app_secret, open_ids = get_config()
    if not app_id or not app_secret:
        print("⏭️  推送未配置（FEISHU_PUSH_APP_ID/SECRET 缺失），跳过推送")
        return
    if not open_ids:
        print("⏭️  推送未配置（FEISHU_PUSH_OPEN_IDS 为空），跳过推送")
        return

    # 2. 参数（日期 / 首页链接）
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--homepage", default="https://macmini9330.github.io/news-daily/")
    args = parser.parse_args()

    # 3. 日报统计数据（读 analyze 产物）
    counts = {"politics_domestic": 0, "politics_foreign": 0, "finance": 0, "mining": 0}
    total = 0
    analyzed_path = "/tmp/kz_articles_analyzed.json"
    if os.path.exists(analyzed_path):
        try:
            with open(analyzed_path, encoding="utf-8") as f:
                data = json.load(f)
            for k in counts:
                counts[k] = len(data.get("sections", {}).get(k, []))
            total = sum(counts.values())
        except Exception as e:
            print(f"⚠️ 读取分析产物失败（用 0 计数）: {e}")

    d = datetime.strptime(args.date, "%Y-%m-%d")
    date_display = f"{d.year}年{d.month}月{d.day}日"

    # 4. 构造卡片 + 发送
    card = build_card(date_display, total, counts, args.homepage)
    try:
        token = get_tenant_token(app_id, app_secret)
        ok, fail = 0, 0
        for oid in open_ids:
            try:
                resp = send_card(token, oid, card)
                if resp.get("code") == 0:
                    ok += 1
                else:
                    fail += 1
                    print(f"  ⚠️ 发送失败 {oid}: {resp.get('msg')}")
            except Exception as e:
                fail += 1
                print(f"  ⚠️ 发送异常 {oid}: {e}")
        print(f"✅ 日报推送完成: 成功 {ok} / 失败 {fail}（{len(open_ids)} 人）")
    except Exception as e:
        print(f"❌ 推送失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
