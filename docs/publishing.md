# 发布这个仓库

## 1 · 建仓

```bash
git init
git add .
git commit -m "feat: comfyui-apng-motion 1.1.0"
git branch -M main
gh repo create comfyui-apng-motion --public --source . --remote origin --push
```

没有 `gh` 就在 GitHub 网页建空仓库，然后：

```bash
git remote add origin https://github.com/<你>/comfyui-apng-motion.git
git push -u origin main
```

## 2 · 替换占位符

README 与 README.zh-CN 里的徽章地址用了 `yourname`：

```bash
# Linux / macOS
grep -rl "yourname/comfyui-apng-motion" . | xargs sed -i "s/yourname\/comfyui-apng-motion/<你>\/comfyui-apng-motion/g"
```

Windows PowerShell：

```powershell
Get-ChildItem -Recurse -Include *.md | ForEach-Object {
  (Get-Content $_.FullName -Raw) -replace 'yourname/comfyui-apng-motion', '<你>/comfyui-apng-motion' |
    Set-Content $_.FullName -NoNewline
}
```

## 3 · 打 tag 发版

```bash
git tag v1.1.0
git push origin v1.1.0
```

`.github/workflows/release.yml` 会自动跑 `package.py`，把 zip 与 `.sha256` 附到 Release。

## 4 · 打开 Pages（可选）

仓库 Settings → Pages → Source 选 **GitHub Actions**。
之后 `deploy-docs.yml` 每次改 `docs/` 会把 mkdocs 发到 Pages。

## 5 · 发版前自检

```bash
python -m compileall -q scripts tests
pytest -q
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story assets/story.4beat.json --out /tmp/x.json
python scripts/package.py
```

最后一条应输出 `VALIDATE OK` 与 zip 的 sha256。

## 6 · 不要提交的东西

`.gitignore` 已排除：`profiles/`（本机路径）、`dist/`（构建产物）、`*.bak*`、`__pycache__/`。
