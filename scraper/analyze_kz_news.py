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


def dedup_cross_lang(classified: list, votes: int = 3) -> list:
    """跨语言去重复核：同一事件保留中文版（哈通社官方中文），删除俄语版条目

    背景：哈通社中文版是俄语版的精选翻译，同一事件会同时出现中文版+俄语版两条。
    fetch 层按 URL 去重识别不了（中俄 URL 不同），分类 prompt 的粗粒度去重不可靠。

    零误删三重保障（2026-09-21 加固，用户要求「不能有误删」）：
    1. LLM 逐条中文版匹配（以 24 条中文版为锚，比遍历 91 条俄语版聚焦）
    2. 多轮投票取交集（默认 3 轮，仅各轮都判为同一事件才删——消除 LLM 随机误判）
    3. 关键数字硬校验（两条标题的关键量词冲突则否决，如「47万台设备」vs「100万个钱包」）
    """
    zh = [a for a in classified if 'cn.inform' in a.get('url', '')]
    ru = [a for a in classified if '/ru/' in a.get('url', '')]

    if not zh or not ru:
        print(f"⏭️ 跨语言去重跳过（中文版 {len(zh)} 条 / 俄语版 {len(ru)} 条，无配对）")
        return classified

    def _t(a):
        return a.get('title_zh') or a.get('title', '')

    # 标题已在分类阶段翻译为中文，两组可直接比对
    zh_slim = [{"id": f"zh_{i}", "title": _t(a)[:120]} for i, a in enumerate(zh)]
    ru_slim = [{"id": f"ru_{i}", "title": _t(a)[:120]} for i, a in enumerate(ru)]

    prompt = f"""你是哈萨克斯坦政策研究分析师。哈通社同一事件会同时发布中文版和俄语版两条新闻，以下是同一天两组标题（均已翻译为中文）。

## 任务
请**逐条**检查 A 组（中文版）的每一条，在 B 组（俄语版）中找出报道**同一事件**的那一条。

## 判断标准
- 「同一事件」= 事件主体 + 事件内容相同。**中俄两版标题措辞往往不同，不要被字面差异迷惑**。
  正例：
  ✅「托卡耶夫会见韩国总理：推动哈韩贸易额翻番」与「托卡耶夫提议将哈萨克斯坦与韩国贸易额翻番」→ 同一事件
  ✅「国家银行：将建立国家加密分析中心」与「哈萨克斯坦将创建国家加密货币分析中心」→ 同一事件
  ✅「约160辆货车因俄方口岸维修滞留哈萨克斯坦"斋桑"口岸」与「约160辆卡车聚集在哈萨克斯坦和俄罗斯边境」→ 同一事件
  ✅「托卡耶夫会见韩国KIND公司总裁金福焕」与「托卡耶夫与KIND负责人会谈后签署三项协议」→ 同一事件
  ✅「托卡耶夫会见韩华集团副会长金东元」与「托卡耶夫建议韩华集团扩大与哈萨克斯坦的合作」→ 同一事件
- 不要判为同一事件（主题相近但具体事实/对象/数字不同）：
  ❌「托卡耶夫会见乐天集团会长辛东彬」与「托卡耶夫会见韩华集团副会长金东元」→ 不同事件（会见不同的人）
  ❌「哈萨克斯坦全国近47万台挖矿设备已登记」与「哈萨克斯坦人在全球拥有约100万个加密钱包」→ 不同事件（都属加密货币统计，但前者是挖矿设备登记数、后者是钱包持有量，是**两个不同的事实**）
  ❌「9月15日终盘汇率」与「9月15日兑换点汇率」→ 不同事件（汇率口径不同）
- ⚠️ 只有「**核心事实完全对应**」才算同一事件；主题相近但事实/数字/对象不同的一律判为不同事件。
- ⚠️ 宁可判 null（无对应），也不要勉强匹配。
- 每条中文版匹配**最多一条**俄语版；确实找不到对应的，ru_id 填 null。

## 输出格式（严格 JSON）
{{"matches": [
  {{"zh_id": "zh_0", "ru_id": "ru_5", "reason": "同一事件简述"}},
  {{"zh_id": "zh_1", "ru_id": null, "reason": "俄语版无对应"}}
]}}
必须对 A 组全部 {len(zh_slim)} 条逐一输出，不得跳过、不得合并。

## A 组（中文版）
{json.dumps(zh_slim, ensure_ascii=False, indent=1)}

## B 组（俄语版，标题已翻译为中文）
{json.dumps(ru_slim, ensure_ascii=False, indent=1)}
"""

    def _ru_idx(rid):
        """解析 ru_id（容错：'ru_3' / 3 / '3' / 'null'）"""
        if isinstance(rid, int):
            return rid
        if isinstance(rid, str):
            s = rid.strip()
            if s.startswith("ru_"):
                s = s[3:]
            try:
                return int(s)
            except ValueError:
                return None
        return None

    def _zh_idx(zid):
        """解析 zh_id（容错：'zh_3' / 3 / '3'）"""
        if isinstance(zid, int):
            return zid
        if isinstance(zid, str):
            s = zid.strip()
            if s.startswith("zh_"):
                s = s[3:]
            try:
                return int(s)
            except ValueError:
                return None
        return None

    print(f"🔍 跨语言去重复核: 中文版 {len(zh)} / 俄语版 {len(ru)}，{votes} 轮投票取交集...")

    # 保障 2：多轮投票，取各轮交集的 (zh_idx, ru_idx) 匹配对
    vote_sets = []
    for v in range(votes):
        try:
            result = llm_chat([
                {"role": "system", "content": "你输出严格 JSON，不要输出其他内容。"},
                {"role": "user", "content": prompt},
            ], max_tokens=4000, temperature=0.1)
            data = parse_json_response(result)
            pairs = set()
            for m in (data.get("matches") or []):
                if not isinstance(m, dict):
                    continue
                zi = _zh_idx(m.get("zh_id"))
                ri = _ru_idx(m.get("ru_id"))
                if zi is not None and ri is not None and 0 <= zi < len(zh) and 0 <= ri < len(ru):
                    pairs.add((zi, ri))
            vote_sets.append(pairs)
            print(f"   第 {v+1} 轮: {len(pairs)} 对匹配")
        except Exception as e:
            print(f"   ⚠️ 第 {v+1} 轮失败: {e}")

    if not vote_sets:
        print("⚠️ 全部去重轮次失败，跳过不去重")
        return classified

    common = set.intersection(*vote_sets)
    print(f"   {len(vote_sets)} 轮交集: {len(common)} 对（各轮均判为同一事件）")

    if not common:
        print("✅ 跨语言去重: 无各轮一致的重复（不删任何条目）")
        return classified

    # 保障 3：关键数字硬校验——两条都有带单位量词且无交集 → 否决
    _num_re = re.compile(r'(\d+(?:\.\d+)?)\s*(万|亿|千|公里|台|辆|个|笔|项|吨|美元|坚戈|卢布|人民币|%)')

    def _knum(s):
        return set(f"{n}{u}" for n, u in _num_re.findall(s))

    drop_urls = set()
    vetoed = []
    for zi, ri in sorted(common):
        zt, rt = _t(zh[zi]), _t(ru[ri])
        nz, nr = _knum(zt), _knum(rt)
        if nz and nr and not (nz & nr):
            vetoed.append((zt, rt, sorted(nz), sorted(nr)))
            continue
        u = ru[ri].get('url', '')
        if u:
            drop_urls.add(u)

    for zt, rt, nz, nr in vetoed:
        print(f"   ⛔ 数字冲突否决: 「{zt[:30]}」{nz} vs 「{rt[:30]}」{nr}")

    if not drop_urls:
        print("✅ 跨语言去重: 未发现可安全删除的重复")
        return classified

    out = [a for a in classified if a.get('url', '') not in drop_urls]
    print(f"✅ 跨语言去重: 删除 {len(drop_urls)} 条俄语版重复（同事件保留中文版）")
    for u in sorted(drop_urls):
        print(f"   - 删: {u}")

    return out


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

    # 第一步半：跨语言去重复核（同一事件保留中文版，删除俄语版）
    classified = dedup_cross_lang(classified)
    if not classified:
        print("⚠️ 去重后无候选新闻")
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
