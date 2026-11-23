# 成品落盘：三个文件，一条路径

这一页只讲一件事：**Queue 一次之后，文件应该出现在哪、为什么有时会出现在错的地方、怎么查、怎么清。**

配套脚本：`scripts/check_output.py`（结构检查 + 可选归档）。

---

## 1 · 正确的目录长什么样

输出根目录永远在 **ComfyUI 自己的 `output/`** 下，不在仓库里，也不在 skill 目录里：

```
<ComfyUI>/output/
└─ APNG/
   ├─ final/
   │  ├─ apng/anim24_00001_.png      ← 成品 APNG（无损，首帧可当静态图）
   │  ├─ webp/anim24_00001_.webp     ← 成品 WebP（可透明，体积最小）
   │  └─ gif/anim24_00001.gif        ← 成品 GIF（聊天用）
   │     └─ anim24_00001.png         ← VHS 首帧预览，插件副产物，可删
   └─ archive/
      ├─ frames/                     ← 需要留档的单帧（默认不产生）
      ├─ tests/                      ← 调参期试片
      └─ stray-<时间戳>/             ← check_output --fix 归档的游离文件
```

一次成功的 Queue 只产生 **三个成品**。`gif/` 里那张同名 `.png` 是 VHS 自己写的首帧预览，不是第四份成品，也不代表"每帧落盘"又回来了。

`<ComfyUI>` 是 profile 里的 `comfy_root`。两套环境各有自己的 output：

| profile | output 根 |
| --- | --- |
| `profiles/xl.json` | `D:\ComfyUI-aki-v3.2-xl\ComfyUI\output` |
| `profiles/dit.json` | `D:\ComfyUI-aki-v3.2-DiT\ComfyUI\output` |

换机器后路径由 `detect_env.py` 重新生成，不要照抄本文的盘符。

---

## 2 · 三个保存节点的硬规则

| 规则 | 说明 |
| --- | --- |
| **同一个 batch** | `SaveAnimatedPNG`、`SaveAnimatedWEBP`、`VHS_VideoCombine` 的 `images` 必须接在**同一个** `ImageBatchMulti` 的输出上。各接各的 batch，三种格式的帧序会不一致。 |
| **不接单帧保存** | 工作流里不出现 `SaveImage`、`PreviewImage`。它们是"每帧落盘"和目录塞满的来源。 |
| **前缀带目录** | `filename_prefix` 里的 `/` 会直接建子目录：`APNG/final/apng/anim24`。 |
| **前缀三路分开** | 三个节点分别写 `.../apng/anim24`、`.../webp/anim24`、`.../gif/anim24`，不能三路同前缀，否则互相覆盖。 |
| **改完刷新** | 改 `filename_prefix` 后必须 **F5 刷新浏览器页面**再 Queue。前端会缓存旧节点值，旧 prefix 就是这样把成品写回 `output/APNG/` 根目录的。 |
| **fps 三路一致** | 三路都填同一个值；只改一路会出现 APNG/WebP/GIF 时长不一致。 |
| **不用固定文件名** | ComfyUI 总会在前缀后追加 `_00001_` 计数器。想要稳定名字就固定前缀，接受计数器；不要去手动改成品名，否则 `check_output.py` 会把它标成 `odd_name`。 |

节点参数（与 `SKILL.md` 第 3 节一致）：

| 节点 | 关键参数 | 推荐值 |
| --- | --- | --- |
| `SaveAnimatedPNG` | `filename_prefix` / `fps` / `compress_level` | `APNG/final/apng/anim24` / 10 / 4 |
| `SaveAnimatedWEBP` | `filename_prefix` / `fps` / `lossless` / `quality` | `APNG/final/webp/anim24` / 10 / True / 90 |
| `VHS_VideoCombine` | `frame_rate` / `loop_count` / `filename_prefix` / `format` | 10 / 0 / `APNG/final/gif/anim24` / `image/gif` |

---

## 3 · 文件为什么会跑到 `output/APNG/` 根目录

本机确实出现过一次：`output/APNG/anim24_00001_.png` 直接躺在 `APNG/` 下，既不在 `final/apng/`，也没有同批的 WebP/GIF。原因不是保存节点写错，而是**运行时用的前缀是旧值**。

四种常见来源：

| 来源 | 现象 | 处理 |
| --- | --- | --- |
| 浏览器缓存旧 prefix | 成品落 `output/APNG/anim24_00001_.png` | 三个保存节点逐个确认前缀 → **F5** → 重跑 |
| 跑了旧工作流 | 同一目录出现旧命名（`anim_base_*`、`anim24_1_*`） | 用 `workflows/workflow-*.json` 或 `emit_workflow.py` 重新生成 |
| 历史 `SaveImage` | `output/` 根目录出现 `anim_base_00001_.png` | 删掉保存节点；文件归档，不再当成品 |
| 旧脚本中间帧 | `anim24_1_00002_.png` 这种带 `_1_` 的 | 历史脚本产物，移到 `archive/frames/` |

