# Contributing

## 环境

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

测试不联网、不用 GPU：只校验曲线、工作流结构、UI→API 转换与资产完整性。

## 改动范围

| 目录 | 规则 |
| --- | --- |
| `scripts/` | 只用标准库 + Pillow；不要写死盘符、端口、模型名，一律从 profile 读 |
| `assets/` | 改工作流模板后必须能被 `emit_workflow.py --validate` 通过 |
| `SKILL.md` | 面向执行者，写「怎么做」和「为什么」，不写流水账 |
| `docs/` | 一页一件事，命令可直接粘贴 |

## 提交前检查

```bash
python -m compileall -q scripts
pytest -q
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story assets/story.4beat.json --out /tmp/x.json
```

输出必须是 `VALIDATE OK`。

## 版本

- 功能变更 → 更新 `skill.json` 的 `version` 与 `CHANGELOG.md`
- 发版：`python scripts/package.py` 然后 `git tag vX.Y.Z`

## 提交信息

```
feat: 新能力
fix: 修复
docs: 文档
chore: 杂项
```
