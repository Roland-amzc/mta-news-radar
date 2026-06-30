# MTA News Radar 前端消费 zh 字段 Plan

> 基于已批准的 frontend-zh-spec.md。纯前端,原生 JS。

## 架构概览

无新组件:在现有 `assets/radar.js` 的 `renderItem` 里消费 `title_zh`/`summary_zh`,模板加一个副标题元素,样式加一条。其余渲染流程不变。

## 核心数据结构

`latest.json` 条目已含可选字段 `title_zh: string|null`、`summary_zh: string|null`(top-N 条目非空,其余 null)。前端按存在与否分支,无需新类型。

## 模块设计

### index.html(模板)
卡片模板在 `.card-title` 之后增 `<div class="card-subtitle" hidden></div>`(承载英文原标题,纯文本)。

### assets/radar.js(`renderItem`)
**职责:** 按 zh 字段决定标题/摘要显示。
- 标题:`item.title_zh` 有值 → `cardTitle.textContent = item.title_zh`;副标题 `textContent = htmlToText(item.title)`、`hidden=false`。无值 → `cardTitle.textContent = htmlToText(item.title)`;副标题 `hidden=true`(回退现状)。两种情况 `cardTitle.href = item.url`。
- 摘要:`text = item.summary_zh ? htmlToText(item.summary_zh) : cleanSummary(item.summary)`;有 text 才显示。
- 收听 / 分数徽章 / 时间 / sub_label 逻辑不变。

### assets/radar.css
新增 `.card-subtitle`:小字号、灰色、`margin` 紧贴标题下方;`[hidden]` 已全局生效。

## 模块交互

```
renderTopic → data.items.forEach → renderItem(item, mode)
   renderItem:
     title_zh? 主标题=中文 + 副标题=原文(显示) : 主标题=原文 + 副标题(隐藏)
     主标题.href = url
     摘要 = summary_zh ? htmlToText(summary_zh) : cleanSummary(summary)
```
数据流不变,仅 renderItem 内部按字段分支。

## 文件组织
```
mta-news-radar/
├── index.html            # 修改:卡片模板加 .card-subtitle
├── assets/radar.css      # 修改:.card-subtitle 样式
└── assets/radar.js       # 修改:renderItem 消费 zh
```

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 副标题显示时机 | 仅 `title_zh` 有值时显示 | 无翻译时不重复原标题、不留空行 |
| 摘要清洗 | `summary_zh` 用 `htmlToText`,不用 `cleanSummary` | summary_zh 已是干净中文摘要;cleanSummary 的时间轴/标记截断会误伤 |
| 中文标题承接链接 | 主标题(中文)即 `url` 链接 | 用户点中文也能到原文;副标题纯文本 |
| 渲染 | 中文/原文均 `textContent` | 防 XSS(F5/N2) |
| 回退 | 无 zh → 原标题 + cleanSummary | top-N 之外/降级条目自然回退(F3) |
