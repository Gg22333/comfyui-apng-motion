# 表情包动作库：怎么把「一个动作」写成可合成的关键帧

这一页解决的是内容问题，不是代码问题：**同一条流水线，为什么有的片像表情包，有的片像卡住的 PPT。**

结论先给：表情包不是「小视频」，是**一个 1–3 秒、首尾能接上的微表演**。
它只需要 2–4 个关键姿势，靠预备动作和停顿把动作读出来，不靠帧数堆。

---

## 1 · 平台规范决定了动作长度

做之前先看发给谁。三家主流平台的实际验收线：

| 平台 | 格式与尺寸 | 时长 / 帧数 | 体积 | 硬性要求 |
| --- | --- | --- | --- | --- |
| Telegram 动态贴纸 | TGS（Lottie）512×512 | ≤ 3 秒，**60fps** | — | 必须循环 |
| Telegram 视频贴纸 | WebM 512×512 | ≤ 3 秒，≤ 30fps | — | 建议循环 |
| LINE 动态贴纸 | **APNG** .png | 5–20 帧，≤ 4 秒，1–4 次循环 | ≤ 1 MB/张 | 第一帧是商店封面；相同帧会被合并 |
| 微信表情 | GIF 240×240 | 单张 ≤ 3 秒（按平台当期规范） | ≤ 500 KB/张 | 一套 16 或 24 张 |
| Discord / 网页 | APNG / WebP | 无硬限制 | 建议 ≤ 2 MB | 首帧兜底、透明优先 WebP |

来源见文末。两个直接推论：

1. **8–24 帧就够**。LINE 上限只有 20 帧；微信 240² 的 GIF 再高帧数也看不出来。
   本项目默认 24 帧 @10fps = 2.4 秒，正好落在 Telegram 的 3 秒线内。
2. **60 帧不是给聊天软件用的**，是给网页、Discord、GitHub 预览、后续转 WebM 用的。
   Telegram 的 60fps 指的是 TGS 矢量动画，不是 60 张位图；位图 60 帧只会让体积翻 2.5 倍。

> 帧数怎么选、各帧数的体积与算力账，见 [用法](usage.md) 的「帧数怎么选」和 [格式对比](formats.md)。

---

## 2 · 五拍语法：表情包的动作都是同一个骨架

把 `actions` 想成舞台提示，不是画面描述。一个能循环的动作只有五拍：

| 拍 | 作用 | 提示词里写什么 | 常见错误 |
| --- | --- | --- | --- |
| K0 静息 | 循环接点，也是聊天列表封面 | 中性表情、正对镜头、嘴闭 | 一上来就是大笑，循环回 K0 会「变脸」 |
| K1 预备 | 反方向蓄力，告诉观众要动了 | 吸气、挑眉、手抬起一半 | 直接跳到主动作，看起来像瞬移 |
| K2 主动作 | 全片最大变化，剪影必须变 | 张嘴、后仰、手举到最高 | 同时改脸、手、身体、背景，插值必糊 |
| K3 余震 | 过冲后回落，给动作重量 | 头回正、手放下、笑收一半 | 直接切回 K0，动作像被剪断 |
| 回到 K0 | 最后一段自动插回第一帧 | 不用写 | 曲线设成 `snap`，末帧冲太快 |

工作流里的对应关系：

```
K0 ──段1──► K1 ──段2──► K2 ──段3──► K3 ──段4──► K0
```

`beats=4` 就是 4 个关键帧、4 段，最后一段自动插回 K0（`emit_workflow.py` 的 `dst = chain[(seg+1) % len(chain)]`）。
所以 **K0 必须是一个能收尾的姿势**，不然循环接点会跳。

### 2.1 四拍怎么分配帧

`frames=24` 的默认分配：

| 拍数 | segs | 节奏感觉 |
| --- | --- | --- |
| 3 | 8 / 8 / 8 | 起 → 一个动作 → 回落，最稳 |
| 4 | 6 / 7 / 6 / 5 | 起 → 预备 → 爆发 → 收，推荐 |
| 5 | 5 / 6 / 5 / 4 / 4 | 有剧情，但 24 帧会赶，建议加到 30/60 |

规律：**预备短、爆发长、收尾中等**。上面 `shock` 用 5/6/7/6，就是让惊吓来得快、停顿留得久。

---

## 3 · 提示词怎么写

一条关键帧提示由三段拼成，顺序固定：

```
lock（不变） + action（这一拍变什么） + style（画风，放最后）
```

