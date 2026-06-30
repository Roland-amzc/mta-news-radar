# MTA News Radar 前端主题 tab Tasks

> 基于已批准的 frontend-spec.md + frontend-plan.md。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 改名 | `index.html` → `index.legacy.html` | 归档旧 AI 单主题页 |
| 新建 | `index.html` | 干净多主题页结构 + `<template>` 卡片 |
| 新建 | `assets/radar.css` | 本页样式 |
| 新建 | `assets/radar.js` | 本页逻辑(单文件) |

## T1: 归档旧页
**文件:** `index.html` → `index.legacy.html`
**依赖:** 无
**步骤:** `git mv index.html index.legacy.html`(旧 assets app.js/styles.css/motion.js 保留给它,不删)。
**验证:** `index.legacy.html` 存在;`git status` 显示 rename。

## T2: 新 index.html 骨架
**文件:** `index.html`(新)
**依赖:** T1
**步骤:**
1. 头部:站点标题 + `更新时间` 占位。
2. 容器:`#tabBar`(tab 条)、`#topicHeader`(主题头部)、`#newsList`(列表)、`#healthDetail`(`<details>` 健康详情)、`#message`(错误/空态)。
3. `<template id="itemTpl">`:卡片含 标题链接 / 来源 / 时间 / 摘要 / sub_label / 分数徽章 槽位。
4. 引 `assets/radar.css` 与 `assets/radar.js`(defer)。
**验证:** 本地 server 打开,结构在、无 JS 报错(空壳)。

## T3: radar.css
**文件:** `assets/radar.css`(新)
**依赖:** T2
**步骤:** tab 条(横向可滚动)、卡片、主题头部、健康摘要 pill、健康详情、空/错误态、响应式断点的样式。
**验证:** 起 server 视觉成形,移动宽度 tab 可横滚。

## T4: radar.js 数据层 + controller 骨架
**文件:** `assets/radar.js`(新)
**依赖:** T2
**步骤:**
1. `state = { index, topicCache: new Map(), activeId }`。
2. `loadIndex()` fetch `data/index.json`;`loadTopic(dataUrl)` fetch 主题 JSON(均 `await resp.ok` 检查)。
3. `init()`:`loadIndex()` → 存 `state.index` → 调 `renderTabs` + `selectTopic(第一个)`;catch → `renderError`。
**验证:** console 无错,`state.index` 拿到 7 主题。

## T5: tab 渲染 + 切换
**文件:** `assets/radar.js`
**依赖:** T4
**步骤:** `renderTabs(topics, activeId)` 渲染 tab(名称+`count`);点击 → `selectTopic(id)`;`selectTopic` 维护 `activeId` + 高亮 + 缓存命中判断。
**验证:** tab 出现、点击切换高亮,默认选第一个。

## T6: 主题视图 + 健康
**文件:** `assets/radar.js`
**依赖:** T5
**步骤:** `renderTopic(data)` 渲染头部(name/mode/window_hours/count/`formatTime(generated_at)`)+ `renderHealth` 摘要(ok·failed·skipped 计数)与详情(failed/skipped 名称+原因);`topic_error` 或空 items → `renderEmpty`。
**验证:** 切主题头部更新;切到含失败源的主题(如 ai_health)健康摘要/详情正确。

## T7: 条目渲染
**文件:** `assets/radar.js`
**依赖:** T6
**步骤:** `renderItem(item, mode)` 克隆 `<template>`:标题链接(`target=_blank rel=noopener`)、来源、`formatTime(published)`、摘要(有才显示)、sub_label;`mode==='topic'` 填分数徽章,否则隐藏。**全部用 `textContent`**。`renderTopic` 按 `items` 顺序 append,不重排。
**验证:** `quant_factor` 条目带分数、顺序同 JSON;`entity_radar` 无分数、按时间。

## T8: 错误/空态接线
**文件:** `assets/radar.js`
**依赖:** T7
**步骤:** `renderError(msg)` 在 `#message` 显眼提示并清空列表;`loadIndex`/`loadTopic` 失败均走它;`renderEmpty` 文案区分「空」与「topic_error」。
**验证:** 临时把 `data/index.json` 改名 → 页面明确报错、不白屏。

## T9: 本地端到端验证
**文件:** —
**依赖:** T2–T8
**步骤:** `python3 -m http.server` 起页,浏览器走一遍:tab 数、切换、topic/entity 展示差异、健康详情、错误态。
**验证:** 见 frontend-checklist.md 逐条。

## 执行顺序
```
T1 → T2 → T3
        └→ T4 → T5 → T6 → T7 → T8 → T9
```
