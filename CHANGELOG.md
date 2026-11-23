# CHANGELOG

## 1.1.0 — 2026-11-23

- 可移植：新增 `scripts/detect_env.py`（扫本机 ComfyUI → `profiles/*.json`）、`scripts/doctor.py`（逐项体检）。
- 剧情：`scripts/emit_workflow.py` 把 3 关键帧工作流扩成 3–5 拍，编译剧情卡、重算曲线、校验连线，支持 `--run`。
- 依赖：`skill.json` / `requirements.txt` / `scripts/check_deps.py`；VHS 的 `/object_info` 过大导致重置时回落到 `assets/node_schema.json`。
- 分发：`scripts/package.py`（确定性 zip + SHA256）、`scripts/install.py`（多目标安装 + 自动备份）。
- 修复：ratio 唯一化从"只比相邻"改成全局去重——3 拍默认曲线里两个 `0.665` 会被 Pillow 合并成 23 帧。
- 增强：`check_anim.py` 增加颜色漂移指标（`color_drift`），超过 6 时告警。

## 1.0.0 — 2026-11-23

- 首版：三关键帧 latent 插值、24 帧曲线、三格式输出、只存成品、双环境参数、排错表。
- 来源：2026-11-22 搭建会话、2026-11-23 续修会话、2026-11-23 交接会话。
