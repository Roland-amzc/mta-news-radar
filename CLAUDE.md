# Claude Code Notes

Before changing this project, read:

- `skills/ai-news-radar/SKILL.md`
- `docs/SOURCE_COVERAGE.md`
- `README.md`

Do not commit private OPML files, API keys, cookies, browser exports, or `.env`
values. Keep the public repo usable without secrets.

The product direction is a two-layer AI news tool:

- Default layer: curated AI-focused view for ordinary AI enthusiasts.
- Advanced layer: custom OPML/source configuration and source health details for maintainers.

When adding sources, prefer official RSS/Atom feeds or OPML first. Add custom
fetchers only for stable, public, high-signal sources.

---

# 多主题雷达重构(MTA News Radar)

把单一 AI 主题雷达泛化为「多主题个人雷达」。设计文档:`spec.md` / `plan.md` /
`task.md` / `checklist.md`;主题注册表:`topics.yaml`。

## 模块状态
- 设计文档(spec/plan/task/checklist):已完成(2026-06-30)
- `topics.yaml` 注册表(7 主题 / 65 源,50 可运行):已完成
- `radar/` 引擎(T0–T18):进行中
- 前端主题 tab / GitHub Actions 调度 / Pages:未开始(后续独立 spec)

## ADR

### ADR-001: 新建 `radar/` 包,不改旧单体
日期: 2026-06-30
决策: 多主题能力建在全新 `radar/` 包,旧 `scripts/update_news.py`(5672 行)一行不动。
原因: 单体回归风险高;依赖反转要求干净边界;已选「干净切断」旧输出。
代价: 旧 `index.html`/单桶输出在前端重构前失效;部分 AI 专属增值逻辑(跨主题精选、标题中译)不迁移。

### ADR-002: `topics.yaml` 驱动 + 三层可插拔接口
日期: 2026-06-30
决策: 一个注册表驱动引擎,抓取(Fetcher)/打分(Scorer)/输出(Writer)抽象成接口,按主题循环产出 `data/<topic>/*.json`。每主题独立 `mode/window/scorer`。
原因: 新增主题改 yaml、新增源类型/策略加一个实现文件,均不碰编排(可扩展 + 依赖反转)。
代价: 比「包一层」工作量大;需重写最小化的 feed 解析(用 feedparser)。

### ADR-003: LLM 精判本期留桩
日期: 2026-06-30
决策: scorer 策略 `keyword/none` 落地,`llm` 留接口 + 桩(委托 keyword),不发任何网络 LLM 调用。
原因: 控范围与外部依赖;token 预算/密钥/成本闸留下一个 spec 专门做。
代价: health/quant 等需语义判定的主题第一版相关性偏弱,靠 keyword 兜底。

### ADR-004: 未实现源类型「解析但跳过」(配置契约)
日期: 2026-06-30
决策: 本期可运行类型 `rss/arxiv/arxiv_author/podcast/youtube`;`scrape/x_account`、`enabled:false`、`author_id:TODO` 的源解析但跳过(记 `status=skipped`),只有拼错的类型才报 `ConfigError`。
原因: 让当前 `topics.yaml`(含 13 个 todo 源)合法可加载,避免 load 直接失败。
代价: 非 feed 源(Anthropic/Meta/具身厂商等)暂无数据,需后续补适配器。
