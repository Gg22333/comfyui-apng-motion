# 发布这个仓库

仓库已经在 <https://github.com/Gg22333/comfyui-apng-motion>，下面的流程是**改版时**重复用的。

## 1 · 改版本号

三个地方必须一起改：

| 文件 | 字段 |
| --- | --- |
| `skill.json` | `"version"` |
| `pyproject.toml` | `version` |
| `CHANGELOG.md` | 顶部新增一节 |

先选对号位：

| 改动 | 升哪一位 |
| --- | --- |
| 修 bug、文案、诊断参数、可选 widget | PATCH：`1.5.0 → 1.5.1` |
| 新增节点/工作流类别，且是成组的大改 | MINOR：`1.5.1 → 1.6.0` |
| 工作流不兼容、必须重装 | MAJOR：`1.6.0 → 2.0.0` |

默认 PATCH。一次只升一级；零散小改不要凑成 MINOR。

## 2 · 提交与打 tag

```bash
git add -A
git commit -m "feat: 一句话说清这次做了什么 (v1.3.2)"
git tag v1.3.2
git push origin main
git push origin v1.3.2
```

`.github/workflows/release.yml` 监听 `v*` tag，会自动跑 `scripts/package.py`，
把 `dist/*.zip` 和 `.sha256` 附到 Release。

## 3 · 网页

`deploy-docs.yml` 在 `docs/**`、`mkdocs.yml`、`README*.md`、`workflows/**`、`assets/**`
任一变动时触发：

1. 跑 `scripts/sync_workflows.py`，把 `workflows/` 与 `assets/*.json` 镜像到 `docs/assets/{workflows,presets}`；
2. `mkdocs gh-deploy --force` 推到 `gh-pages`。

站点：<https://gg22333.github.io/comfyui-apng-motion/>

Pages 的构建方式是 **legacy / 分支 `gh-pages` / root**，不是 GitHub Actions 直出。
所以 `docs/assets/workflows/*.json` 不进 git（见 `.gitignore`），只在构建时生成。

## 4 · 改完自检

```bash
python -m compileall -q scripts tests
pytest -q
python scripts/sync_workflows.py --check
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json --story assets/story.4beat.json --out /tmp/x.json
python scripts/emit_workflow.py --base workflows/workflow-moss.json --story assets/story.diet.json --size 512 --out /tmp/diet.json
python scripts/package.py
```

期望：测试全绿、`SAME`、两行 `VALIDATE OK`、zip 与 sha256 生成。

## 5 · 不要提交的东西

`.gitignore` 已排除：`profiles/`（本机路径）、`dist/`（构建产物）、`*.bak*`、
`__pycache__/`、`.pytest_cache/`、`docs/assets/workflows/`、`docs/assets/presets/`。
