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
- GitHub Actions 每天跑 + Pages 部署(`.github/workflows/radar.yml`):已完成(2026-07-01)。`feat/radar-engine` 已合并入 `master` 并 push;Secret `DIGEST_API_KEY`(DeepSeek)+ Pages(Source=Actions)已配置;手动 Run workflow 跑绿(2分40秒),线上 `data/frontier/latest.json` 实测含真实 `title_zh` 中文翻译。线上地址:https://roland-amzc.github.io/mta-news-radar/
- 非 feed 源适配器(`radar/fetchers/scrape.py`):试点完成(2026-07-01)。选择器驱动的通用
  `ScrapeFetcher`(一份实现 + topics.yaml 配 CSS 选择器,不写 per-site 代码),已注册进
  `FETCHERS`、移出 `DEFERRED_TYPES`;9 个测试(fixtures + 真实站点结构建模)全绿。试点 2
  源:Anthropic News + 宇树 Unitree,`--only frontier` 真实抓取验证 `status=ok`(fetched=4/9,
  日期解析、相对链接转绝对链接均正确;Unitree 9 条被 72h 窗口过滤属预期,非故障)。其余 9 个
  scrape 源(Meta AI/DeepSeek/1X/π/智元/Isomorphic/Recursion/Insilico/The Browser)显式
  `enabled: false`,补 item_selector/title_selector 后改 true 即可接入,不用碰 `radar/` 代码。
  `x_account`(Figure)仍无实现,留 `DEFERRED_TYPES`。entity_radar 的姚顺宇源保持 skipped——
  唯一可锚定的 arXiv ID(yao_s_2)只覆盖他转 AI 前的物理论文,接入会导致"实体雷达"里混入无关
  数据,故意不接(详见 topics.yaml 该条 note 与 ADR-008)。
- `scorer=llm` 真实相关性判定(`radar/scorers/llm.py`):已完成(2026-07-01,范围仅
  ai_health+quant_factor,详见 ADR-009)。复用 digest 层同一把 DeepSeek key,budget=200/次
  运行(共享,非按主题各自 200)、按 item.id 缓存(`data/relevance-cache.json`,已进
  `.gitignore`/Actions cache/`_site` 排除清单,与 digest-cache 同等对待)。本地无 key 情况
  实跑验证:优雅降级为纯关键词打分(`score_reason` 仍是 `hits: ...` 格式),不崩溃、不产生
  多余缓存文件。真实 LLM 判定质量待下次 GitHub Actions 跑(用真 key)后核实
  `score_reason` 是否变成 LLM 生成的自然语言理由。frontier 的 `keyword_prefilter+llm`
  改直接指向纯关键词 scorer,不再共享这个桩/真实现——原因见 ADR-009。
- 前端美工 v2 + 信息源健康修复:已完成(2026-07-02)。前端(`assets/radar.{css,js}` bump 到
  `?v=3`):内容列 `max-width:900px; margin:0 auto` 居中(消除宽屏右侧大片空白);卡片结构统一
  为 标题/副标题/摘要/footer 元信息行(source·time·score 移到带上边框的 footer,视觉更整齐);
  摘要去掉 2 行 `-webkit-line-clamp` 硬截断——中文 digest 摘要(`summary_zh`)整段完整显示,长英文
  原文摘要(>320 字)默认收起 3 行 + 「展开全文/收起」按钮;`radar.js` 的 `cleanSummary()` 新增正则
  剥离 arXiv 摘要前缀噪声(`arXiv:xxxx Announce Type: xxx Abstract:`)。Preview 桌面/移动实测:居中
  生效(content 900px 居中)、展开按钮 68px↔316px 切换、arXiv 前缀已清、192 测试全绿。
  信息源:根因是 fetcher 用机器人 UA(`mta-news-radar/0.1`)被 Substack/Cloudflare 403(详见
  ADR-010)。`radar/fetchers/{feed,scrape}.py` 改真实浏览器 UA + Accept 头,一举修复
  Latent Space(播)/Endpoints News 等;QuantSeeker→`www.quantseeker.com/feed`、Import
  AI→`jack-clark.net/feed/`(Substack 自有域名不受 `*.substack.com` 边缘 IP 拦截)、Cognitive
  Revolution→`feeds.megaphone.fm/RINTP3108857801`(真音频 feed,354 条);xAI(404 无 RSS)与
  MIT Press(Cloudflare 硬拦,非 UA 可解)显式 `enabled:false` 止血。本地跑 4 主题实测所有原失败源
  回 `status=ok`(Nature 两源本地网络不可达但线上一直 ok,非回归)。
