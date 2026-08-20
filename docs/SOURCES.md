# 信息源清单

> 2026-08-18 摸底实测，2026-08-20 更新。
> 所有 URL 在部署前均验证可访问（国内网络）。

## 1. 核心源：哈通社（Kazinform，哈萨克斯坦官方通讯社）

### 中文版（cn.inform.kz）——精选翻译，约 22-33 条/天

| 板块 | URL | 用途 |
|------|-----|------|
| 全量列表 | https://cn.inform.kz/lenta | 主抓取源 |
| 总统 | https://cn.inform.kz/category/section_s22796 | 内政·高层动态 |
| 国际 | https://cn.inform.kz/category/section_s22880 | 外交 |
| 政府 | https://cn.inform.kz/category/section_s22798 | 内政·政策 |
| 经济 | https://cn.inform.kz/category/section_s22810 | 金融政策一部分 |
| 议会 | https://cn.inform.kz/category/section_s22801 | 内政·立法 |
| 事件 | https://cn.inform.kz/category/section_s25828 | 补充 |

### 俄语版（www.inform.kz/ru）——全量，约 168 条/天

| 用途 | URL | 说明 |
|------|-----|------|
| 全量列表 | https://www.inform.kz/ru/lenta | 分页：`?page=2`…每页 24 条，约 7 页 |
| 详情页 | https://www.inform.kz/ru/{slug}/ | 正文在 `article__content` div 内 `<p>` 段落 |

**⚠️ 时区**：哈通社显示阿斯塔纳时间（UTC+5），解析后 +3h 转北京时间。

## 2. 补充源（用户拍板方案，2026-08-18）

### 金融政策深度（用户选推荐 A：哈通社为主 + 央行补细节）
| 源 | URL | 用途 |
|----|-----|------|
| 哈央行官网 | https://nationalbank.kz | 基准利率/汇率权威（⚠️ 子页 URL 404，用主站）|

### 矿产覆盖面（用户选「够用组合」）
| 源 | URL | 用途 |
|----|-----|------|
| 商务部驻哈使馆 | https://kz.mofcom.gov.cn | 中文经贸政策 |
| 全球矿产资源网 | https://worldmr.net | 铀矿业税/稀有金属出口管制 |

### 国际视角补充
| 源 | URL | 用途 |
|----|-----|------|
| 观察者网 | https://www.guancha.cn | 国际视角 |

## 3. 详情页格式

https://cn.inform.kz/news/{slug}/ = 标题 + 正文（含数据细节）+ 标签，web_extract 可完整提取。

## 4. 抓取策略

- 主源抓**全量列表页**（lenta），再 LLM 按四板块分类——比逐板块抓更全面
- 中文版 + 俄语版都抓（俄语补全量、中文提供现成翻译标题）
- 时间窗口：前一日 9:00 → 当日 9:00（北京时间），双向过滤
- 补充源目前**未接入自动抓取**（信息源清单已确认，抓取模块只实现哈通社）——如矿产板块需稳定产出可后续加
