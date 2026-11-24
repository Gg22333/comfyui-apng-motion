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
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json --story assets/story.4beat.json --out /tmp/x.json
```

输出必须是 `VALIDATE OK`。

## 版本

- 功能变更 → 更新 `skill.json` 的 `version` 与 `CHANGELOG.md`
- 发版：`python scripts/package.py` 然后 `git tag vX.Y.Z`

**版本号只升一级，能补丁就补丁：**

| 位 | 什么时候动 | 例子 |
| --- | --- | --- |
| PATCH `x.y.Z` | 修 bug、改文案、加诊断参数、加可选 widget、兼容性小改 | 1.5.0 → 1.5.1 |
| MINOR `x.Y.0` | 新增用户可见的节点或工作流类别，且一次至少 3 个以上大项 | 只有「单节点 + 19 档缓动」这种量级才配 |
| MAJOR `X.0.0` | 工作流格式不兼容、必须重装或重新生成图 | 极少 |

拿不准就升 PATCH。**不要一次跨两级**，也不要用 MINOR 装零散小改。

## 提交信息

```
feat: 新能力
fix: 修复
docs: 文档
chore: 杂项
```

## 许可

提交 PR 即表示你同意该贡献按 MIT 许可发布，允许在本仓库中分发与再许可。
请勿提交来自 GPL 项目的代码片段——KJNodes、VideoHelperSuite 与 ComfyUI 只作为运行依赖，
通过节点调用使用，源码不进本仓库。

By submitting a pull request you agree that your contribution is licensed under
the MIT License (see LICENSE), and that you will not paste GPL-licensed source
code from ComfyUI, KJNodes or VideoHelperSuite into this repository.

