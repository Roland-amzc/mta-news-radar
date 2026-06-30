# MTA News Radar 前端主题 tab Plan

> 基于已批准的 frontend-spec.md。纯静态页,原生 HTML/CSS/JS,无框架、无构建。

## 架构概览

单页应用,逻辑集中在 `assets/radar.js`,分 5 个职责块,依赖单向(controller → renderers → data loader → DOM):

| 块 | 职责 |
|---|---|
| **data loader** | fetch `index.json`、fetch 主题 `data_url`、主题级缓存、错误传播。 |
| **tab bar** | 按 index topics 渲染 tab(名称+条数)、处理点击切换、维护 active 态。 |
| **topic view** | 渲染主题头部(元信息 + 源健康摘要)+ 条目列表 + 可展开健康详情 + 空/错误态。 |
| **item renderer** | 渲染单条卡片;按 `mode` 决定是否带分数徽章。 |
| **app controller** | `init`:加载 index → 渲染 tab → 选默认主题 → 按需加载并渲染主题;绑定 tab 切换。 |

## 核心数据结构

### 运行时状态(JS)
```
state = {
  index: { topics: [...] } | null,     // 解析后的 index.json
  topicCache: Map<topic_id, topicData>,// 已加载主题数据缓存
  activeId: string | null,             // 当前主题 id
}
```
`index.topics[i]` = `{ id, name, mode, window_hours, count, stats, topic_error, generated_at, data_url }`
`topicData` = `{ topic_id, name, mode, window_hours, generated_at, topic_error, stats, source_health: [{ source_name, type, status, fetched, error }], items: [{ id, title, url, source_name, tier, summary, published, sub_label, score, score_reason }] }`

### 主要函数签名(用途)
- `loadIndex() -> Promise<index>`:fetch `data/index.json`,解析返回。
- `loadTopic(dataUrl) -> Promise<topicData>`:fetch 主题 JSON。
- `selectTopic(id)`:缓存命中用缓存,否则 `loadTopic` 后写 `topicCache`,再 `renderTopic`。
- `renderTabs(topics, activeId)`:渲染 tab 条;点击回调 `selectTopic`。
- `renderTopic(topicData)`:渲染头部 + 列表 + 健康详情;空/错误走对应分支。
- `renderItem(item, mode) -> HTMLElement`:克隆 `<template>` 填充;`mode==='topic'` 时填分数徽章。
- `renderHealth(sourceHealth) -> { summary, detail }`:计 ok/failed/skipped 数 + 详情列表。
- `formatTime(iso) -> string`:`toLocaleString('zh-CN')`,无值返回占位。
- `renderError(msg)` / `renderEmpty(topicData)`:错误态 / 空态。
- `init()`:入口。

## 模块交互

```
init()
 └─ loadIndex()
     ├─ 失败 → renderError("加载 index.json 失败")
     └─ 成功 → state.index = index
               renderTabs(index.topics, activeId=index.topics[0].id)
               selectTopic(index.topics[0].id)

selectTopic(id):
   state.activeId = id; 高亮对应 tab
   if topicCache.has(id): renderTopic(cache)
   else: loadTopic(topic.data_url)
          ├─ 失败 → renderError("加载主题数据失败")
          └─ 成功 → topicCache.set(id, data); renderTopic(data)

renderTopic(data):
   渲染头部(name/mode/window_hours/count/generated_at + renderHealth.summary)
   if data.topic_error or items 为空 → renderEmpty(data)
   else → data.items.forEach(it => list.append(renderItem(it, data.mode)))   # 不重排
   健康详情面板 ← renderHealth.detail

tab 点击 → selectTopic(id)
```

数据流:`index.json → state.index → tabs`;`data_url → topicData(缓存)→ 头部/列表/健康`。

## 文件组织

```
mta-news-radar/
├── index.html            # 新建:干净多主题页(结构 + <template> 卡片)
├── index.legacy.html     # 由旧 index.html 改名归档(不再维护)
├── assets/
│   ├── radar.css         # 新建:本页样式
│   └── radar.js          # 新建:本页逻辑(单文件,defer 加载)
└── data/                 # 引擎产出(只读消费)
    ├── index.json
    └── <topic>/latest.json
```
旧 `assets/app.js` / `styles.css` / `motion.js` 保留给归档页,新页不引用。

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 重建形态 | 新 `index.html` + `radar.css` + `radar.js`;旧页 → `index.legacy.html` | 已选重建干净页;旧页 AI 概念耦合重 |
| 无框架/无构建 | 原生 JS 单文件 `radar.js`(defer) | 纯静态、规模小,无打包器 |
| 数据加载 | `fetch` + 主题级 `Map` 缓存 | F2 懒加载、不重复请求 |
| 渲染 | DOM API + `<template>` 卡片 | 无框架下清晰 |
| 安全 | 标题/摘要一律 `textContent`,禁用 innerHTML 注入 | feed 内容不可信,防 XSS |
| 排序 | 前端不排,按 `items` 顺序渲染 | 引擎已按 mode 排好(topic 分数 / entity 时间) |
| mode 适配 | 读 `topicData.mode` 决定是否渲染分数徽章 | F4 |
| 时间本地化 | `toLocaleString('zh-CN')` | F3 |
| 旧页兼容 | 不保活,归档即可 | 干净切断 N3 |
