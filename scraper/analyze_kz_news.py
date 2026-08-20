#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""哈萨克斯坦每日要闻 - LLM 分类分析模块 v2

流程:
1. 读取 /tmp/kz_articles_raw.json（中文+俄语，约170条）
2. LLM 批量处理：翻译俄语标题→中文 + 四板块分类 + 去重
3. 对入选四板块的新闻：抓详情页全文 → LLM 翻译成中文全文 + 摘要 + 要点 + 影响
输出: /tmp/kz_articles_analyzed.json
"""
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime

# ============ DeepSeek API ============
def get_api_key() -> str:
    env_path = os.path.expanduser("~/.hermes/.env")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("DEEPSEEK_API_KEY not found in ~/.hermes/.env")


def llm_chat(messages: list, max_tokens: int = 4000, temperature: float = 0.2) -> str:
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
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode())
        return data["choices"][0]["message"]["content"]


# ============ 板块定义（唯一来源：sections.py）============
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sections import SECTIONS, OTHER_DESC, CLASSIFY_RULES


def parse_json_response(result: str) -> dict:
    """解析 LLM JSON 输出（容错处理）"""
    result = result.strip()
    if result.startswith("```"):
        result = re.sub(r'^```(?:json)?\s*', '', result)
        result = re.sub(r'\s*```$', '', result)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', result, flags=re.S)
        if m:
            return json.loads(m.group(0))
        raise


def classify_and_translate(articles: list) -> list:
    """第一步：LLM 批量翻译俄语标题 + 分类 + 去重

    输入: 文章列表（zh 已有中文标题，ru 是俄语标题）
    输出: 四板块候选文章列表 [{...原始字段, title_zh, section}]
    """
    # 构造精简列表（标题+时间+url hash，不含正文）
    slim = []
    for i, a in enumerate(articles):
        slim.append({
            "id": i,
            "lang": a["lang"],
            "title": a["title"][:120],
            "time": a["time"],
        })

    sections_desc = "\n".join([f"- {s['id']}: {s['name']}（{s['desc']}）" for s in SECTIONS])
    classify_rules_str = "\n".join(f"- {r}" for r in CLASSIFY_RULES)

    prompt = f"""你是哈萨克斯坦政策研究分析师。以下是今日哈萨克斯坦新闻标题列表（部分俄语，部分中文）。

## 任务
1. 俄语标题翻译成中文（中文标题保持原样）
2. 判断每条新闻属于哪个板块
3. 去重：如果两条新闻（不同语言）是同一事件，只保留中文版那条

## 板块分类
{sections_desc}
- other: {OTHER_DESC}

## 分类优先级规则（多板块冲突时按序裁决）
{classify_rules_str}

## 输出格式（严格 JSON）
{{
  "articles": [
    {{"id": 0, "title_zh": "中文标题", "section": "politics_domestic"}},
    {{"id": 1, "title_zh": "中文标题", "section": "other"}}
  ]
}}
只输出四板块相关的新闻到结果里（section 为 other 的不输出）。

## 新闻列表
{json.dumps(slim, ensure_ascii=False, indent=1)}
"""
    print("🤖 第一步：LLM 批量翻译+分类...")
    result = llm_chat([
        {"role": "system", "content": "你输出严格 JSON，不要输出其他内容。"},
        {"role": "user", "content": prompt},
    ], max_tokens=10000, temperature=0.2)

    data = parse_json_response(result)
    classified = []
    by_id = {i: a for i, a in enumerate(articles)}
    for item in data.get("articles", []):
        idx = item.get("id")
        orig = by_id.get(idx)
        if not orig:
            continue
        section = item.get("section", "other")
        if section == "other":
            continue
        new_item = dict(orig)
        new_item["title_zh"] = item.get("title_zh", orig.get("title", ""))
        new_item["section"] = section
        classified.append(new_item)

    print(f"✅ 翻译+分类完成: {len(classified)} 条进入四板块候选")
    return classified


def fetch_detail(article: dict) -> str:
    """抓取详情页正文（中文/俄语通用）"""
    sys.path.insert(0, os.path.expanduser("~/Documents/news-daily"))
    from scraper.fetch_kz_news import fetch_article_content
    return fetch_article_content(article["url"], article.get("lang", "zh"))


def translate_full_content(article: dict, content: str) -> dict:
    """第二步：LLM 翻译全文 + 生成摘要/要点/影响

    输入: 文章 + 俄语/中文全文
    输出: {title_zh, summary, points, impact, full_content_zh}
    """
    lang_note = "俄语" if article.get("lang") == "ru" else "中文"

    prompt = f"""你是哈萨克斯坦政策研究分析师。以下是哈通社的一篇{lang_note}新闻全文，请：

1. 翻译全文为中文（保留数字、专有名词、机构名称）
2. 写内容摘要（100-150字，保留关键数字和事实）
3. 提炼要点（3-5条，每条15-30字）
4. 写影响分析（50-80字：对哈国政治/经济/外交/矿产格局的影响）

## 新闻
标题: {article['title']}
正文:
{content[:2500]}

## 输出格式（严格 JSON）
{{
  "full_content_zh": "完整中文翻译（保留所有段落和数字）",
  "summary": "内容摘要100-150字",
  "points": ["要点1", "要点2", "要点3"],
  "impact": "影响分析50-80字"
}}
"""
    result = llm_chat([
        {"role": "system", "content": "你输出严格 JSON，不要输出其他内容。"},
        {"role": "user", "content": prompt},
    ], max_tokens=4000, temperature=0.2)

    data = parse_json_response(result)
    return {
        "title": article.get("title_zh", article.get("title", "")),
        "url": article["url"],
        "time": article.get("time", ""),
        "source": article.get("source", ""),
        "lang": article.get("lang", "zh"),
        "summary": data.get("summary", ""),
        "points": data.get("points", []),
        "impact": data.get("impact", ""),
        "full_content": data.get("full_content_zh", ""),
    }


def main():
    with open("/tmp/kz_articles_raw.json", encoding="utf-8") as f:
        raw = json.load(f)
    articles = raw["articles"]
    print(f"📄 待处理文章: {len(articles)} 条")

    # 第一步：翻译+分类（一次调用处理全部，约170条标题）
    classified = classify_and_translate(articles)
    if not classified:
        print("⚠️ 无四板块候选新闻")
        return

    # 统计各板块
    from collections import Counter
    counts = Counter(a["section"] for a in classified)
    print(f"  候选分布: {dict(counts)}")

    # 第二步：对每条候选抓详情 + 翻译全文 + 摘要
    result = {s["id"]: [] for s in SECTIONS}
    for i, art in enumerate(classified):
        print(f"\n📰 [{i+1}/{len(classified)}] {art['title_zh'][:40]}...")
        content = fetch_detail(art)
        if not content:
            print(f"  ⚠️ 详情为空，跳过")
            continue
        print(f"  正文 {len(content)} 字符, 翻译中...")
        try:
            item = translate_full_content(art, content)
            result[art["section"]].append(item)
        except Exception as e:
            print(f"  ❌ 翻译失败: {e}")
        time.sleep(0.3)

    total = sum(len(v) for v in result.values())
    print(f"\n📊 最终: 内政{len(result['politics_domestic'])} 外交{len(result['politics_foreign'])} 金融{len(result['finance'])} 矿产{len(result['mining'])} 共{total}条")

    out = {
        "generated_at": datetime.now().isoformat(),
        "sections": result,
    }
    with open("/tmp/kz_articles_analyzed.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ 分析结果已保存: /tmp/kz_articles_analyzed.json")


if __name__ == "__main__":
    main()
