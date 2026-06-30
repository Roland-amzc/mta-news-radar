# MTA News Radar Actions+Pages 部署 Spec

> 范围:加 GitHub Actions 工作流(每天跑引擎)+ GitHub Pages 部署(artifact 方式)。不动引擎/前端逻辑。

## 背景

引擎 + 前端 + 内容加工层(多 provider,DeepSeek 实测)全完成,本地 `run_radar.py` 能产出 `data/<topic>/latest.json` + `index.json`,静态页 `index.html`+`assets` 读它们。现在要在 GitHub 上自动定时跑并发布成网页。旧 `.github/workflows/update-news.yml`(跑旧引擎、每 30 分钟)需停用。

## 目标

- **G1**:GitHub Actions 每天定时跑 `run_radar.py`(+手动触发)。
- **G2**:整站(`index.html`+`assets`+`data`)以 **Pages artifact** 部署,生成数据不入库。
- **G3**:加工密钥走 Secrets,digest 缓存跨运行持久化省钱。

## 功能需求

- **F1 触发**:`schedule`(每天一次)+ `workflow_dispatch`(手动)。
- **F2 跑引擎**:checkout → 装 Python + 依赖 → 跑 `run_radar.py`(全主题)→ 产出 `data/`。
- **F3 密钥/配置**:`DIGEST_API_KEY` 走 Secret;`DIGEST_BASE_URL`/`DIGEST_MODEL` 走 Variables(带 DeepSeek 默认);注入 run 步骤 env,不打印。
- **F4 缓存**:`actions/cache` 还原/保存 `digest-cache.json`,跨运行复用、只加工新条目。
- **F5 部署**:把 `index.html`+`assets`+`data` 暂存为站点目录 → Pages artifact → 发布。
- **F6 优雅**:无 `DIGEST_API_KEY` 时引擎降级照常产出、workflow 不失败、部署照常。
- **F7 停用旧 workflow**:`update-news.yml` 移除定时触发(不再每 30 分钟跑旧引擎)。

## 非功能需求

- **N1** Secrets 不入库、不入日志。
- **N2** 用官方 actions(checkout / setup-python / cache / upload-pages-artifact / deploy-pages)并钉大版本。
- **N3** 最小权限:`contents: read`、`pages: write`、`id-token: write`。
- **N4** 不动引擎 / 前端逻辑。

## 不做的事

- 提交数据到分支(已选 artifact)。
- 矩阵 / 多 workflow 并行。
- 自定义域名。
- **替你设 Secrets / 启用 Pages / push**(给你步骤,你在仓库设置里做)。

## 验收标准

- **AC1**(本地可验):workflow YAML 合法;`run_radar.py` 全主题能产出 data(已验)。
- **AC2**(push 后 GitHub):手动/定时跑 → 产出 `data/<topic>/latest.json` + `index.json`。
- **AC3**(GitHub):Pages URL 打开 → 多主题雷达页。
- **AC4**(GitHub):配 `DIGEST_API_KEY` → 条目带中文;不配 → 回退原文、workflow 仍成功。
- **AC5**(GitHub):二次跑命中 `actions/cache` → digest 只加工新条目(看日志 from_cache/llm_calls)。
- **AC6**:产出/日志无 key 泄漏;旧 `update-news.yml` 不再定时触发。
