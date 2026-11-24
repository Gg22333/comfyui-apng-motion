# CHANGELOG

## 1.4.0 — 2026-11-24

**一个节点出整段 + 缓动分档到 19 种。**

- **`APNGOneShot`（`APNG One Shot`）**：`model/clip/vae/positive/negative` → `IMAGE`，不用搭图。
  内部与 `--dynamic` 工作流等价：K 拍各跑一次 `common_ksampler`（第 1 拍 denoise 1.0，之后默认 0.4），
  latent 插值成整段，一次 `VAEDecode`，最后走镜头。**采样次数 = 拍数，不是帧数**，不会退化成本项目
  明确否掉的逐帧重绘。`actions` 用 `|` 或换行分隔，`frames` 平均分配到各拍（余数给最后一拍）。
- **缓动 7 → 19**：在原有 `linear/sine/cubic/quint/back/elastic/bounce` 之外，新增
  `sine_in/sine_out/cubic_in/cubic_out/quint_in/quint_out/back_in/back_out/elastic_in/elastic_out/bounce_in/bounce_out`。
  裸名保持历史数值（`sine` 缓入缓出，`cubic/quint/back/elastic` 缓入，`bounce` 缓出），
  已有工作流出帧不变 —— 有回归测试逐值比对。
- **`apply_camera()` / `camera_is_neutral()`** 抽成模块函数，`APNGCameraMove` 与 `APNGOneShot` 共用；
  中立参数直接跳过重采样。
- **测试**：旧 7 种缓动逐值不变、`_out` 与 `_in` 镜像、19 种两端取到 0/1、`split_actions` / `split_segments`。
- **版本号**：1.3.10 → 1.4.0。

## 1.3.10 — 2026-11-24

**镜头出图的漂移误报修掉：`check_anim.py --camera`。**

- 带 `--camera` 的动态图整段在位移，`check_anim.py` 原来用固定阈值 20 判 `color drift`，
  正常平移 / 推近也会报 `FAIL: 颜色漂移 > 20，大概率是色块闪`。现在新增 `--camera`：
  阈值放宽到 45，并明确标注「漂移来自整段位移，不等于色块闪」。
- `emit_workflow.py --run` 会读工作流的镜头 widget；只要 `x/y/zoom/angle` 任一偏离中立位，
  就自动给 `check_anim.py` 加 `--camera`，`--run` 不再对镜头图误报。
- 新增 `tests/test_check_anim.py`（默认阈值仍报 FAIL、`--camera` 放宽、120 的离谱漂移照样 FAIL、
  `--json` 带 `camera` 字段）与 `test_camera_motion_detection`。
- `scripts/package.py`：`docs/assets` 的排除条件从「只排该层」改成「排整棵子树」，
  本地先跑过 `sync_workflows.py` 再打包也不会把文档镜像重复塞进 zip。
- 版本号：1.3.9 → 1.3.10。

## 1.3.9 — 2026-11-24

**整段镜头运动：平移 / 缩放 / 旋转 + 缓动，一次作用于全部帧。**

- **`APNGCameraMove`（`APNG Camera Move`）**：`images → IMAGE` 的纯像素仿射变换，
  参数 `x / y / zoom / angle / easing / loop / border`。不重新采样、不加依赖、
  不碰采样器，只 `torch.nn.functional.affine_grid` + `grid_sample`。
  `easing` 支持 `linear / sine / cubic / quint / back / elastic / bounce`；
  `loop=True` 时推进量走 0→1→0，首尾帧像素完全一致。
- **`emit_workflow.py --camera`**：动态模式在 `VAEDecode` 后插镜头节点，三个保存节点与
  `APNGFrameStats` 全部改接镜头输出，帧差 / 接缝检查看的是最终像素。3 拍 24 帧 = 27 节点。
- **`--validate`**：新增镜头节点校验（参数类型、easing/loop/border 取值、接线必须是
  `VAEDecode → APNGCameraMove → 保存/报告`），静态图里出现镜头节点直接报错。
- **随包工作流**：`workflow-sdxl-dynamic-camera.json`、`workflow-moss-dynamic-camera.json`。
- **测试**：`camera_progress` 端点、缓动端点、平移方向（±x）、缩放、`loop` 首末帧一致、
  非法 widget / 错误接线 / 静态图混用镜头节点的负例。
