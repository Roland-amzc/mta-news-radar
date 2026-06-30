# MTA News Radar Actions+Pages 部署 Checklist

> 分两类:本地可验(我现在跑)+ push 后在 GitHub 验(你触发后看)。

## 本地可验(现在)
- [ ] `radar.yml` YAML 合法(验证:`python -c "import yaml; yaml.safe_load(open('.github/workflows/radar.yml'))"` 退出 0)。
- [ ] `update-news.yml` 已删 schedule、YAML 仍合法(验证:解析通过 + `grep -c 'schedule' update-news.yml` 为 0)。
- [ ] workflow 引用的命令本地成立:`python run_radar.py`(全主题或 `--only`)产出 `data/<topic>/latest.json` + `index.json`(验证:跑一次看产出)。
- [ ] `_site` 暂存逻辑正确:含 `index.html`/`assets`/`data`,不含 `data/digest-cache.json`、不含 `radar/`/`scripts/`/`tests/`(验证:本地照工作流命令暂存一份,`find _site` 核对)。
- [ ] workflow 不含明文密钥(验证:grep `radar.yml` 无 key 字面量,只引用 `secrets.`/`vars.`)。

## push 后在 GitHub 验(你做)
- [ ] 配好 Secret `DIGEST_API_KEY` + Pages Source=Actions 后,手动 Run workflow → job 绿(验证:Actions 页看运行)。
- [ ] 运行日志显示 `[digest] OpenAI-compatible provider: …` 且 `run_radar.py` 打印各主题条数(验证:看日志)。
- [ ] Pages URL 打开 → 多主题雷达页,条目带中文标题+摘要(验证:浏览器打开 `https://<user>.github.io/<repo>/`)。
- [ ] 不配 `DIGEST_API_KEY` 时:job 仍绿、页面显示英文原文(验证:临时不配 secret 跑一次)。
- [ ] 二次跑:日志 `from_cache` > 0(actions/cache 命中,只加工新条目)(验证:连跑两次看日志)。
- [ ] 旧 `update-news.yml` 不再自动触发(验证:Actions 页无每 30 分钟的旧 workflow 运行)。

## 端到端
- [ ] 场景(GitHub):设 Secret + Pages=Actions → Run workflow → 等部署 → 打开 Pages URL,看到 7 主题中文要点雷达(结果:线上可访问)。
