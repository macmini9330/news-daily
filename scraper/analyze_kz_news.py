#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""哈萨克斯坦每日要闻 - LLM 分类分析模块

读取 /tmp/kz_articles_raw.json → LLM 按 4 板块分类 → 生成要点+影响分析
输出: /tmp/kz_articles_analyzed.json
"""
import json
import os
import re
import sys
import urllib.request

# ============ DeepSeek API ============
def get_api_key() -> str:
    """从 .env 读取 DeepSeek key"""
    env_path = os.path.expanduser("~/.hermes/.env")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("DEEPSEEK_API_KEY not found in ~/.hermes/.env")


def llm_chat(messages: list, max_tokens: int = 4000, temperature: float = 0.2) -> str:
    """调用 DeepSeek Chat Completions"""
    key = get_api_key()
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
        return data["choices"][0]["message"]["content"]


# ============ 板块定义 ============
SECTIONS = [
    {
        "id": "politics_domestic",
        "name": "政治新闻及分析（内政）",
        "desc": "哈萨克斯坦内政：总统/政府/议会活动、选举、法律政策、国内治理、社会政策",
    },
    {
        "id": "politics_foreign",
        "name": "政治新闻及分析（外交）",
        "desc": "哈萨克斯坦外交：对外关系、国际会议、中哈关系、与各国合作、地缘政治",
    },
    {
        "id": "finance",
        "name": "金融政策新闻及分析",
        "desc": "哈萨克斯坦金融政策：央行、基准利率、汇率、货币政策、金融监管、银行、通胀",
    },
    {
        "id": "mining",
        "name": "矿产资源进出口管制政策新闻及分析",
        "desc": "哈萨克斯坦矿产资源：铀/稀土/钨/铬/锌/铜等矿产，进出口管制、矿业政策、资源出口",
    },
]

# 其他不重要/无关的新闻归为 other（不出现在日报）
OTHER_DESC = "社会/体育/文化/教育/卫生/环境/娱乐等与四板块无关的新闻"


# ============ 分类 + 分析（一次调用处理所有文章）============
def analyze_articles(articles: list) -> dict:
    """用 LLM 对所有文章分类并生成要点+影响分析

    返回: {section_id: [ {title, url, time, source, points[], impact} ]}
    """
    # 精简文章列表给 LLM（标题+全文内容，最多1500字）
    slim = []
    for i, a in enumerate(articles):
        content = (a.get("content") or "")[:1500]
        slim.append({
            "id": i,
            "title": a["title"],
            "time": a["time"],
            "source": a["source"],
            "content": content,
        })

    sections_desc = "\n".join(
        [f"- {s['id']}: {s['name']}（{s['desc']}）" for s in SECTIONS]
    )

    prompt = f"""你是哈萨克斯坦政策研究分析师。请将以下今日哈萨克斯坦新闻分类并分析。

## 分类规则
- {sections_desc}
- other: {OTHER_DESC}

每条新闻只能归入一个板块。与四板块都无关的归入 other。

## 输出格式（严格 JSON）
{{
  "politics_domestic": [
    {{
      "id": 0,
      "summary": "内容摘要（100-150字，保留关键数字和事实：金额/百分比/日期/人物/机构）",
      "points": ["要点1（15-30字，从原文提炼具体事实）", "要点2", "要点3"],
      "impact": "影响分析（50-80字：对哈国政治/经济/外交/矿产格局的影响）"
    }}
  ],
  "politics_foreign": [...],
  "finance": [...],
  "mining": [...]
}}
注意：other 板块的新闻不要输出。每条新闻 summary 100-150字、points 3-5 条、impact 必须基于事实、避免空话。

## 新闻列表
{json.dumps(slim, ensure_ascii=False, indent=1)}
"""

    print("🤖 调用 LLM 分类分析...")
    result = llm_chat([
        {"role": "system", "content": "你输出严格 JSON，不要输出其他内容。"},
        {"role": "user", "content": prompt},
    ], max_tokens=8000, temperature=0.2)

    # 解析 JSON（处理可能的 markdown 包裹）
    result = result.strip()
    if result.startswith("```"):
        result = re.sub(r'^```(?:json)?\s*', '', result)
        result = re.sub(r'\s*```$', '', result)
    try:
        data = json.loads(result)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}", file=sys.stderr)
        print(f"LLM 输出前 500 字符: {result[:500]}", file=sys.stderr)
        # 尝试提取 JSON 部分
        m = re.search(r'\{.*\}', result, flags=re.S)
        if m:
            data = json.loads(m.group(0))
        else:
            raise

    # 防御：如果 data 是列表（LLM 可能返回数组），转成 dict
    if isinstance(data, list):
        print("⚠️ LLM 返回了数组，尝试转换", file=sys.stderr)
        new_data = {}
        for item in data:
            if isinstance(item, dict):
                for k, v in item.items():
                    new_data[k] = v
        data = new_data
    # 防御：键可能是 dict（嵌套异常）
    for sid in [s["id"] for s in SECTIONS]:
        if sid not in data:
            # 尝试从 data 的任意值中找
            for k, v in list(data.items()):
                if isinstance(v, list) and v and isinstance(v[0], dict) and "points" in v[0]:
                    if sid not in data:
                        data[sid] = v

    # 把 id 映射回完整文章数据
    by_id = {i: a for i, a in enumerate(articles)}
    result_data = {}
    for sec in SECTIONS:
        sid = sec["id"]
        items = data.get(sid, [])
        full_items = []
        for it in items:
            idx = it.get("id")
            orig = by_id.get(idx, {})
            full_items.append({
                "title": orig.get("title", ""),
                "url": orig.get("url", ""),
                "time": orig.get("time", ""),
                "source": orig.get("source", ""),
                "summary": it.get("summary", ""),
                "points": it.get("points", []),
                "impact": it.get("impact", ""),
            })
        result_data[sid] = full_items

    # 统计
    total = sum(len(v) for v in result_data.values())
    print(f"✅ 分类完成: 内政{len(result_data['politics_domestic'])} 外交{len(result_data['politics_foreign'])} 金融{len(result_data['finance'])} 矿产{len(result_data['mining'])} 共{total}条")

    return result_data


def main():
    with open("/tmp/kz_articles_raw.json", encoding="utf-8") as f:
        raw = json.load(f)

    articles = raw["articles"]
    print(f"📄 待分析文章: {len(articles)} 条")

    # 分批处理（每批最多 25 条，避免超长上下文）
    batch_size = 25
    all_results = {s["id"]: [] for s in SECTIONS}
    for start in range(0, len(articles), batch_size):
        batch = articles[start:start + batch_size]
        print(f"\n--- 批次 {start//batch_size + 1}（{len(batch)} 条）---")
        batch_results = analyze_articles(batch)
        for sec in SECTIONS:
            all_results[sec["id"]].extend(batch_results[sec["id"]])

    # 汇总输出
    total = sum(len(v) for v in all_results.values())
    print(f"\n📊 最终: 内政{len(all_results['politics_domestic'])} 外交{len(all_results['politics_foreign'])} 金融{len(all_results['finance'])} 矿产{len(all_results['mining'])} 共{total}条")

    out = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "sections": all_results,
    }
    with open("/tmp/kz_articles_analyzed.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ 分析结果已保存: /tmp/kz_articles_analyzed.json")


if __name__ == "__main__":
    main()
