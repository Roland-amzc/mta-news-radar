# MTA News Radar 引擎深度重构 Spec

> 范围:**仅引擎核心**(前端 / GitHub Actions / Pages 留作后续独立 spec)
> 架构路线:**B 深度重构**——抓取/打分/输出抽象成可插拔接口,由 `topics.yaml` 完全驱动。

## 背景

上游 `LearnPrompt/ai-news-radar` 是单一 AI 主题雷达。引擎 `scripts/update_news.py`(5672 行单体)有三个写死假设:

1. **单一全局时间窗**(`args.window_hours`,默认 24h)——对慢主题是错的;
2. **AI 相关性焊进打分公式**(`calculate_item_importance`)与硬门禁(`is_ai_relevant`)——对非 AI 主题是死重;
3. **单一输出桶**(`data/*.json`)——无法分主题。

已就绪:7 主题框架(`ai-news-radar-PLAN.md`)+ 注册表草案 `topics.yaml`(65 源,47 已 HTTP 验证)。

本次将引擎从「单一 AI 主题」泛化为「多主题个人雷达」,由 `topics.yaml` 注册表驱动,按主题循环产出 `data/<topic>/*.json`。

## 目标

- **G1**:引擎由 `topics.yaml` 注册表驱动,支持 N 个主题,每主题独立 `mode / window / scorer`。
- **G2**:抓取、打分、输出三层抽象成可插拔接口——新增主题/源类型/打分策略**不改核心**。
- **G3**:每主题独立产出 `data/<topic>/*.json`;移除单一全局窗与 AI 焊死打分。
- **G4**:支持两种 `mode`——`topic`(打分+门禁)与 `entity`(全收不打分,按时间排序)。

## 功能需求

- **F1 注册表驱动**:引擎读取 `topics.yaml`,解析出主题列表及每主题的 `mode / window / scorer / keywords / sub_labels` 和源清单。**未知/拼错的源类型或非法枚举 → 明确报错**;但**已知尚未实现的类型(`scrape / x_account`)、`enabled: false`、`author_id` 为 `TODO` 的源 → 解析但跳过**(记 `status=skipped`,不报错、不抓取),不影响该主题加载。
- **F2 按主题循环**:对每个主题独立跑「抓取→粗筛→窗过滤→去重→打分→排序→输出」管线;主题之间互不影响,一个主题整体失败不拖垮其余主题。
- **F3 多种 feed 源类型**:支持 `rss / arxiv(按 category) / arxiv_author(按作者 ID) / podcast / youtube(频道 RSS)` 五类抓取,各自解析为**统一条目记录**(标题、链接、**摘要**、发布时间、来源名、来源层级 tier、sub_label)。摘要(feed 的 summary/description)进入条目,供打分使用。
- **F4 每主题独立窗**:用该主题自己的 `window`(72h/1w/2w…)过滤条目,彻底取代全局单一窗。`published` 非空者按窗过滤;`published` 为空者保留、排序殿后。
- **F5 可插拔打分策略**:按主题 `scorer` 选择——`keyword`(用主题 `keywords` 对 标题+摘要 命中度 + tier 加权打分)、`none`(不打分)、`llm`(**本次留接口+桩**,行为暂等同 keyword)。`frontier` 的 `keyword_prefilter+llm` 本次=keyword 打分,LLM 段走桩。**`keywords`(主题相关性打分)与 `prefilter_keywords`(高频源粗筛)是两个独立字段。**
- **F6 两种 mode 行为**:`topic` 模式按分数排序并应用门禁筛选;`entity` 模式全收、不打分、仅按发布时间倒序。
- **F7 实体反混淆**:`arxiv_author` 源按作者标识符锚定抓取,避免同名混淆(姚顺宇 vs 姚顺雨)。`author_id` 未确认时该源跳过(本期 姚顺宇 禁用)。
- **F8 高频源粗筛**:对带 `prefilter` 标记的源(如 arXiv),抓取后先用 `prefilter_keywords` 做粗筛再进打分,降低条目量。
- **F9 主题内去重**:同一主题内按链接/标题归一去重,多来源同一故事保留更权威来源(tier 高者)。
- **F10 分主题产出**:每主题写独立 JSON 到 `data/<topic>/`,含条目列表 + 元信息(生成时间、window、**各源健康状态 `ok/failed/skipped`、各阶段计数 stats**)。
- **F11 故障隔离**:单源抓取失败(超时/403/解析错)被捕获并记 `status=failed`,不中断该主题其余源,也不中断其他主题。主题级罕见硬错也写出 `items=[]` + `topic_error` 的合法产出。

## 非功能需求

