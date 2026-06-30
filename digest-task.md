# MTA News Radar 内容加工层 Tasks

> 基于已批准的 digest-spec.md + digest-plan.md。范围:引擎侧产出 `title_zh`/`summary_zh` 到 JSON;前端消费留下一个模块。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `requirements.txt` | 加 `anthropic` |
| 修改 | `radar/models.py` | `Item` 增 `title_zh`/`summary_zh` |
| 新建 | `radar/digest/__init__.py` | `build_digester` 工厂 |
| 新建 | `radar/digest/base.py` | `Digester` 协议 + `DigestRequest`/`DigestOutput`/`DigestConfig` |
| 新建 | `radar/digest/cache.py` | `DigestCache` |
| 新建 | `radar/digest/noop.py` | `NoopDigester` |
| 新建 | `radar/digest/claude.py` | `ClaudeDigester`(Haiku 4.5) |
| 新建 | `radar/digest/service.py` | `DigestService` |
| 修改 | `radar/writer.py` | 序列化 `title_zh`/`summary_zh` |
| 修改 | `radar/runner.py` | 集成 `DigestService` |
| 新建 | `tests/test_radar_digest.py` | FakeDigester 注入测试 |

## T0: 依赖与 models 扩展
**文件:** `requirements.txt`、`radar/models.py`
**步骤:** requirements 加 `anthropic`;`Item` 增 `title_zh: str | None = None`、`summary_zh: str | None = None`。

## T1: digest/base.py
**文件:** `radar/digest/base.py`
**依赖:** T0
**步骤:** 定义 `DigestRequest(id, title, summary)`、`DigestOutput(title_zh, summary_zh)`(frozen);`DigestConfig(top_n=24, max_items_per_run=200, model="claude-haiku-4-5", max_concurrency=6)`;`Digester` Protocol:`digest(requests: list[DigestRequest]) -> dict[str, DigestOutput]`。

## T2: digest/cache.py
**文件:** `radar/digest/cache.py`
**依赖:** T1
**步骤:** `DigestCache(path)`:内存 dict;`load()` 读 JSON(不存在则空);`save()` 写 JSON;`get(id) -> DigestOutput | None`;`put(id, output)`。JSON 形如 `{id: {"title_zh":..,"summary_zh":..}}`。

## T3: digest/noop.py
**文件:** `radar/digest/noop.py`
**依赖:** T1
**步骤:** `NoopDigester.digest(requests)` 返回 `{}`。

## T4: digest/claude.py
**文件:** `radar/digest/claude.py`
**依赖:** T1
**步骤:**
1. `ClaudeDigester(config, client=None)`:client 为空则 `anthropic.Anthropic()`。
2. `digest(requests)`:`ThreadPoolExecutor(max_concurrency)` 并发,每条调 `client.messages.create(model=config.model, max_tokens=512, system=SYSTEM, messages=[{"role":"user","content": title+summary}], output_config={"format":{"type":"json_schema","schema": SCHEMA}})`。
3. `SYSTEM`:中文编辑,产「中文标题(≤30字)+ 2-3 句中文摘要」,忠实不编造,英文则翻译。`SCHEMA`:object `{title_zh:string, summary_zh:string}` required + `additionalProperties:false`。
4. 解析首个 text block 的 JSON → `DigestOutput`;任何异常/解析失败 → 跳过该 id(不抛、不计入结果)。
5. 汇总 `dict[id, DigestOutput]` 返回。

## T5: digest/__init__.py
**文件:** `radar/digest/__init__.py`
**依赖:** T3、T4
**步骤:** `build_digester(config) -> Digester`:`os.environ.get("ANTHROPIC_API_KEY")` 且 `os.environ.get("DIGEST_ENABLED","1")!="0"` → `ClaudeDigester(config)`,否则打印一行降级提示并返回 `NoopDigester()`。

## T6: digest/service.py
**文件:** `radar/digest/service.py`
**依赖:** T1、T2
**步骤:**
1. `DigestService(digester, cache, config)`;`self._budget = config.max_items_per_run`。
2. `process(result, topic)`:`targets = result.items[:config.top_n]`;`from_cache=0`、`llm_calls=0`。
3. 命中缓存的回填 `title_zh/summary_zh`、`from_cache+=1`。
4. 未缓存的取前 `min(len, self._budget)` 条 → `digester.digest([DigestRequest(...)])` → 写缓存、回填、`llm_calls+=len(outs)`、`self._budget-=len(被尝试的)`。
5. `result.stats` 写入 `digest_targets=len(targets)`、`from_cache`、`llm_calls`。

## T7: writer 序列化
**文件:** `radar/writer.py`
**依赖:** T0
**步骤:** `_item_to_dict` 增 `"title_zh": item.title_zh`、`"summary_zh": item.summary_zh`。

## T8: runner 集成
**文件:** `radar/runner.py`
**依赖:** T5、T6
**步骤:** `run_all` 开头建 `DigestConfig`、`cache=DigestCache(output_dir/"digest-cache.json").load()`、`service=DigestService(build_digester(cfg), cache, cfg)`;每主题 `run_topic` 后 `service.process(result, topic)` 再 `write_topic`;循环末 `cache.save()`。注:digest 异常不应中断主题——`process` 内自身已 try/except 兜底。

## T9: 测试
**文件:** `tests/test_radar_digest.py`
**依赖:** T1–T8
**步骤:** 定义 `FakeDigester`(按 id 返回固定中文,或对某 id 抛错);测:
1. service 对 top-N 回填 zh、N 之后不回填;
2. 第二次 process 全命中缓存、`llm_calls==0`;
3. `max_items_per_run=K` 时只新加工 K 条;
4. `NoopDigester` → 无 zh;
5. 某 id 加工失败(不在返回里)→ 该条留空、其余正常;
6. `DigestCache` save→load 往返一致;
7. `build_digester` 无 `ANTHROPIC_API_KEY` → 返回 `NoopDigester`(monkeypatch env)。

## 执行顺序
```
T0 → T1 ─┬→ T2 ─┐
         ├→ T3  │
         ├→ T4  ├→ T6 → T8 → T9
         └→ T5 ─┘
   T7(并行,依赖 T0)────────→ T8
```
