# MTA News Radar 前端主题 tab Checklist

> 每项通过起本地 server(`python3 -m http.server`)在浏览器观察验证。覆盖 frontend-spec.md 的 AC1–AC8。

## 实现完整性
- [ ] 页面加载无 JS 报错,`data/index.json` 被请求一次(验证:DevTools Console 无红 + Network 见 index.json)。
- [ ] 旧页已归档为 `index.legacy.html`,新 `index.html` 不引用旧 `app.js`/`styles.css`(验证:查看 index.html 源,只引 radar.css/radar.js)。

## 主题 tab(AC1 / AC2)
- [ ] 顶部 tab 数量与 `index.json` 的 topics 一致,各显示名称 + 条数,默认选中第一个(验证:数 tab、看高亮)。
- [ ] 点某 tab → 渲染该主题条目;再点已看过的 tab,Network 不再发该主题请求(验证:Network 面板观察缓存命中)。

## 条目展示(AC3 / AC4)
- [ ] 条目标题点击在新标签打开原 `url`,显示来源/时间/摘要(有则显示)(验证:点开一条、核对字段)。
- [ ] `quant_factor`(topic)条目带分数徽章、顺序与 JSON 一致;`entity_radar`(entity)无分数、顺序与 JSON 一致(验证:对照 latest.json)。

## 主题头部与健康(AC5 / AC6)
- [ ] 头部显示 window/条数/更新时间(本地化)/源健康摘要(ok·failed·skipped 计数)(验证:对照 stats/source_health)。
- [ ] 切到空或含 `topic_error` 的主题 → 显示友好空态,不白屏、不报错(验证:观察空态文案)。
- [ ] 展开源健康详情 → 列出 failed/skipped 源名称与原因(如 ai_health 的 Nature failed、entity 的姚顺宇 disabled)(验证:展开面板核对)。

## 错误态(AC7)
- [ ] 把 `data/index.json` 改名制造失败 → 页面明确报错提示,不白屏(验证:改名后刷新观察)。

## 干净切断(AC8)
- [ ] 全程 Network 面板**不出现**任何旧数据文件请求(`latest-24h.json`/`daily-brief.json`/`waytoagi-7d.json` 等)(验证:Network 过滤核对)。

## 端到端场景
- [ ] 场景 1:打开页 → 默认主题 frontier 列表加载,带分数、源健康摘要正常(结果:首屏即有内容)。
- [ ] 场景 2:切到 entity_radar → 无分数、按时间倒序、姚顺宇 skipped 见于健康详情(结果:entity 语义正确)。
- [ ] 场景 3:切到 ai_health → 健康详情显示 Nature×2 failed 及原因,列表仍有其余源条目(结果:故障不影响展示)。