- **N1 干净切断**:引擎**只**产出 `data/<topic>/*.json`(含 `data/frontier/`),不再写旧单桶路径;旧 `index.html` 在前端 spec 落地前失效——已接受的代价。
- **N2 可扩展(核心诉求)**:新增主题 = 只改 `topics.yaml`,**0 行核心代码**;新增源类型 = 新增一个抓取适配器实现统一接口,不改编排;新增打分策略 = 新增一个策略实现。
- **N3 依赖反转**:编排层与接口契约**不依赖**具体源实现/具体打分实现——换 feed 解析库或将来换 LLM 都不动编排逻辑。
- **N4 成本与网络**:每源设抓取超时上限;粗筛发生在打分**之前**以控下游处理量;**本次不引入任何付费 API 调用**(LLM 走桩,零成本)。
- **N5 安全**:不硬编码密钥;feed 地址与将来密钥走配置/环境变量;产出沿用引擎现有脱敏思路;遵守仓库 `CLAUDE.md`——不提交私有 OPML/key/cookie。
- **N6 可测试**:抓取解析、窗过滤、打分策略、去重各自可单测;网络 IO 与纯解析逻辑分离,解析层用固定样本即可测。
- **N7 代码规范**:文件/函数 `snake_case`、类 `PascalCase`、常量 `UPPER_CASE`、函数参数与返回值类型注解齐全。
- **N8 健壮性**:空主题/源全失败/配置缺源时,产出**结构合法的空 JSON**,不崩溃。

## 不做的事

延后到后续独立 spec:
1. 前端/可视化:`index.html` 主题 tab、多主题 UI、Pages 部署。
2. GitHub Actions 调度:cron 定时、多主题调度、secrets 配置。本次引擎**能本地命令行跑通**即可。
3. LLM 精判实现:provider 选型、密钥、token 预算、成本闸、批量判定。留接口+桩。
4. 非 feed 源适配器:`scrape / x_account` 类(topics.yaml 里的 todo:Anthropic、Meta AI、DeepSeek、Figure/1X/π/宇树/智元、Isomorphic/Recursion/Insilico、The Browser)。本期引擎**解析但跳过**这些源(记 `status=skipped`),接口为它们**预留位置**,具体适配器后续按需补。
5. 动态嘉宾标签(guest_tagging):从播客标题/描述识别嘉宾。本次只**透传静态 sub_label**。
6. 现引擎的 AI 专属增值逻辑:跨主题统一精选池(今日 Top 3 从 20 条故事池筛)、标题中译缓存(title-zh-cache)。本次不迁移。

永不做(PLAN 已定):
7. 商品基本面(棕榈油/白糖/黄金/厄尔尼诺)——撞「无公开 feed / 结构化数字 / 低频报告」三堵墙。

暂缓(需专门适配器,后续):
8. 药明系公告、国内量化公众号、国内具身厂商(公众号/公告类源)。

兼容:
9. 不为旧 `index.html` / 旧单桶输出保活(已选「干净切断」)。

## 验收标准

- **AC1**(F1):当前 `topics.yaml`(含 `scrape/x_account/enabled:false/author_id:TODO` 源)→ 全部 7 主题正常解析(那些源记 `skipped` 而非报错);把某源 `type` 拼成未知值或漏必填字段 → 报明确错误并非 0 退出。
- **AC2**(F2/F11):跑全量 → 每主题在 `data/<topic>/` 产出;故意令某主题一个源不可达 → 该主题其余源仍出结果、其他主题不受影响,该源 `status=failed`;`scrape/x_account/禁用` 源记 `status=skipped`。
- **AC3**(F3):`rss/arxiv/arxiv_author/podcast/youtube` 各至少一个真实源 → 条目记录含 标题/链接/来源名/tier;`sub_label`/摘要/发布时间**可空**(配了 sub_label 则透传)。
- **AC4**(F4):`frontier`(72h)与 `new_books`(2w)产出中**发布时间非空**的条目落在各自窗内;`published` 为空的条目可保留但排序殿后;改某主题 `window` 重跑 → 过滤边界随之变化。
- **AC5**(F5):`scorer=keyword` 主题条目带分、按分排序;`scorer=none` 主题条目无分、按时间倒序;`scorer=llm` 主题走桩、**不发起任何网络 LLM 调用**,行为与 keyword 粗筛一致。
- **AC6**(F6):`entity_radar` 全收(不因低分丢条)、按时间倒序;`topic` 模式应用门禁后,低于门槛条目不进主榜。
- **AC7**(F7):`arxiv_author`(姚顺宇)只返回锚定作者 ID 的论文,人工抽查无同名(姚顺雨)条目混入。
- **AC8**(F8):带 `prefilter` 的 arXiv 源,产出元信息 `stats.after_prefilter < stats.fetched_total`(粗筛生效,可观测)。
- **AC9**(F9):构造同一故事多来源样本 → 去重后只留一条,且为 tier 更高来源。
- **AC10**(F10):每主题 `data/<topic>/` 下 JSON 含条目列表 + 元信息(生成时间/window/源健康 `ok|failed|skipped`/各阶段 stats),可被 JSON 解析。
- **AC11**(N8):空主题/源全失败 → 产出结构合法的空 JSON,进程退出 0、不崩溃。
- **AC12**(N1):运行后旧路径 `data/latest-24h.json` 不再被本引擎生成/更新。
- **AC13**(N2 可扩展):在 `topics.yaml` **仅加配置**新增一个主题(不改核心代码)→ 重跑后 `data/<新topic>/` 出现且含条目。
