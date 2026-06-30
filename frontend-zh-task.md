# MTA News Radar 前端消费 zh 字段 Tasks

> 基于已批准的 frontend-zh-spec.md + frontend-zh-plan.md。纯前端。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `index.html` | 卡片模板加 `.card-subtitle` |
| 修改 | `assets/radar.css` | `.card-subtitle` 样式 |
| 修改 | `assets/radar.js` | `renderItem` 消费 `title_zh`/`summary_zh` |

## T1: 模板加副标题
**文件:** `index.html`
**步骤:** 在 `<a class="card-title">` 之后加 `<div class="card-subtitle" hidden></div>`。
**验证:** 模板含该元素,默认 hidden。

## T2: 副标题样式
**文件:** `assets/radar.css`
**步骤:** 加 `.card-subtitle`:字号 ~0.78rem、颜色 `var(--faint)`、`margin: -2px 0 7px`(紧贴主标题下)。
**验证:** 起 server 观察副标题为灰色小字。

## T3: renderItem 消费 zh
**文件:** `assets/radar.js`
**依赖:** T1
**步骤:**
1. 标题:`if (item.title_zh) { cardTitle.textContent = item.title_zh; sub.textContent = htmlToText(item.title); sub.hidden = false; } else { cardTitle.textContent = htmlToText(item.title); }`。两分支后 `cardTitle.href = item.url`。
2. 摘要:`var text = item.summary_zh ? htmlToText(item.summary_zh) : cleanSummary(item.summary);` 有 text 才 `summary.hidden=false`。
3. 收听 / 分数 / 时间 / sub_label 不动。
**验证:** 带 zh 的条目显示中文主标题 + 英文副标题 + 中文摘要;无 zh 回退原文。

## T4: 本地端到端验证
**文件:** —
**依赖:** T1–T3
**步骤:** 用真实带 zh 的数据(DeepSeek 跑出的 quant_factor)同步进 preview 站点,起 server,Preview 观察中文卡片 + 副标题 + 回退条目。
**验证:** 见 frontend-zh-checklist.md。

## 执行顺序
```
T1 → T3
T2 ↗      ↘ T4
```
