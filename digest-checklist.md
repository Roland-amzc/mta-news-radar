# MTA News Radar 内容加工层 Checklist

> 引擎侧验收:单测(注入 FakeDigester,零网络)+ 产出 JSON 观察。真实 Haiku 加工质量需 `ANTHROPIC_API_KEY` 另验(见末尾)。

## 实现完整性
- [ ] `radar.digest` 包可导入(验证:`python -c "import radar.digest, radar.digest.service, radar.digest.claude"` 退出 0;`claude.py` 仅在调用时才需 key)。
- [ ] `pytest tests/test_radar_digest.py` 全绿(验证:运行,0 失败)。

## 加工范围与回填(AC1)
- [ ] 注入 FakeDigester 跑一主题 → 排序后前 N 条得非空 `title_zh`+`summary_zh`,第 N+1 条起为空(验证:断言 `items[:N]` 有值、`items[N:]` 为 None)。

## 缓存(AC3 / N7)
- [ ] 同数据第二次 `process` → 全命中缓存,`stats.llm_calls==0`,zh 字段不变(验证:第二次断言 llm_calls=0 且值一致)。
- [ ] `DigestCache` save→load 往返后内容一致(验证:写入若干条、save、新实例 load、逐条比对)。

## 预算闸(AC4)
- [ ] `max_items_per_run=K`、无缓存、目标 > K → 本次只新加工 K 条,其余无 zh,不报错(验证:断言 llm_calls==K,剩余条目 zh 为空)。

## 优雅降级(AC5 / AC6)
- [ ] 无 `ANTHROPIC_API_KEY` → `build_digester` 返回 `NoopDigester`;整管线跑通、条目无 zh、进程退出 0(验证:monkeypatch 删 env,跑 run_all,断言无 zh、退出 0)。
- [ ] 某 id 加工失败(FakeDigester 不返回该 id)→ 该条 zh 留空、其余条目正常回填(验证:构造部分失败,断言)。

## 产出 JSON(AC7)
- [ ] `data/<topic>/latest.json` 条目含 `title_zh`/`summary_zh` 键(有加工则非空,否则 null);`stats` 含 `digest_targets`/`from_cache`/`llm_calls`(验证:`json.load` 后断言键存在)。

## 可测性 / 安全(AC8 / N3)
- [ ] 全部单测经注入 `FakeDigester` 完成,无真实网络调用(验证:测试不导入真实 client / 不需 key)。
- [ ] `ANTHROPIC_API_KEY` 不出现在代码、产出 JSON、日志中(验证:grep 代码与 latest.json 无 key 字面量)。

## 编译与回归
- [ ] `pytest tests/test_radar_*.py` 全绿(含既有引擎测试,无回归)。
- [ ] 代码规范:snake_case/PascalCase/类型注解(验证:人工抽查)。

## 端到端(注入桩)
- [ ] 场景:用 FakeDigester 跑 `run_radar.py --only quant_factor` → `data/quant_factor/latest.json` 前 N 条带中文 zh、`digest-cache.json` 生成、stats 计数正确(结果:文件与字段符合)。

## 需真实 key 另验(本轮不阻塞)
- [ ] (需 key)`AC2`:英文条目 `title_zh` 为中文译名、中文条目 `title_zh` 为中文、`summary_zh` 为 2-3 句中文 —— 配 `ANTHROPIC_API_KEY` 后对 frontier/quant 抽样人工核验。