`emit_workflow.py` 的 `compile_prompt()` 就是这么拼的。三个理由：

1. **lock 放最前**：脸、发型、服装、构图锚死，插值才不会换人。
2. **action 放中间**：只写这一拍**变化的部分**，不要重复 lock 里已有的内容。
3. **style 放最后**：Moss 的文本编码器对末尾 token 权重最高，风格词放末尾才压得住动作词。

### 3.1 每拍只改一件事

| 想让人物… | 写 | 不要写 |
| --- | --- | --- |
| 笑 | `big smile, eyes half closed` | `laughing, jumping, waving, background changes` |
| 惊讶 | `eyes wide, mouth slightly open` | `turning around, camera zoom` |
| 生气 | `frowning, cheeks puffed` | `whole body shaking, red background` |
| 打招呼 | `raising right hand, palm open` | `walking toward viewer` |

**最多同时改两个部位**（例如「眼 + 嘴」或「手 + 眉」）。改三样以上，中间帧就会互相打架，出现重影和色斑。

### 3.2 全局动作指导写什么

`motion`（工作流里的「全局动作指导」）不是第二个动作，是**全片共享的约束**：

```
same camera, same framing, stable lighting, no zoom, no camera move
```

可以加：`subtle head motion`、`rain falling`、`steam rising`、`warm morning light`。
不要写：`camera pans`、`zoom in`、`character walks`——插值处理不了镜头运动，只会把画面拉花。

留空也可以。留空时工作流会**旁路** `ConditioningCombine`，不稀释每帧提示（1.3.0 起）。

### 3.3 negative 只写会坏事的词

默认 negative 已经包含：`photo, photorealistic, 3d render, collage, grid, multiple girls, different outfit, camera move, zoom, color shift`。
不要往里堆 `ugly, bad`，那会连正常表情一起压掉。

---

## 4 · 动作库（17 组，直接调用）

`assets/motion-presets.json` 是随包的动作库。每组都带：拍数、帧数、段数、fps、denoise、四条动作、全局指导、场景提示。

### 4.1 情绪类

| id | 名称 | 节拍 | 适用 |
| --- | --- | --- | --- |
| `laugh` | 大笑 | 忍笑 → 爆发 → 后仰 → 收 | 聊天里表示笑到不行 |
| `cry` | 大哭 | 委屈 → 泪涌 → 抽泣 → 擦眼 | 求安慰、装可怜 |
| `shock` | 震惊 | 平静 → 瞳孔缩 → 后仰 → 僵住 | 听到离谱消息 |
| `angry` | 生气 | 皱眉 → 鼓脸 → 握拳 → 别头 | 假装生气 |
| `smug` | 得意 | 挑眉 → 斜眼 → 抱臂 → 轻笑 | 「我早就说了」 |
| `sigh` | 无语 | 半睁眼 → 呼气 → 垂肩 → 死鱼眼 | 冷场、无奈 |
| `panic` | 慌张 | 呆住 → 左右看 → 抱头 → 强笑 | 翻车现场 |
| `sleepy` | 困 | 哈欠 → 打盹 → 惊醒 | 早八、加班 |
| `love` | 比心 | 害羞 → 抬手 → 比心 → 收 | 表白、撒娇 |

### 4.2 动作类

| id | 名称 | 节拍 | 适用 |
| --- | --- | --- | --- |
| `wave` | 打招呼 | 抬手 → 挥两下 → 收回 | 开场、打招呼 |
| `nod` | 点头 | 微笑 → 点头 → 再点 → 定住 | 同意、收到 |
| `shake` | 摇头 | 叹气 → 摇头 → 再摇 → 无奈 | 拒绝、不行 |
| `thumbsup` | 点赞 | 抬手 → 竖拇指 → 眨眼 → 收 | 认可、加油 |
| `think` | 思考 | 抬头 → 摸下巴 → 灵光 → 点头 | 「让我想想」 |

### 4.3 五拍小故事

| id | 名称 | 节拍 | 适用 |
| --- | --- | --- | --- |
| `rainy-walk` | 雨天出门 | 看雨 → 撑伞 → 踩水 → 回头 | 60 帧 / 30fps 的完整场景 |
| `morning-coffee` | 早八续命 | 趴桌 → 找咖啡 → 喝 → 满血 → 起身 | 五拍情绪曲线 |

故事类不要求「一个表情」，它演的是**状态变化**：困 → 清醒、平静 → 惊喜。
但结构不变：每一拍仍然只推进一步，最后一拍仍然插回 K0。

