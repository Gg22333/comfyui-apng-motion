# CHANGELOG

## 1.1.2 — 2026-11-23

- 预览图重出：`story.preview.json` 改为上半身四拍（中性 → 惊讶 → 大笑 → 死鱼眼），关键帧同 seed、denoise 0.55；`docs/assets/preview.gif` 换成新片（24 帧，相邻帧 diff avg 2.49，颜色漂移 1.37）。
- 修复 `emit_workflow.py --run` 的自动验片：Windows 上 `os.system` 对多段带引号路径报 `filename syntax is incorrect`，改用 `subprocess.call` 列表参数。
- `assets/workflow-sdxl-preview.json` 同步重生成。

## 1.1.1 — 2026-11-23

- 新增 `scripts/check_output.py`：检查 `output/APNG/` 根目录游离文件、三格式缺组、`output/` 根残留、VHS 首帧预览；`--fix` 归档到 `archive/stray-<时间戳>/`。
- 新增 `docs/output.md` / `docs/en/output.md`：落盘目录、三格式硬规则、游离文件四类来源、验收清单、归档约定。
- 修复 `emit_workflow.py --seed-mode`：现在会回写到**已有关键帧**的 KSampler，关键帧统一同 seed + 同 denoise；`story.json` 的 `seed_mode` 生效。
- 重新生成 `assets/workflow-sdxl-4beat.json`、`workflow-moss-4beat.json`、`workflow-sdxl-preview.json`：全部关键帧同 seed。
- 补齐 `docs/en/` 英文文档，README 里的链接不再 404；mkdocs 增加成品落盘页与 English 分区。

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
