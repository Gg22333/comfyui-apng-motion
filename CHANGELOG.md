# CHANGELOG

## 1.3.1 — 2026-11-23

- **六拍全身故事**：新增 `assets/story.diet.json` 与 `diet-betrayal` 动作预设
  （60 帧 / 30fps / 640×640 / `moss_zh` / denoise 0.85）。主预览换成这一版，
  并新增 `docs/assets/storyboard-diet.webp` 关键拍联系表。
- **第二套提示词方言**：`emit_workflow.py --prompt-mode tags|moss_zh`。`moss_zh` 把
  `lock / action / style` 拼成中文散文，换行分段、每段以「。」收尾；适合 MOSS / Qwen-VL 文本编码器。
- **`--size` / `--width` / `--height`**：直接改 latent 尺寸，不用在画布上找节点。
- **`--notes-only`**：给任意工作流补/更新两个说明 Note（参数清单 + 提示词写法），幂等。
- **工作流独立目录**：`assets/workflow-*.json` → `workflows/`，新增 `workflows/README.md`；
  新增 `scripts/sync_workflows.py`，把 `workflows/` 与 `assets/*.json` 镜像到
  `docs/assets/{workflows,presets}`，`--check` 查漂移，已接入 CI 与 Pages 构建。
- **新页面**：`docs/workflows.md` / `docs/en/workflows.md`（下载、结构、两个环境的参数差异、
  提示词方言、帧数表）。
- **`check_anim.py --segs`**：按拍比较段首与段尾，输出 `full` 与画面下半区 `lower` 差异；
  `--strict` 让 CI 在表演不足时失败。
- **`make_storyboard.py`**：按 segs 抽关键拍拼联系表。
- 修：`docs/install.md` 的 `yourname`、`docs/publishing.md` 过时步骤、GIF 体积、
  `site_url` 大小写、`deploy-docs.yml` 不监听 `workflows/` 与 `assets/`、
  `install.py` 不排除 `.pytest_cache`。
- 帧数表统一为 8 @8fps / 24 @10fps / 30 @15fps / 60 @30fps。
- 测试 49 → 56 项。

## 1.3.0 — 2026-11-23

- **任意帧数**：`emit_workflow.py` 新增 `--frames N`（8–60），剧情卡支持 `"frames"`；`--segs` 之和必须等于 N，
  缺省按拍平均分；`ensure_frames()` 自动克隆/删除 `LatentInterpolate` + `VAEDecode`，重建 `ImageBatchMulti`
  的 `image_1..image_N` 与计数值，并按 6 列重排画布。`validate()` 改为「插值数 = 解码数 = batch 接线数」。
- **修两个真 bug**：空 `motion` 不再参与 `ConditioningCombine`（旁路，避免稀释本帧提示导致掉画质）；
  提示词顺序改为 `lock + action + style`（Moss 文本编码器对末尾 token 权重最高）。
- **动作库**：新增 `assets/motion-presets.json`（16 组：9 情绪 + 5 动作 + 2 五拍故事）与 `scripts/make_story.py`；
  自动校验 `frames >= beats`、`len(segs) == beats`、`sum(segs) == frames`。
- **60 帧 Moss 展示图**：`assets/story.preview.json` 改为 4 拍 / 60 帧 / 30fps / denoise 0.5；
  `preview.webp`（384², q100, 1.78 MB, 60 帧）与 `preview.gif`（384², 全局调色板 + `dither=NONE`, 1.46 MB）重出。
  注：q90 会把 60 帧压成 58 帧（libwebp 合并近重复帧），默认改 q100 并核对帧数。
- **文档去 24 帧化**：README / usage / formats / architecture / FAQ / SKILL 改成 8–60 帧口径；
  formats 补 24 / 60 帧体积实测；新增中英双语 `docs/motion-presets.md`（平台规格 + 五拍语法 + 提示词规则 + 16 组动作）。
- 修正 usage 节点数表：4 拍 69/71、5 拍 72/74（此前写少了 `ConditioningCombine`）。
- 测试 40 → 49 项：任意帧数扩缩、空 motion 旁路、prompt 顺序、动作库与 `make_story.py`。

## 1.2.1 — 2026-11-23

- 新增全局动作层：每个工作流带一个共享的 `CLIPTextEncode`「全局动作指导」+ 每关键帧一个 `ConditioningCombine`，
  改一处全片生效；每帧提示仍独立可调。画布内附 `Note` 参数清单。
- 插值曲线改为段内 `linear`（每帧步长恒定），新增 `--curve linear|ease|snap`；旧的 `snap` 幂曲线保留但不再是默认。
- `emit_workflow.py` 新增 `--motion` `--curve` `--seed` `--steps` `--cfg`；重复 emit 幂等，不会叠加合并节点。
- 修 `--run`：`Note` / `Reroute` / `PrimitiveNode` 是纯前端节点，不再被当成服务器缺节点。
- 预览图重出并重编码：关键帧 denoise 0.55 → 0.35，相邻帧差异 2.34 → 1.08，颜色漂移 3.07 → 2.63。
- 新增 `scripts/make_preview.py`：全局固定调色板 + `dither=none` 重编码 GIF（相邻帧差异 2.49 → 1.03，体积 3.45 MB → 0.76 MB），
  同时输出 WebP（0.57 MB）作为网页主预览。
- `docs/formats.md` 增加「网页预览为什么用 WebP」和「色块闪动的两个来源」；README / usage 增加模型支持表与可调参数表。
- GitHub topics 补 `dit` `moss` `webp` `gif` `image-generation`；Dependabot 的三个 action 升级合并进主线。

## 1.2.0 — 2026-11-23

- 双环境统一：xl 与 Dit 的 3 拍模板、4 拍模板、正在使用的工作流全部改成关键帧同 seed；`test_shipped_assets_share_one_seed` 防止回退。
- 新增 `docs/synthesis-comparison.md` / `docs/en/synthesis-comparison.md`：APNG 定义与 GIF 差异、和 Live2D / Spine 的定位区别、与逐帧 AI / 视频生成 / 序列帧 / Lottie 的对比、采样次数与显存账。
- README 增加「Why it is cheap / 为什么省算力」：3 拍 60 次、4 拍 80 次采样，对比逐帧 480 次。
- mkdocs 导航、docs 索引、formats 交叉链接补齐。

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