### 4.3.1 十一拍全身故事（`moss_zh`）

`diet-betrayal`｜减肥破功｜60 帧 / 30fps / 640×640｜`prompt_mode: moss_zh`｜`segs = 5,5,4,7,6,7,5,6,5,5,5`

| 拍 | 帧 | 动作 |
| --- | --- | --- |
| K0 | 0 | 坐直、双手撑桌沿、抬下巴、面前是沙拉碗 |
| K1 | 5 | 肩膀塌下、双手滑到碗两侧、头微低 |
| K2 | 10 | 双肘撑桌、头低到碗口、嘴角拉直、叉子垂下 |
| K3 | 14 | 头慢慢抬起、转向右边、看向桌旁地板 |
| K4 | 21 | 身体右倾、右手撑桌、左手够地上的手机、冷光打脸 |
| K5 | 27 | 收回手机、坐正、低头看屏、嘴角放松 |
| K6 | 34 | 缩肩、从桌下抱起炸鸡桶、抱在胸前、鼓腮、额角一滴汗 |
| K7 | 39 | 低头看桶、一只手伸进桶里、肩膀放松 |
| K8 | 45 | 后靠椅背、举鸡腿到嘴边、眼睛闭成两道弯、嘴角上扬 |
| K9 | 50 | 放下炸鸡、手垂桌面、整个人松下来 |
| K10 | 55 | 坐直、推走空桶、双手扶住白碗、握拳、眼角有泪光 |
| 收尾 | 55→59 | 用 5 帧插回 K0，循环接回封面 |

```bash
python scripts/make_story.py --preset diet-betrayal --out assets/story.diet.json
python scripts/emit_workflow.py --base workflows/workflow-moss.json \
    --story assets/story.diet.json --size 640 --out my-60.json
```

这一组的关键约束：

- **每拍只推进一步**。11 拍不是为了凑数，是为了把“趴桌→够手机”“看屏→抱桶”这种大跨度的动作
  拆成两个小跨度；单段跨太大时，插值会糊成叠影。
- **大动作多给帧**。`segs` 里 K3→K4 和 K5→K6 各 7 帧，只动肩/头的段 4–5 帧。判断标准是两端姿态差，
  不是动作名称长短。
- **每个动作都以「矮木桌前，」开头**。场景锚点放在句首，模型更不容易把桌子、白碗画丢；
  背景只留墙面、台灯、矮桌，减少每拍重绘的自由度。
- **下半身全程固定在矮桌后面**。腿的位置一变，latent 插值就会出现「双重腿」残影。
- **关键帧 denoise 0.85（范围 0.82–0.90）**。MOSS 是 8 步 DMD 蒸馏模型，低于 0.80 关键帧几乎不动
  （实测整片相邻帧差 0.03）；动作幅度靠提示词和分帧，不靠继续抬 denoise。
- **`motion` 留空**。写「不要推镜头 / 不要换角度」这类否定句，模型会理解成「保持原样」，
  把本帧动作一起压掉。
- 提示词用中文散文，每段以「。」结尾；`prompt_mode` 设成 `moss_zh`。

### 4.4 动作词汇表（直接粘进 `actions`）

热门表情包的动作高度套路化，翻来覆去就是下面这些。用法：**每拍取「1 个动作短语 + 1 个表情短语」**，
不要整句照抄，也不要一拍拍全用。

| 类别 | 可直接用的英文短语 |
| --- | --- |
| 问候 / 告别 | `wave hello` · `salute` · `bow` · `peace sign` · `blowing a kiss` · `goodbye wave` |
| 肯定 / 同意 | `nod` · `thumbs up` · `OK sign` · `clapping` · `fist pump` · `arms crossed with a nod` |
| 否定 / 拒绝 | `shake head` · `palm out` · `cross arms` · `turn away` · `shrug` · `push away` |
| 情绪爆发 | `laughing hard` · `crying` · `screaming` · `gasping` · `jaw dropped` · `rage` · `pouting` · `sulking` |
| 日常状态 | `yawning` · `sleepy` · `eating` · `drinking` · `working` · `studying` · `gaming` · `scrolling phone` |
| 亲密 / 撒娇 | `heart hands` · `hug` · `headpat` · `blushing` · `shy look` · `wink` · `leaning on shoulder` |
| 搞笑 / 梗 | `facepalm` · `sweat drop` · `anger vein` · `blank stare` · `side-eye` · `smirk` · `dizzy swirls` |
| 节奏 / 身体 | `bounce` · `sway` · `tilt head` · `lean back` · `lean forward` · `recoil` · `freeze` · `tremble` |

