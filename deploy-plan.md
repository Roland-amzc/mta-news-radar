# MTA News Radar Actions+Pages 部署 Plan

> 基于已批准的 deploy-spec.md。GitHub Actions YAML。

## 架构概览

一个新工作流 `.github/workflows/radar.yml`(build+deploy 单 job)+ 停用旧 `update-news.yml` 的定时触发。无引擎/前端改动。

## 核心结构(workflow)

单 job `build-deploy`(`ubuntu-latest`):
1. `actions/checkout@v4`
2. `actions/setup-python@v5`(3.11)
3. `pip install -r requirements.txt`
4. `actions/cache@v4` 还原/保存 `data/digest-cache.json`(key 带 run_id,restore-keys `digest-cache-`)
5. `python run_radar.py`(env 注入 `DIGEST_API_KEY`(secret)/`DIGEST_BASE_URL`/`DIGEST_MODEL`(vars+默认))
6. 暂存站点:`_site/` ← `index.html` + `site.webmanifest` + `assets/` + `data/`(剔除 `data/digest-cache.json`)
7. `actions/upload-pages-artifact@v3`(path=`_site`)
8. `actions/deploy-pages@v4`

触发:`schedule: cron "0 22 * * *"`(每天 22:00 UTC ≈ 北京 06:00)+ `workflow_dispatch`。
权限:`contents: read` / `pages: write` / `id-token: write`。并发组 `pages`(不取消进行中)。

## 模块设计

### .github/workflows/radar.yml(新建)
**职责:** 定时/手动跑引擎 → 部署 Pages。
**关键点:**
- `env` 在 job 级:`DIGEST_API_KEY: ${{ secrets.DIGEST_API_KEY }}`、`DIGEST_BASE_URL: ${{ vars.DIGEST_BASE_URL || 'https://api.deepseek.com' }}`、`DIGEST_MODEL: ${{ vars.DIGEST_MODEL || 'deepseek-chat' }}`。
- 无 secret 时 `DIGEST_API_KEY` 为空 → 工厂走 Noop → 引擎照常产出无 zh(F6),workflow 成功。
- `_site` 暂存避免把 `radar/`、`scripts/`、`tests/`、`*.md` 发到 Pages 根。

### .github/workflows/update-news.yml(修改)
**职责:** 停用旧引擎定时跑。**改动:** 删除 `schedule:` 段(保留 `workflow_dispatch`,不自动触发)。

## 模块交互

```
schedule/dispatch
 └─ build-deploy job:
      checkout → setup-python → pip install
      → cache restore(digest-cache.json)
      → run_radar.py (env: DIGEST_*)  → 产出 data/<topic>/latest.json + index.json
      → stage _site (html+assets+data, 去 digest-cache)
      → upload-pages-artifact(_site) → deploy-pages → 站点上线
      (cache 自动 save digest-cache.json)
```

## 文件组织
```
mta-news-radar/.github/workflows/
├── radar.yml            # 新建:build + deploy
└── update-news.yml      # 修改:去掉 schedule(停用旧引擎定时)
```

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 部署方式 | Pages artifact(build+deploy) | 生成数据不入库,与 gitignore 一致;现代 Pages 推荐 |
| 数据持久化 | 不持久化 data/,只持久化 digest 缓存(actions/cache) | data 每次重生成;缓存跨运行省钱(只加工新条目) |
| 频率 | `cron "0 22 * * *"` 每天一次 | 最慢窗 2 周、最快 72h,日级足够;成本极低 |
| 密钥 | `DIGEST_API_KEY` Secret;base_url/model 用 Variables+默认 | 只一个真密钥;换 provider 改 Variables 不动代码 |
| 无 key 处理 | 引擎降级(Noop),workflow 仍成功 | F6;先上线英文版,配 key 后自动变中文 |
| Python | setup-python 3.11 | 引擎 3.9+ 兼容;3.11 稳 |
| 站点暂存 | `_site/` 只装 html+assets+data | 不把源码/文档/缓存发到 Pages |
| 旧 workflow | 删 `update-news.yml` 的 schedule(保留 dispatch) | 停止每 30 分钟跑旧引擎;不删文件、最小改动 |
| actions 版本 | checkout@v4 / setup-python@v5 / cache@v4 / upload-pages-artifact@v3 / deploy-pages@v4 | 钉大版本,官方维护 |
