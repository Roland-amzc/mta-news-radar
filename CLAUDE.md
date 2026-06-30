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
- 引擎设计文档(spec/plan/task/checklist):已完成(2026-06-30)
- `topics.yaml` 注册表(7 主题 / 65 源,50 可运行):已完成
- `radar/` 引擎(T0–T18,31 测 + 真实跑通 7 主题):已完成
- 前端主题 tab(`index.html` + `assets/radar.{css,js}`,Preview 实测 8 AC):已完成
- 内容加工层(`radar/digest/`,产中文 title_zh/summary_zh;多 provider:OpenAI 兼容 DeepSeek/Qwen/Kimi/GLM/Gemini 或 Anthropic):已完成(注入桩验证;真实质量待配置某家 key)
- 前端消费 zh 字段(卡片显示中文标题+原文副标题+中文摘要,DeepSeek 实测 Preview 验证):已完成
- GitHub Actions 每天跑 + Pages 部署(`.github/workflows/radar.yml`):代码完成,本地验通过;GitHub 侧实跑待用户 push + 配 Secret/Pages
- 分板块差异化呈现 / 非 feed 源适配器:未开始(后续独立 spec)

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

### ADR-005: 前端重建干净多主题页,旧页归档
日期: 2026-06-30
决策: 新建 `index.html` + `assets/radar.{css,js}`(原生、无框架、无构建)读新数据;旧 AI 单主题页归档为 `index.legacy.html`。生成的 `data/index.json` 与 `data/<topic>/` 不入库(gitignore)。
原因: 旧页重度耦合旧 AI 数据模型(栏目/Top3/WaytoAGI/AI相关度),改造成本高于重建;与引擎「干净切断」一致。
代价: 旧页高级筛选/搜索等未迁移;新页搜索/排序/深色留待后续。

### ADR-006: 内容加工层落地 LLM(核心总结+翻译合一)
日期: 2026-06-30
决策: 之前留桩的 LLM 落地为「内容加工」——对每主题 top-N 条目用 Claude Haiku 4.5 产出 `title_zh`+`summary_zh`(中文标题+2-3句摘要,英文则翻译),引擎侧生成写进 JSON。可插拔 `Digester` 协议(Claude/Noop/Fake)、按 id 持久化缓存、单次预算闸、无 key 优雅降级。
原因: 原文长文+大量英文难消化;Haiku 便宜($1/$5)、批量足够;缓存+预算控成本(稳态≈只新条目)。
代价: 真实翻译质量需 ANTHROPIC_API_KEY 才能验;Batch API 50% 折扣暂未用(同步并发换即时性);前端消费 zh 字段是另一个模块。
备注: 注意「核心总结/翻译」与「关系打分」是两件事——本层只加工,打分仍走 keyword。这是用户在前端长文难读后提出的方向。

### ADR-007: 加工层支持多 provider(OpenAI 兼容),不绑 Anthropic API
日期: 2026-06-30
决策: 因用户只有 Claude Coding Plan 订阅(≠ Anthropic 按量 API),新增通用 `OpenAICompatibleDigester`,由 env 驱动(`DIGEST_API_KEY`/`DIGEST_BASE_URL`/`DIGEST_MODEL`)。一个适配器覆盖 DeepSeek / 通义 Qwen / Kimi / 智谱 GLM / Gemini(OpenAI 端点)/ OpenAI(`PROVIDER_PRESETS` 给 base_url+model)。工厂优先级:OpenAI 兼容 > Anthropic > Noop。
原因: 订阅 OAuth 不能调 Messages API,且 GitHub Actions 里也只能放第三方 secret;中文输出+省钱首选 DeepSeek/Qwen 等。`Digester` 协议(ADR-002 依赖反转)正是为此留的活口——只多一个实现。
代价: 各家结构化输出能力不一,统一改成 prompt 指示 JSON + 容错解析(Claude 也随之去掉 output_config),可靠性略低于原生 schema 约束但跨家通用。
