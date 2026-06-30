# MTA News Radar 引擎深度重构 Checklist

> 每项通过运行代码或观察行为验证,聚焦系统行为(与具体实现解耦)。
> 括号内为验证方式。覆盖 spec.md 的 AC1–AC13。

## 实现完整性
- [ ] `radar` 包及所有子模块可导入,无 import 错误(验证:`python -c "import radar.runner, radar.config, radar.pipeline"` 退出 0)。
- [ ] `config.load_topics("topics.yaml")` 返回 7 个 `TopicSpec`,各含源清单(验证:跑一段加载脚本,打印主题数 = 7)。

## 配置校验(AC1)
- [ ] **当前** `topics.yaml`(含 scrape/x_account/enabled:false/author_id:TODO 源)→ 全部 7 主题正常解析,那些源在 `source_health` 记 `skipped` 而非报错(验证:加载后断言主题数 = 7、被跳过源 status = skipped)。
- [ ] 缺必填字段 / 未知 `scorer` / **拼错的 `type`** / `entity` 模式非 `none` 打分 → 抛 `ConfigError`,CLI 以非 0 退出(验证:对故意写坏的配置跑 `run_radar.py`,观察退出码 = 2 且报错信息清晰)。

## 抓取与统一条目(AC3)
- [ ] `rss / arxiv / arxiv_author / podcast / youtube` 各至少一个源能解析出 `Item`,字段 标题/链接/来源名/tier 非空;`sub_label`/`summary`/`published` 可空(配了 sub_label 则透传)(验证:对 `tests/fixtures/radar/` 样本解析断言字段;或真实源各跑一次抽查)。

## 时间窗(AC4)
- [ ] `frontier`(72h)与 `new_books`(2w)产出中**`published` 非空**的条目落各自窗内;`published=None` 的条目可保留但排在末尾(验证:跑这两个主题,有时间的最早条目 ≥ now − window,无时间的排在尾部)。
- [ ] 改某主题 `window` 重跑 → 过滤边界随之变化(验证:把 frontier 改 24h 重跑,条目数减少或边界前移)。

## 打分策略(AC5)
- [ ] `scorer=keyword` 主题:用主题 `keywords` 对 `title+summary` 打分,条目带 `score` 且按 score 降序(验证:观察输出 items 的 score 单调不增,命中词体现在 score_reason)。
- [ ] `scorer=none`(entity)主题:条目 `score=None`、按 `published` 倒序(验证:观察 score 全空、时间单调不增)。
- [ ] `scorer=llm` 主题:走桩、**全程无网络 LLM 调用**,结果与 keyword 一致(验证:断网或 mock 断言无外部 LLM 请求;对比同输入下 llm 与 keyword 输出 score 相同)。

## 两种 mode 行为(AC6)
- [ ] `entity_radar` 全收(不因低分丢条)、按时间倒序(验证:跑该主题,条目数 = 各源去重后总数)。
- [ ] `topic` 模式应用门禁后,低于 `score_gate` 的条目不进主榜(验证:设一个 `score_gate>0`,断言输出无低分条目)。

## 实体反混淆(AC7)
- [ ] `arxiv_author` 源按作者 ID 锚定,只返回该 ID 的论文(验证:用一个**已知有效 author_id**(姚顺宇真实 ID 待补,先用任一可验证作者)跑,人工抽查返回论文均属该作者,无同名混入)。

## 粗筛与去重(AC8 / AC9)
- [ ] 带 `prefilter` 的 arXiv 源:产出元信息 `stats.after_prefilter < stats.fetched_total`(验证:读 `latest.json` 的 stats,断言前者 < 后者)。
- [ ] 同一故事多来源样本 → 去重后只留一条,且为 tier 更高来源(验证:构造 official+self_media 同标题样本,断言保留 official)。

## 分主题产出(AC10 / AC12 / AC13)
- [ ] 每主题 `data/<topic>/latest.json` 含条目列表 + 元信息(生成时间/window/源健康 `ok|failed|skipped`/各阶段 `stats`),可被 JSON 解析(验证:`json.load` 每个文件成功,断言 keys 齐全)。
- [ ] 顶层 `data/index.json` 列出全部主题清单(验证:`json.load`,断言含 7 主题 id/name/mode/条目数)。
- [ ] 运行后旧路径 `data/latest-24h.json` 未被本引擎更新(验证:跑前记录 mtime,跑后比对未变)。
- [ ] 在 `topics.yaml` **仅加配置**新增一个主题(不改 `radar/` 代码)→ 重跑后 `data/<新topic>/latest.json` 出现且含条目(验证:加一个测试主题跑 `run_radar.py`,观察新目录产出)。

## 健壮性(AC11)
- [ ] 空主题 / 某主题源全失败 / 配置缺源 → 产出结构合法的空 JSON,进程退出 0、不崩溃(验证:构造全坏源的主题跑,观察 `latest.json` 为合法空列表 + 退出码 0)。

## 故障隔离(AC2)
- [ ] 某主题一个源不可达 → 该主题其余源仍出结果、其他主题不受影响,`source_health` 标该源 `status=failed`;deferred/禁用源标 `status=skipped`(验证:把一个源 URL 改为不可达地址跑,观察其余条目正常 + health 标记正确)。
- [ ] 主题级硬错也写出 `data/<topic>/latest.json`(`items=[]` + `topic_error` 可见)(验证:制造一个主题级异常,确认产出文件仍生成且 topic_error 非空)。

## 编译与测试
- [ ] `pytest tests/test_radar_*.py` 全绿(验证:运行,观察 0 失败)。
- [ ] 代码符合规范:snake_case 文件/函数、PascalCase 类、类型注解齐全(验证:人工 + 可选 lint 抽查)。

## 端到端场景
- [ ] 场景 1:`python run_radar.py --only frontier` → `data/frontier/latest.json` 含近 72h 条目、按 score 降序、`source_health` 记录各源状态(结果:文件生成且内容符合)。
- [ ] 场景 2:`python run_radar.py --only entity_radar` → 全收、按时间倒序、score 全空(结果:符合 entity 语义)。
- [ ] 场景 3:`python run_radar.py`(全量)→ 7 主题各自 `data/<topic>/latest.json` + `data/index.json` 全部生成,单个慢/坏主题不阻断其余(结果:全部文件就位)。