三条硬规则：

1. **表情包的动作是符号，不是解剖**。写 `sweat drop`、`anger vein`、`blank stare` 比写「眉头下压 3 毫米」有效。
2. **一个 beat 只取一个动作短语**。`waving, jumping, winking` 三条一起写，插值只会糊。
3. **动作词放 action，镜头词放 motion**。`close-up`、`from above` 不属于动作，写了会换构图。

---

## 5 · 用法

列出全部动作：

```bash
python scripts/make_story.py --list
```

用动作库生成剧情卡，再交给 `emit_workflow.py`：

```bash
python scripts/make_story.py \
  --preset laugh \
  --lock "masterpiece, best quality, 1girl, solo, upper body, silver hair, blue eyes, school uniform, simple background" \
  --name my-laugh \
  --out assets/story.my-laugh.json

python scripts/emit_workflow.py \
  --base workflows/workflow-sdxl.json \
  --story assets/story.my-laugh.json \
  --out my-laugh.json \
  --run
```

改帧数 / 帧率 / 段数：

```bash
# 12 帧轻量版（LINE 风格）
python scripts/make_story.py --preset wave --lock "..." --frames 12 --fps 12 --out story.wave12.json

# 五拍故事拉到 60 帧
python scripts/make_story.py --preset rainy-walk --lock "..." --frames 60 --fps 30 --out story.rain60.json

# 手动分配段数（必须满足 sum(segs) == frames）
python scripts/make_story.py --preset shock --lock "..." --frames 24 --segs 4,6,8,6 --out story.shock.json
```

`make_story.py` 会校验：

- `frames >= beats`；
- `segs` 段数 = 拍数；
- `sum(segs) == frames`；
- 每拍动作数与拍数一致。

场景类动作（`rainy-walk`、`morning-coffee`）会自动把 `lock_hint` 追加到 `lock` 后面；不想要就加 `--no-hint`。

---

## 6 · 按平台改参数

| 目标 | frames | fps | 额外动作 |
| --- | --- | --- | --- |
| Telegram 动态贴纸 | 24–60 | 30（导出后转 TGS/WebM） | 512×512，≤3 秒 |
| LINE 动态贴纸 | 8–20 | 8–10 | 缩到 370×320 内，压到 ≤1 MB |
| 微信表情 | 24 | 10 | 缩到 240×240，GIF ≤500 KB |
| Discord / 网页 | 24–60 | 15–30 | 优先 WebP，透明背景 |
| GitHub 预览 | 24–60 | 15–30 | 384²，见 `make_preview.py` |

体积换算：60 帧约为 24 帧的 2.5 倍；WebP q90 约为 APNG 的 1/7。详见 [格式对比](formats.md)。

---

## 7 · 七个常见错误

| 症状 | 原因 | 修法 |
| --- | --- | --- |
| 循环接点「变脸」 | K0 不是静息姿势，或末拍没回 K0 | `actions[0]` 写中性；用四拍模板 |
| 中间帧重影 / 色斑 | 一拍里改了三个以上部位 | 每拍只改 1–2 个部位；denoise 降到 0.4 |
| 手部糊成一团 | 手部大幅动作 + 低帧数 | 手部动作给 0.5 denoise；裁到上半身 |
| 画面被拉花 | `motion` 里写了 camera move / zoom | 只写 `same camera, same framing` |
| 风格被动作词吃掉 | style 写在 action 前面 | 固定顺序 `lock + action + style` |
| 排了 24 帧只剩 19 帧 | 同一对 latent 上 ratio 重复 | 用 `make_curve.py`，别手填重复值 |
| GIF 有色块闪 | 逐帧调色板 + 抖动 | 用 `make_preview.py` 的全局调色板 + `dither=NONE` |

---

## 8 · 参考

- Telegram Stickers（512×512、≤3 秒、必须循环、60fps）：<https://core.telegram.org/stickers>
- LINE Creators Market · Animated Stickers（APNG、5–20 帧、≤4 秒、≤1 MB、首帧为封面）：
  <https://creator.line.me/en/guideline/animationsticker/>
- 微信表情开放平台投稿指南（GIF 240×240、≤500 KB、16 或 24 张一套）：<https://sticker.weixin.qq.com/>
- APNG 规范与 GIF89a 延迟单位：见 [格式对比](formats.md) 的参考一节