#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""哈萨克斯坦每日要闻 - 汇率抓取模块

数据源: open.er-api.com（免费、无需 key、国内可达）
展示形式（用户拍板）: 以人民币为基准的三币对照
    人民币 : 美元 : 坚戈 = 1 : 0.1482 : 67.7645
    （即 1 人民币 = 0.1482 美元 = 67.7645 坚戈）

输出: /tmp/kz_rates.json
    {"cny": 1, "usd": 0.1482, "kzt": 67.7645, "fetched_at": "...", "api_time": "..."}
失败时: 不写文件（generate 读到就显示，读不到就隐藏卡片）
"""
import json
import sys
import urllib.request
from datetime import datetime

API_URL = "https://open.er-api.com/v6/latest/KZT"  # base=KZT, rates={CNY:.., USD:..}
OUT_PATH = "/tmp/kz_rates.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def fetch_rates():
    """抓取汇率，返回 {cny:1, usd:.., kzt:..}；失败返回 None"""
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))

        if data.get("result") != "success":
            print(f"⚠️ 汇率 API 返回异常: {data.get('result')}", file=sys.stderr)
            return None

        # 1 KZT = X CNY / X USD
        cny_per_kzt = data["rates"]["CNY"]
        usd_per_kzt = data["rates"]["USD"]

        # 以人民币为基准: 1 CNY = ? USD = ? KZT
        kzt_per_cny = 1.0 / cny_per_kzt      # 1 人民币 = 多少坚戈
        usd_per_cny = usd_per_kzt / cny_per_kzt  # 1 人民币 = 多少美元

        return {
            "cny": 1.0,
            "usd": round(usd_per_cny, 4),
            "kzt": round(kzt_per_cny, 4),
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "api_time": data.get("time_last_update_utc", ""),
        }
    except Exception as e:
        print(f"⚠️ 汇率抓取失败: {e}", file=sys.stderr)
        return None


def main():
    rates = fetch_rates()
    if rates is None:
        print("❌ 汇率获取失败，不写入文件（首页将不显示汇率卡片）")
        sys.exit(1)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rates, f, ensure_ascii=False, indent=2)
    print(f"✅ 汇率已保存: {OUT_PATH}")
    print(f"   人民币 : 美元 : 坚戈 = {rates['cny']} : {rates['usd']} : {rates['kzt']}")


if __name__ == "__main__":
    main()
