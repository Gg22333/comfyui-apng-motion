# AGENTS.md

给在本仓库工作的 agent：

## 事实源

- 唯一源就是本仓库根目录；`profiles/` 与 `dist/` 是生成物，不进版本库。
- 改动 `scripts/` 后必须跑 `pytest -q` 与一次 `emit_workflow.py --validate`。

## 常用命令

```bash
python scripts/detect_env.py
python scripts/doctor.py
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story assets/story.4beat.json --out /tmp/x.json
python scripts/check_deps.py
pytest -q
```

## 约束

- 不在脚本里写死盘符、端口、模型名。
- 不改 `assets/*.json` 的节点结构而不跑校验。
- 版本号只改 `skill.json`，并同步 `CHANGELOG.md`。
