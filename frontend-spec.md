# MTA News Radar 前端主题 tab Spec

> 范围:重建一个干净的多主题前端(纯静态页)。基于引擎重构(分支 feat/radar-engine)产出的新数据。

## 背景

引擎重构产出多主题 JSON(`data/index.json` + `data/<topic>/latest.json`)。现有 `index.html` 是旧 AI 单主题重耦合页(栏目 / AI相关度 / 今日Top3 / WaytoAGI / 高级筛选),读旧 `latest-24h.json` 等——引擎已「干净切断」不再产这些数据,旧页已失效。本模块重建一个干净的多主题前端。

新数据形态:
- `data/index.json`:`{ topics: [{ id, name, mode, window_hours, count, stats, topic_error, generated_at, data_url }] }`
- `data/<topic>/latest.json`:`{ topic_id, name, mode, window_hours, generated_at, topic_error, stats, source_health: [{ source_name, type, status, fetched, error }], items: [{ id, title, url, source_name, tier, topic_id, summary, published, sub_label, score, score_reason }] }`

## 目标

- **G1**:纯静态页读 `index.json` + `data/<topic>/latest.json`,按主题 tab 切换展示。
- **G2**:适配两种 mode 的展示——`topic`(分数徽章)/ `entity`(无分数、按时间)。
- **G3**:展示主题头部元信息 + 源健康(摘要 + 可展开详情)。
- **G4**:干净重建,旧页归档,不依赖旧数据 / 旧 AI 概念。

## 功能需求

- **F1 主题 tab**:读 `index.json`,每个主题渲染一个 tab(名称 + 条数);点击切换,默认选第一个。
- **F2 懒加载**:切到某主题时 fetch 其 `data_url`,渲染;已加载缓存,不重复请求。
- **F3 条目列表**:每条显示 标题(链接、新标签打开)、来源名、发布时间(本地化)、摘要(若有)、sub_label(若有)。
- **F4 mode 适配**:`topic` 显示分数徽章;`entity` 不显示分数。两者均按引擎给定 items 顺序渲染,前端不重排。
- **F5 主题头部**:显示 名称 / mode / window / 条数 / 生成时间(本地化)/ 源健康摘要(ok·failed·skipped 计数);`topic_error` 或空列表 → 友好空/错误态。
- **F6 源健康详情面板**:可展开,列出每个源的 status + 名称 +(failed/skipped 的)原因。
- **F7 加载/错误态**:`index.json` 或主题 json 加载失败 → 明确提示,不白屏。

## 非功能需求

- **N1** 纯静态、无构建、无框架:plain HTML/CSS/JS。
- **N2** 经 `fetch` 读同源 JSON,需 http 提供(Pages/本地 server);`file://` 直开会被 CORS 挡(已知约束)。
- **N3** 干净切断:不读任何旧数据(`latest-24h.json` 等);旧 `index.html` 归档为 `index.legacy.html`。
- **N4** 响应式:移动端可用,tab 可横向滚动。
- **N5** 中文 UI。
- **N6** 可本地验证:`python -m http.server` 起页即可观察。

## 不做的事

- 搜索、排序切换、深色模式(本次不做)。
- GitHub Actions / Pages 部署(单独模块)。
- 旧页的 Top3 故事池 / WaytoAGI / AI相关度 / 高级多维筛选(不迁移)。
- 跨主题聚合视图、写操作 / 后端。

## 验收标准

- **AC1**(F1):本地 server 打开 → 顶部主题 tab 数量与 `index.json` 一致,各显示名称+条数,默认选中第一个。
- **AC2**(F2):点 tab → 渲染该主题条目;重复点已看过的 tab 不再发请求。
- **AC3**(F3):条目可点开新标签到原 `url`,显示来源/时间/摘要(有则显示)。
- **AC4**(F4):`quant_factor`(topic)条目带分数徽章、顺序同 JSON;`entity_radar`(entity)无分数、顺序同 JSON。
- **AC5**(F5):头部显示 window/条数/更新时间/源健康摘要;切到空或含 `topic_error` 的主题显示友好空态、不白屏。
- **AC6**(F6):展开源健康详情 → 列出 failed/skipped 源名称与原因(如 Nature "connection"、姚顺宇 "disabled")。
- **AC7**(F7):把 `index.json` 改名制造失败 → 页面明确报错,不白屏。
- **AC8**(N3):页面不请求任何旧数据文件;旧页已归档。
