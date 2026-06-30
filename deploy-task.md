# MTA News Radar Actions+Pages 部署 Tasks

> 基于已批准的 deploy-spec.md + deploy-plan.md。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `.github/workflows/radar.yml` | 每天跑引擎 + Pages 部署 |
| 修改 | `.github/workflows/update-news.yml` | 删除 schedule(停用旧引擎定时) |

## T1: 新建 radar.yml
**文件:** `.github/workflows/radar.yml`
**步骤:**
1. `name`、`on`(`schedule: cron "0 22 * * *"` + `workflow_dispatch`)。
2. `permissions: contents: read / pages: write / id-token: write`;`concurrency: group: pages, cancel-in-progress: false`。
3. job `build-deploy`(`ubuntu-latest`,`environment: github-pages` + url);job 级 `env`:`DIGEST_API_KEY=${{ secrets.DIGEST_API_KEY }}`、`DIGEST_BASE_URL=${{ vars.DIGEST_BASE_URL || 'https://api.deepseek.com' }}`、`DIGEST_MODEL=${{ vars.DIGEST_MODEL || 'deepseek-chat' }}`。
4. steps:checkout@v4 → setup-python@v5(3.11) → `pip install -r requirements.txt` → cache@v4(path `data/digest-cache.json`,key `digest-cache-${{ github.run_id }}`,restore-keys `digest-cache-`)→ `python run_radar.py` → 暂存 `_site`(`mkdir _site; cp index.html site.webmanifest _site/ 2>/dev/null || true; cp -r assets _site/; cp -r data _site/data; rm -f _site/data/digest-cache.json`)→ upload-pages-artifact@v3(path `_site`)→ deploy-pages@v4(id `deploy`)。
**验证:** `python -c "import yaml; yaml.safe_load(open('.github/workflows/radar.yml'))"` 解析通过。

## T2: 停用旧 workflow
**文件:** `.github/workflows/update-news.yml`
**依赖:** 无
**步骤:** 删除 `schedule:` 段(及其 cron 行),保留 `workflow_dispatch`。
**验证:** YAML 仍合法;`grep schedule` 无结果。

## T3: 本地验证可验部分
**文件:** —
**依赖:** T1、T2
**步骤:** ① 两个 YAML 用 PyYAML 解析通过;② 模拟工作流核心(无 key)本地跑 `run_radar.py --only cn_podcasts` 产出 data + 暂存 `_site` 目录结构正确(html+assets+data、无 digest-cache)。
**验证:** 见 deploy-checklist.md(本地项)。

## 执行顺序
```
T1 → T3
T2 ↗
```

## 用户侧步骤(本地无法替你做,push 后在 GitHub)
1. 在仓库 **Settings → Secrets and variables → Actions** 加 Secret `DIGEST_API_KEY`(你**轮换后**的 key);可选加 Variables `DIGEST_BASE_URL`/`DIGEST_MODEL`(不加则用 DeepSeek 默认)。
2. **Settings → Pages → Source = GitHub Actions**。
3. push 分支并合并到默认分支(或把 workflow 放默认分支);**Actions → Run workflow** 手动触发一次。
