# Security Policy

## 报告

请通过 GitHub 的私有安全公告（Security → Advisories）报告，不要开公开 issue。

## 范围

| 项 | 说明 |
| --- | --- |
| 本仓库脚本 | 只读写工作目录、`profiles/` 与 `dist/`；只在显式 `--run` 时访问本机 ComfyUI HTTP 接口 |
| 不收集 | 不上传任何数据，不包含遥测 |
| 外部依赖 | 风险由 ComfyUI / KJNodes / VHS 各自承担 |

## 使用边界

`--run` 会向本机 ComfyUI 提交任务并写入其 `output/` 目录。请只在你拥有或获授权使用的实例上运行。