- scrape 源铺开(第二批)+ 信息源掉线告警:已完成(2026-07-02)。探测 8 个 disabled scrape 站,
  只 Physical Intelligence(π)一个干净可接(SSR 出 blog 卡片、标题+日期均能解析,已 enable);
  其余 6 站均有硬障碍且**如实记进 topics.yaml 各源 note**:Meta AI(400 边缘拦)、DeepSeek
  (404 无静态新闻页)、1X(Next.js SPA)、智元(SPA/复杂+无日期)、Recursion(000 反爬)、
  Isomorphic/Insilico(SSR 可抓但卡片**无机器可读日期**,接入会因 `_within_window` 对无日期条目
  返回 True 而把全部历史文章永久灌进 1 周窗口——宁缺毋滥,保持 disabled)。The Browser 付费跳过。
  告警:新增 `scripts/check_source_health.py`——跑完读各主题 source_health,只对 `status=failed`
  (enabled 源真抓失败)告警,`skipped`/`disabled`/`ok`-0-条 均不误报;GitHub Actions 里发
  `::warning::` 注解 + step-summary 表格,**恒 exit 0 不阻断部署**(`--fail-over N` 可选让 CI 变红)。
  已接进 `.github/workflows/radar.yml`(Run engine 之后一步)。5 个新测试覆盖告警口径,全套 197 测全绿。
- 分板块差异化呈现:未开始(后续独立 spec)

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

### ADR-008: 非 feed 源用「选择器驱动的通用 ScrapeFetcher」,不写 per-site 代码;试点 2/12 站
日期: 2026-07-01
决策: 新增 `radar/fetchers/scrape.py`(`ScrapeFetcher`,复用 `parse_published` 做日期归一化),`item_selector`/`title_selector`/`date_selector` 三个 CSS 选择器字段进 `SourceSpec`,由 topics.yaml 配置驱动——新增一个 scrape 源只改配置,不碰 `radar/` 代码(与 ADR-002 的可插拔原则一致)。`scrape` 从 `DEFERRED_TYPES` 移出、注册进 `FETCHERS`;`config.py` 相应加校验(enabled 的 scrape 源必须有 url+item_selector+title_selector,否则 ConfigError,与其余类型的"跑的源必须配对"一致)。范围上不追求一次性覆盖全部 12 个 scrape 站(与用户对齐:先试点见效再铺开),选 Anthropic News + 宇树 Unitree 两个代表性官网试点,`--only frontier` 真实网络验证通过(status=ok,标题/日期/链接均解析正确)。其余 9 个 scrape 源(Meta AI/DeepSeek/1X/π/智元/Isomorphic/Recursion/Insilico/The Browser)显式加 `enabled: false`(此前靠 `scrape` 类型本身被全量 deferred,现在类型已实现,必须显式关,否则会因缺选择器报 ConfigError 炸掉整个 topics.yaml 加载)。
原因: 12 个站点 HTML 结构互不相同,一次性写全量易碎、难维护;选择器驱动比"一站点一 Python 文件"更符合 ADR-002 的分层(变化率高的东西——站点样式——放最外层配置,不进代码层)。选择器优先锚定语义标签(`h4`/`time`/`p.title`)而非 CSS-module 哈希类名(如 Anthropic 的 `FeaturedGrid-module-scss-module__W1FydW__title`),更扛得住前端重构。
代价: 选择器仍是"读 DOM 结构猜的",目标站改版会让该源静默掉线为 `status=failed`(不会崩溯,但需要人工发现+补选择器,无自动告警机制)。X/Twitter(Figure,`x_account`)未处理——反爬更强,通常要付费 API 或登录态 cookie,单独放行程外。姚顺宇的 `arxiv_author` 调研发现唯一可锚定 ID(`yao_s_2`)只覆盖他转 AI 前的物理论文,不含 Anthropic/DeepMind 时期工作,故意保持 skipped 不接入(见 topics.yaml 该条 note),非 arXiv 监控渠道(个人站/官方公告)属 scrape 范畴,未来若要盯他可另起一个 scrape 源。