判断标准很简单：**成品必须三件同批存在**。缺 WebP 或 GIF 的那张 PNG，只是半次运行或旧前缀的残留。

---

## 4 · 检查与清理

```powershell
# 只检查（默认 dry-run，不动文件）
python scripts/check_output.py --profile profiles/xl.json

# 把 APNG 根目录 / output 根目录的游离文件移进 archive/stray-<时间戳>/
python scripts/check_output.py --profile profiles/xl.json --fix

# 机器可读
python scripts/check_output.py --profile profiles/xl.json --json
```

退出码：`0` 无 FAIL，`1` 有 FAIL，`2` 路径不存在。

检查项：

| 级别 | 含义 |
| --- | --- |
| `FAIL stray_root` | `output/APNG/` 根目录有文件 → 前缀旧值 / 前端没刷新 |
| `FAIL incomplete` | 某一批只有 1–2 种格式 → 保存节点没接同一 batch，或某路报错 |
| `WARN outside_apng` | `output/` 根目录有 `anim*` 残留 → 历史 SaveImage 或旧前缀 |
| `WARN odd_name` | 文件名不符合 `<name>_<5位>.<ext>` → 手动改名或固定名 |
| `INFO vhs_sidecar` | gif 目录的同名 `.png`，VHS 首帧预览，可删 |
| `INFO archive` | 留档文件数量，不参与判定 |

手工清理（先看再动）：

```powershell
$apng = 'D:\ComfyUI-aki-v3.2-xl\ComfyUI\output\APNG'
Get-ChildItem -LiteralPath $apng -File | Select-Object Name, Length, LastWriteTime
# 确认是游离成品后，用脚本归档，不要直接删
python scripts/check_output.py --profile profiles/xl.json --fix
```

---

## 5 · 一次运行后的验收清单

1. `output/APNG/` 根目录**没有文件**。
2. `final/apng`、`final/webp`、`final/gif` 三处出现**同一序号**的三件成品。
3. `gif/` 里的同名 `.png` 是首帧预览，保留或删除都不影响动图。
4. 跑 `check_anim.py`：

```powershell
& 'D:\ComfyUI-aki-v3.2-xl\python\python.exe' scripts\check_anim.py `
  'D:\ComfyUI-aki-v3.2-xl\ComfyUI\output\APNG\final\apng\anim24_00001_.png' --expect 24
```

期望：`frames=24`、`loop=0`、`identical_pairs=0`、`color_drift < 6`。

5. 再跑一次 `check_output.py`，`FAIL 总数: 0`。

---

## 6 · 归档约定

| 目录 | 放什么 | 谁产生 |
| --- | --- | --- |
| `final/` | 三格式成品 | 三个保存节点 |
| `gif/*.png` | VHS 首帧预览 | VHS 插件 |
| `archive/tests/` | 调参试片、对比版本 | 手动 |
| `archive/frames/` | 需要留档的单帧 | 手动（默认不产生） |
| `archive/stray-<时间戳>/` | 游离文件、旧前缀残留 | `check_output.py --fix` |

备份工作流也不要留在 `ComfyUI/user/default/workflows/`。同名 `-v1.json` 会被前端当成第二套工作流；备份放 `archive/`，目录里只留正在用的那一份。

---

## 7 · 仓库里不该出现的东西

仓库和 skill 目录只放**源代码与网页素材**。运行产物一律留在 ComfyUI 的 `output/`：

| 路径 | 该有什么 | 不该有什么 |
| --- | --- | --- |
| `<ComfyUI>/output/APNG/final/` | 三格式成品 | 单帧 PNG、旧前缀残留 |
| 仓库 `docs/assets/` | `preview.webp` / `preview.gif` / `storyboard-*.webp` | 原始 APNG、`_00001_` 成品 |
| 仓库根 | 源码、文档、`workflows/` | 任何 `output/` 的拷贝 |
| `_tmp/` 之类的草稿区 | 一次性脚本、试片 | 长期留存的 PNG / WebP |

脚本自己产出的只有两种，而且都是**网页素材**，不是成品：

- `make_preview.py` → `docs/assets/preview.{webp,gif}`（重编码过的预览）
- `make_storyboard.py` → `docs/assets/storyboard-<name>.webp`（关键拍联系表）

验收：`git status` 除了这两个文件，不该出现任何图片的增删。