- **引用**：整段镜头 + 缓动的思路来自
  [ShmuelRonen/ComfyUI-AstralAnimator](https://github.com/ShmuelRonen/ComfyUI-AstralAnimator)。
  该仓库无 LICENSE 文件，**未复用任何代码**；见 NOTICE 与 CITATION.cff。
- **版本号**：1.3.8 → 1.3.9。

## 1.3.8 — 2026-11-24

**工作流里直接调帧数、看帧差、看接缝。** 新增随包 ComfyUI 自定义节点（`comfyui_nodes/`），
把「N 个 LatentInterpolate + N 个 VAEDecode」压成「每拍一个插值节点 + 一次解码」。

- **`APNGLatentInterpolateN`**：`samples1/samples2 → LATENT(batch=frames)`。
  `frames` 是图上的 INT widget（1–240），改数字即改这一拍的帧数；`role`（first/middle/last）
  与 `curve`（linear/ease/snap）与 `comfy_lib.build_curve` 的单段结果逐值一致。
- **`APNGLatentConcat`**：把多拍 batch 按顺序拼接，用于一次解码全部帧。
- **`APNGFrameStats`**：存盘前打印总帧数、`frames/fps` 时长、相邻帧差 min/max/avg、
  相同帧对数，以及每拍 `K_n→K_n+1` 的 full/lower 差与循环接缝 `K_N→K0`，阈值与
  `scripts/check_anim.py` 相同。接 `OUTPUT_NODE`，结果显示在节点和 ComfyUI 日志里。
- **`emit_workflow.py --dynamic`**：输出动态图结构（3 拍 24 帧 = 26 节点 / 39 连线，
  静态原图 67 节点）。三拍各一个 `frames` widget，一次 `VAEDecode` 后同时接三个保存节点
  和帧报告；`--validate` 会检查 frames 之和与 `segs` 是否一致、role/curve 是否合法、
  是否只剩一个解码节点。
- **`scripts/install_nodes.py`**：读 `profiles/*.json` 的 `comfy_root`，把 `comfyui_nodes`
  复制到 `<comfy_root>/custom_nodes/apng_motion_nodes/`；支持 `--profile`、`--all`、
  `--check`、`--dry-run`。装完重启 ComfyUI 生效。
- **修 bug**：命令行 `--frames` 覆盖剧情卡帧数时，不再照抄剧情卡的 `segs`（否则总和对不上），
  改为按拍重新平均分。
- **测试**：新增 `tests/test_dynamic.py`（比例 parity、动态图结构、非法 widget、
  静态模式回归、install_nodes 拷贝与 `--check`）。
- **版本号**：1.3.7 → 1.3.8。

## 1.3.7 — 2026-11-24

- **默认目标再补两家**：`skill.json` 的 `targets` 增加 `~/.dsh/skills/comfyui-apng-motion`
  （DSH / DeepSeek harness）与 `~/.workbuddy/skills/comfyui-apng-motion`（WorkBuddy 用户级 skills 目录）。
  父目录存在才装，不存在一律跳过，行为与 Codex / Claude Code / magpie 一致。
- **文档**：中英 `docs/install.md` 的目标清单与客户端对照表同步补 DSH、WorkBuddy 两行。
- **版本号**：1.3.6 → 1.3.7。

## 1.3.6 — 2026-11-24

- **默认目标补 Claude Code**：`skill.json` 的 `targets` 增加 `~/.claude/skills/comfyui-apng-motion`，
  不带 `--dest` 时只要 `~/.claude/skills` 存在就一并安装，不用手打路径。
- **提示语改通用**：找不到目标时的提示不再只提 `~/.codex/skills`，改成 `--dest` 或任一客户端 skill 目录。
- **修脏拷贝**：`install.py` / `package.py` 的跳过表补 `site`、`.venv`、`venv`、`node_modules`。
  此前在仓库里跑过 `mkdocs build` 再安装/打包，会把整个 `site/` 站点（约 90 个文件）一起拷进去。
- **版本号**：1.3.5 → 1.3.6。

## 1.3.5 — 2026-11-24

- **安装说明补通用性**：`SKILL.md` 0.8 与 `docs/install.md`（中英）补上 Claude Code 与任意
  Agent Skills 目录的安装方式，并写明 `SKILL.md` 只有 `name` / `description`，没有 Codex 私有字段；
  脚本只依赖 Python ≥3.9 + Pillow，CI 在 `ubuntu-24.04` × 3.9 / 3.12 上跑。
- **清掉作者本机路径**：`E:\...\comfyui-apng\skill` 与 `C:\Users\...\archived_sessions\*.jsonl`
  不再出现在 `SKILL.md`，改成「仓库根目录 + 来历记录见 CHANGELOG」，别人 clone 后不会看到对不上的路径。
- **版本号**：1.3.4 → 1.3.5。
## 1.3.4 — 2026-11-24

- **补齐预览工作流**：新增 `workflows/workflow-moss-preview.json`（60 帧 / 11 拍 / 20fps /
  `denoise 0.85`），与 `assets/story.diet.json` 一致，就是首页那张预览图的配方；
  `workflows/workflow-sdxl-preview.json` 按 `assets/story.preview.json` 重生成
  （60 帧 / 4 拍 / `denoise 0.5`）。旧文件停在 24 帧，Note 也还是「SDXL / MOSS 两套」的旧标题。
- **`workflows/README.md` 对齐 v1.3.3**：环境列改成「UNet（SDXL）/ DiT（MOSS-Image）」，
  不再把 DiT 与模型并列；节点数改成实测值（67 / 70 / 69 / 72）；关键帧 denoise 改成 0.82–0.90；
  帧数表改成 60 帧 / 20fps / 3.00 秒默认；提示词段收敛为三种方言，规则链接到 `docs/prompting.md`。
- **文档下载表**：中英 `workflows.md` 的「预览用」拆成 SDXL / MOSS 两行，各自写真实参数。
- **版本号**：1.3.3 → 1.3.4。

## 1.3.3 — 2026-11-24

- **节奏参数化**：新增 `scripts/timing.py` 作为帧延时唯一真相源，导出
  `frame_delays(frames, segs, fps, dwell, ease, quantum)`。两条不变量有测试守住：
  列表长度恒等于 `frames`，总延时恒等于 `frames / fps`。
- **每拍停留（`dwell`）与拍内缓动（`ease`）**：剧情卡新增两个字段。`fps` 决定总时长，
  `dwell` 决定这段时间怎么分给每一拍，`ease` 让每拍首尾帧多停、中段加速。
  ComfyUI 的保存节点只接受一个全局 fps，所以这两项由新增的 `scripts/retime.py`
  在**导出后**写进 APNG 的 fcTL 延时——像素一个字节都不动，不重跑采样。
- **默认成片放慢到 3 秒**：`story.diet.json` 与 `diet-betrayal` 预设从 `30fps` 改为 `20fps`，
  60 帧 = 3.00 秒；`dwell = 0.95,0.95,1.1,1.3,1.0,1.3,0.95,1.0,0.9,0.95,0.95`，
  够手机与抱桶两拍各多停 30%，单拍最短 210 ms（原来 60 帧 11 拍挤在 2 秒里，平均每拍 180 ms）。
- **GIF 帧延时口径写进文档**：GIF 的延时只能量化到 10 ms（1 厘秒）。24fps 会被写成 40 ms，
  整片实际 2.4 秒而不是 2.5 秒；30fps 实际 1.8 秒。20 / 25 fps 整除，不会走样。
  APNG / WebP 是毫秒精度，不受限。
- **新增 `docs/prompting.md` 提示词权威页**（中英各一份）：三种方言按**文本编码器**分
  （CLIP 标签 / Qwen-VL 散文 / T5 句子），逐拍三段式，可测量身体描述对照表，常见翻车表。
  并入 `moss-image-prompt-enhancer` 的四条 Layout 规则：绝对像素 bbox、画布边长取 16 的倍数、
  不写占位符、只描述可见内容。README、`usage`、`workflows`、`SKILL.md` 与画布 Note 里的写法段
  全部收敛为摘要 + 链接。
- **新增 `docs/models.md` 模型与架构页**（中英各一份），修正分类错误：
  **DiT 是架构，MOSS 是模型**。旧文档把「Moss / DiT」并列，等于把架构当成了 MOSS 之外的另一类。
  现在按三层组织——架构（UNet / DiT）、文本编码器（CLIP / T5 / Qwen-VL）、步数范式（常规 / DMD·Turbo），
  覆盖 SD1.5、SDXL、FLUX.1、SD3/3.5、MOSS-Image、Krea 2、Anima 2B、Qwen-Image，每条给加载器与出处。
  本机目录 `-xl` / `-Dit` 明确写为「跑 UNet 系 / 跑 DiT 系」，不是分类标准。
- **画布 Note 重写**：标题从「提示词写法（SDXL / MOSS 两套）」改为「提示词写法（按架构分方言）」，
  内容加三种方言、Layout 四条、fps 与 dwell 分工。Note 复用改为按标题首行匹配，旧标题也能原地更新，
  不会叠出第三个 Note。
- **`check_anim.py --story`**：按剧情卡读 `segs`，逐拍打印毫秒数，低于 200 ms 的拍给 WARN。
  `make_preview.py --story` 用同一份延时写 GIF / WebP。
- **`make_story.py`**：透传 `dwell` / `ease`；改了帧数导致 `segs` 变化时自动丢弃旧 `dwell`。
- **测试**：新增 `tests/test_timing.py` 10 项；全仓 69 项通过。
- **预览重出**：`docs/assets/preview.webp` / `preview.gif` 从重定时后的 APNG 重新编码，
  60 帧 / 3.00 秒 / 384×384。
- **README 合并为单文件双语言**：GitHub 一次只渲染一个文件，`README.md` ↔ `README.zh-CN.md`
  互链必然是整页跳转，没法原地切换。现在中文全文放进 `README.md` 的 `<details>` 折叠块，
  点 summary 原地展开；顶部的「简体中文」改成页内锚点 `#简体中文`，锚点落在折叠块外面的
  可见标题上，不会跳进一段看不见的内容。`README.zh-CN.md` 保留为十几行指针页，旧链接不断。


- **许可与署名加固**：`LICENSE` 的版权主体从 `comfyui-apng-motion contributors` 改为
  `Gg22333`（此前无可主张的权利人）；新增 `NOTICE`，写明 MIT 授权范围、KJNodes /
  VideoHelperSuite / ComfyUI 三个 GPL-3.0 运行依赖「只调用节点、未复制源码」、
  以及项目名与 Logo 不在 MIT 授权内；新增 `CITATION.cff`，GitHub 侧栏会显示
  "Cite this repository"。README 中英双版补「保留声明即可、回链不强制」与 fork 不得冒充官方。

## 1.3.2 — 2026-11-23

- **接缝停顿修复**：`build_curve()` 不再让每段都从 `1.0` 走到 `0.0`。旧排法段尾与下一段段首是
  同一个关键帧，实测接缝相邻帧差只有 `0.06`，播放像卡住。现在关键帧在时间线上只出现一次；
  最后一段停在 K0 前一格，循环回第 0 帧不会多停一帧。
- **十一拍 60 帧故事**：`diet-betrayal` 从 6 拍拆成 11 拍，大动作（够手机、抱炸鸡桶）给 7 帧，
  小动作给 4–5 帧，`segs = 5,5,4,7,6,7,5,6,5,5,5`。成片相邻帧差 `1.72–5.00`（平均 `2.78`），
  接缝无 0.06 级停顿。
- **画面锚点**：每个动作以「矮木桌前，」开头，背景收敛为墙面 / 台灯 / 矮桌；11 个关键帧的
  桌子与白碗全程在画面里，减少道具忽隐忽现。
- **Moss denoise 口径修正**：关键帧 `denoise` 从 `0.50–0.80` 改为 `0.82–0.90`。MOSS 是 8 步 DMD，
  低于 0.80 关键帧几乎不动（整片相邻帧差 0.03）；动作靠提示词与分帧，不靠继续抬 denoise。
- **文档站改版**：接入 `mkdocs-static-i18n`，右上角语言选择器直接切到同一页的中/英版本（不另开窗口）；
  新增顶部导航分组、代码复制、搜索建议、自定义排版层 `docs/stylesheets/extra.css`。
- **新章节**：`docs/workflows.md#过渡帧怎么排` / `docs/en/workflows.md#how-to-lay-out-transition-frames`，
  写明接缝重复的根因、每拍帧预算、`check_anim.py` 的读数与处理。
- **回归测试**：新增段内严格递减、段尾关键帧唯一、封面只出现一次、末帧留循环间隙四项。
- 重新生成 `docs/assets/preview.webp` / `preview.gif` / `storyboard-diet.webp`。

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