### ADR-009: `scorer=llm` 落地真实相关性判定,范围只 ai_health/quant_factor,不含 frontier
日期: 2026-07-01
决策: `radar/scorers/llm.py` 的 `LlmScorer` 从纯 keyword 桩改为真实 LLM 判定——复用 digest 层同一把 OpenAI 兼容 key(`DIGEST_API_KEY`/`DIGEST_BASE_URL`/`DIGEST_MODEL`,同 ADR-007),不新增 GitHub secret。keyword 打分作为**每条都先算好的基线**,LLM 判定只在有 client 配置、预算未耗尽、缓存未命中时才覆盖;任一环节失败(超预算/解析失败/网络异常)都保留 keyword 基线分,主题产出永远不会因为 LLM 掉线而空手。`SCORERS` 注册表里 `keyword_prefilter+llm`(frontier 用)改直接指向纯 keyword 实现,**不再共享** `llm` 那个真实现——frontier 一次产出 754 条(vs ai_health 147 + quant_factor 15 = 162 条),真接进来会让日常 LLM 调用量涨 5.6 倍,而 frontier 官方源信号本来就强、关键词打分够用,ADR-003 原话点名"相关性偏弱"的只有 health/quant 两个主题。`pipeline.run_topic()` 新增 `scorer_overrides` 参数、`runner.run_all()` 里按 env 是否配置构造真实/桩 `LlmScorer` 并注入——之所以不能像 fetcher 那样走纯无状态注册表,是因为真实打分需要运行时才知道的 cache 路径(挂在 `output_dir` 下)和跨主题共享的预算计数器,这两个 `radar.scorers.get_scorer()` 的静态单例拿不到。
原因: 真花钱的调用必须能就低不就高——宁可某天判定失败退回关键词,也不能让一个主题因为 LLM 掉线而空产出(与 digest 层"never raises"哲学一致,ADR-006/007 已验证过这个模式)。范围收窄到 ai_health/quant_factor 是显式用户决策(之前问过,选了"只两个主题",非我自行决定)。
代价: 本地无法验证真实判定质量——DeepSeek key 只在 GitHub Secrets 里,不下沉到本地环境,真实效果要等下次 Actions 跑完看 `score_reason` 是否变成自然语言(而非 `hits: x, y` 关键词格式)才能确认。budget=200/次运行是硬编码常量非配置项,ai_health+quant_factor 冷启动共 162 条勉强够,如果这两个主题源增多导致单次新条目超预算,多出的会静默退回关键词分(不报错,但需要人工发现)。

### ADR-010: fetcher 统一用真实浏览器 UA + Accept 头,不再用机器人 UA
日期: 2026-07-02
决策: `radar/fetchers/feed.py` 与 `scrape.py` 的 `USER_AGENT` 从 `Mozilla/5.0 (compatible; mta-news-radar/0.1)` 改为主流桌面 Chrome UA,并加 `Accept`(feed 声明 rss/atom/xml,scrape 声明 html)+ `Accept-Language` 头,抽成 `BROWSER_HEADERS`。这是把之前散落在 topics.yaml 里一堆源的 `status=verify`/`403` note(Endpoints News 明确写「需带浏览器 UA」、多个 Substack、MIT Press)的根因一次性解决——绝大多数 403 是 Cloudflare/WAF 的「拦非浏览器客户端」规则,机器人味 UA 撞墙。配套 topics.yaml 换源:Substack 的 `*.substack.com` feed 换到自有域名(`www.quantseeker.com/feed`、`jack-clark.net/feed/`)绕开 Substack 边缘 IP 拦截;Cognitive Revolution 换成 Megaphone 真音频 feed;xAI(x.ai/news/rss.xml 实测 404,RSS 不存在)与 MIT Press(Cloudflare 硬拦,浏览器 UA 仍 403)显式 `enabled:false`,避免长期红失败噪声。
原因: 一个 UA 常量改动比逐源试错省事,且对所有现有+未来源都生效(依赖反转:HTTP 策略属 fetcher 层,不该泄漏到每条源配置)。换自有域名而非靠 UA 硬扛 Substack,是因为 `*.substack.com` 的 403 疑似 IP 段级(GitHub Actions IP 被 Substack 拦),UA 修不了,自有域名(CNAME 到 Substack 但走不同边缘)实测能过。
代价: 浏览器 UA 是「伪装」,若某站将来按更强指纹(TLS/JA3、header 顺序)反爬仍会掉线,requests 层伪装能力有限。Nature 两源(nbt/natmachintell.rss)本地网络仍不可达(Max retries),但线上 GitHub Actions 一直 `ok`,属本地环境限制非代码问题,保持 `status=verify` 不动。xAI/MIT Press 禁用是止血非解决,要接得另走 scrape 或第三方桥。
