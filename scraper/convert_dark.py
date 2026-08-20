#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧版日报 HTML 深色主题转换脚本

把 v1 结构（.section/.article/.title/.meta/.summary/.points/.impact）
的旧版浅色日报页转换成 OpenClaw 深色主题。

用法: python3 convert_dark.py <旧HTML文件> [输出文件]
"""
import re
import sys

DARK_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  background: #0d1117; color: #c9d1d9; line-height: 1.75; min-height: 100vh;
}
.container, body > div { max-width: 880px; margin: 0 auto; padding: 24px 20px 60px; }
.header { text-align: center; padding: 30px 0 18px; border-bottom: 1px solid #21262d; margin-bottom: 20px; }
.header h1 { font-size: 1.8em; font-weight: 700; color: #f0f6fc; margin-bottom: 10px; }
.header .meta, .header .date { font-size: .95em; color: #8b949e; }
.header .date { font-size: 1.1em; color: #e6edf3; margin-bottom: 6px; }
.header .stats { margin-top: 12px; font-size: .85rem; color: #8b949e; }
.header .stats .stat { background: #161b22; border: 1px solid #21262d; border-radius: 20px; padding: 4px 12px; margin: 0 4px; display: inline-block; }

/* 板块 */
.section { margin-top: 30px; }
.section h2 {
  display: flex; align-items: center; gap: 10px;
  font-size: 1.15rem; font-weight: 700; color: #e6edf3;
  padding: 10px 16px; margin-bottom: 16px;
  background: #161b22; border: 1px solid #21262d; border-left: 4px solid #c0392b;
  border-radius: 8px;
}

/* 单条 */
.article { padding: 14px 4px 10px; margin-bottom: 6px; border-bottom: 1px solid #161b22; border-left: 3px solid transparent; padding-left: 14px; }
.article .title { display: flex; align-items: flex-start; gap: 10px; font-size: 1.05rem; font-weight: 650; color: #e6edf3; margin-bottom: 6px; }
.article .title a { color: #e6edf3; text-decoration: none; }
.article .title a:hover { color: #58a6ff; }
.article .meta { font-size: .8rem; color: #8b949e; margin: 0 0 8px 0; }
.article .meta a { color: #58a6ff; text-decoration: none; }
.article .source-link { margin-left: 8px; }

/* 摘要 */
.article .summary {
  margin: 8px 0 8px 0; padding: 8px 14px;
  background: #161b22; border: 1px solid #21262d;
  border-radius: 0 6px 6px 0;
  font-size: .92rem; color: #d4d9e0;
}
.article .summary b { color: #58a6ff; }

/* 展开全文 */
.summary-toggle { margin: 6px 0 2px 0; font-size: .82rem; color: #58a6ff; cursor: pointer; user-select: none; display: inline-block; padding: 2px 0; }
.summary-toggle:hover { text-decoration: underline; }
.summary-toggle .arrow { display: inline-block; transition: transform 0.2s; margin-right: 4px; }
.summary-toggle.open .arrow { transform: rotate(90deg); }
.full-content {
  display: none;
  margin: 8px 0 4px 0;
  font-size: .9rem; line-height: 1.85; color: #c9d1d9;
  background: #0d1117; border: 1px dashed #30363d;
  border-radius: 8px; padding: 12px 16px;
  white-space: pre-wrap;
}
.full-content.show { display: block; }

/* 要点 */
.article ul { margin: 6px 0 6px 0; padding-left: 18px; }
.article ul li { margin-bottom: 6px; font-size: .93rem; }

/* 影响 */
.article .impact {
  margin: 10px 0 4px 0; padding: 8px 14px;
  background: #f0b90b10; border-left: 3px solid #f0b90b;
  border-radius: 0 6px 6px 0;
}
.article .impact b { font-weight: 700; color: #f0b90b; margin-right: 8px; }

.empty { color: #8b949e; font-size: .9rem; padding: 12px 0 12px 0; font-style: italic; }

.footer { text-align: center; color: #8b949e; font-size: .8rem; padding: 40px 0 0; border-top: 1px solid #21262d; margin-top: 40px; }
.footer a { color: #58a6ff; text-decoration: none; }
"""


def convert(filepath: str, outpath: str = None) -> bool:
    with open(filepath, encoding="utf-8") as f:
        html = f.read()

    if "#0d1117" in html:
        print(f"✅ {filepath} 已是深色主题，跳过")
        return False

    # 替换 <style>...</style> 块
    new_html, n = re.subn(r"<style>.*?</style>", f"<style>{DARK_CSS}</style>", html, flags=re.S)
    if n == 0:
        print(f"⚠️ {filepath} 无 <style> 块")
        return False

    out = outpath or filepath
    with open(out, "w", encoding="utf-8") as f:
        f.write(new_html)
    print(f"✅ 已转换: {filepath} → {out}（{len(new_html)/1024:.0f}KB）")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 convert_dark.py <HTML文件> [输出文件]")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
