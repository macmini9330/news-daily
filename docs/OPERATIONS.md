# 运维手册

## 1. 定时任务

```bash
# 查看日报 cron
hermes cron list          # job: d5de4f2b93e3 哈萨克斯坦每日要闻-日报
# 调度：0 9 * * *（每天 09:00 北京时间）
# 执行：python3 /Users/liam/Documents/news-daily/scraper/run_daily.py
# 投递：origin（飞书 DM）
```

⚠️ 若改脚本路径/参数，同步更新 cron 的 prompt。

## 2. 手动运行

```bash
cd ~/Documents/news-daily
python3 scraper/run_daily.py           # 完整流水线 + push
python3 scraper/run_daily.py --no-push # 只生成不推送（调试用）

# 分步调试
python3 scraper/fetch_kz_news.py       # 只抓取 → /tmp/kz_articles_raw.json
python3 scraper/analyze_kz_news.py     # 只分析 → /tmp/kz_articles_analyzed.json
python3 scraper/generate_kz_html.py    # 只生成 HTML
```

⚠️ 完整流水线 5-10 分钟（LLM 逐条翻译全文），**必须后台运行**：
```bash
# 后台跑（推荐）
cd ~/Documents/news-daily && python3 scraper/run_daily.py
# 或 Hermes terminal 用 background=true
```

## 3. 核心规则速查

| 规则 | 值 |
|------|-----|
| 运行时间 | 每天 09:00（北京时间）|
| 抓取窗口 | 前一日 09:00 → 当日 09:00（北京时间）|
| 时区 | 哈通社阿斯塔纳 UTC+5 → 解析后 +3h 转北京 |
| 日期命名 | 文件名=页面标题=首页=发布日 |
| 页面结构 | header → window-bar → stats-bar → toc → sections → footer |
| 索引计数 | `count('class="item"')`，旧结构 `count('class="article"')` |

## 4. 发布检查清单（交付前全链路核对）

- [ ] 文件名 = 今天日期（`kz/2026-08-20.html`）
- [ ] 页面标题 = 「2026年8月20日日报」
- [ ] window-bar 时间范围正确（前一日 9:00 → 当日 9:00 北京时间）
- [ ] 首页最新一期 = 今天日期，链接指向今天的文件
- [ ] 索引页条数 = 实际条目数（非「展开全文」计数）
- [ ] 返回首页链接 `../index.html`（不是 `index.html`）
- [ ] 目录短名（内政/外交/金融/矿产）
- [ ] 线上 HTTP 200 + 深色主题（`#0d1117`）
- [ ] git 干净、已推送、无孤儿文件（旧日期残留）

## 5. 踩坑速查（详见技能 news-daily-digest）

### 日期类（用户两次投诉，最重要）
1. **文件名/标题/首页必须同一天**——别「文件名=发布日、标题=新闻日」分离
2. **日期=发布日**（用户原话拍板），别用「新闻主日期」（用户觉得慢一天）
3. 改命名后**清理孤儿文件**（旧日期残留会让索引多一期）

### 时区/窗口类
4. 哈通社时间是**阿斯塔纳 UTC+5**，必须 +3h 转北京时间（验证：抓 lenta 最新时间 vs 系统时间，差 3h 整）
5. 窗口**双向过滤**（起点+终点），只过滤起点会混入 9:00 后新闻
6. 窗口**锚定今日 9:00** 而非 now-24h（cron 延迟不漂移）

### 抓取类
7. 俄语版 lenta 会 IncompleteRead → gzip + `Connection: close` + `r.read(5_000_000)`
8. 俄语月份是属格（Августа=8月），建 RU_MONTHS 映射
9. 停页条件：本页最早时间 < 窗口起点 且 page≥2

### 代码类
10. `for sec in SECTIONS: sid = sec["id"]`（别 `for sid in SECTIONS`，dict 不可 hash）
11. LLM JSON 输出要防御解析（偶发数组/嵌套异常）
12. 跨模块导入先 `sys.path.insert(0, BASE_DIR)`
13. `__pycache__` 别提交（.gitignore + `git rm -r --cached`）

### 部署类
14. git push 走 **SSH over 443**（`ssh.github.com`），HTTPS 直连被墙
15. 改版必须**全站生效**（首页模板 + 存量旧页都要改）
16. 「返回首页」链接子目录要用 `../index.html`
17. 索引计数别用 `count("展开全文")`（JS 按钮文本虚高 +2）

### 验证类
18. 交付前线上抓取验证（HTTP 200 + 新特征存在）
19. 用户对「低级错误」（日期不一致/404/条数虚高）零容忍——全链路核对

## 6. 故障排查

### 日报没生成/没推送
```bash
# 1. 看 cron 输出
ls ~/.hermes/cron/output/d5de4f2b93e3/ | tail
# 2. 看 /tmp 中间产物
ls -la /tmp/kz_articles_raw.json /tmp/kz_articles_analyzed.json
# 3. git 状态
cd ~/Documents/news-daily && git log --oneline -3 && git status
# 4. 线上是否更新
curl -s https://macmini9330.github.io/news-daily/ | grep -o 'kz/2026[^"]*'
```

### 推送失败
```bash
# SSH over 443 通道测试
ssh -T git@github.com   # 应返回 Hi macmini9330!
# 若失败，检查 ~/.ssh/config 是否含：
#   Host github.com / HostName ssh.github.com / Port 443 / User git
```

### 抓取数量异常（太少/太多）
```bash
# 检查窗口边界（/tmp/kz_articles_raw.json）
python3 -c "import json; d=json.load(open('/tmp/kz_articles_raw.json')); print(d['count'])"
# 正常：170-220 条/天；入选四板块：50-60 条
```

## 7. 数据恢复

- **日报文件被覆盖**：`git show <commit>:kz/<file>.html > kz/<file>.html`
- **/tmp 中间产物被清**（重启后）：重跑对应模块即可（fetch → analyze → generate）
- **历史版本**：git log 里每个 commit 对应一版日报
