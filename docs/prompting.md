# 提示词写法

这是全仓唯一一份提示词规范。其它页面只写摘要并链到这里，不再各写一套。

先回答一个问题：**你的模型用哪个文本编码器？** 写法由它决定，不由模型名决定。

| 文本编码器 | 谁在用 | 方言 | 一句话记法 |
| --- | --- | --- | --- |
| CLIP | SD 1.5、SDXL、Illustrious、NoobAI、Pony | [标签](#a--clip) | 逗号堆词，画风放最后 |
| Qwen-VL 系 | MOSS-Image、Krea 2、Qwen-Image、Anima | [散文](#b--qwen-vl) | 中文分段，每段句号结尾 |
| T5 | FLUX.1、SD3 / SD3.5 | [句子](#c--t5) | 完整英文句子，不用权重括号 |

认不出来就看加载器：`CheckpointLoaderSimple` 基本是 CLIP；`UNETLoader` + `CLIPLoader` 看 `type` 参数；
`DualCLIPLoader` 带 `t5xxl` 的就是 T5 路线。详见 [模型与架构](models.md)。

## A · CLIP

### 骨架

```
主体与外观, 场景与光线, 〈这一拍的动作〉, 画风
```

### 规则

1. **英文逗号分隔**，重要标签往前放。前 20 个 token 权重最高。
2. **画风放最后**：`anime screencap, clean lineart, flat cel shading`。
3. **写画面，不写效果**。`shocked` 是效果，`eyes wide, pupils small, mouth open` 是画面。
4. **一个标签一件事**，不要写句子。`a girl sitting on a chair` 不如 `1girl, sitting, chair`。
5. **负向单独一个 `CLIPTextEncode`**，不要混进正向。

### 例

```
1girl, solo, full body, black short hair, blue eyes, beige hoodie, dark shorts,
barefoot, bedroom at night, warm lamp light, sitting behind a low wooden table,
hands on the table edge, chin up, mouth corner slightly raised,
anime screencap, clean lineart, flat cel shading
```

### 关键帧之间只改一个变量

十一拍故事里，除了动作那一段，其余每个字都不变。改两个变量，插值出来就是两张不同的脸。

## B · Qwen-VL

MOSS-Image、Krea 2、Qwen-Image、Anima 用的是 Qwen 系多模态编码器。它读**语义**，不读逗号权重。

### 骨架

四段，换行分隔，每段以「。」结尾：

```
〈场景 + 光线 + 机位〉。
〈人物外观 + 服装 + 位置〉。
〈这一拍的动作，写到身体部位〉。
〈画风〉。
```

### 规则

1. **不堆 quality tag**。`masterpiece, best quality, 8k` 对它是噪声，会把画面拉回通用图库风。
2. **用可测量的身体描述代替形容词**：

   | 想表达 | 写什么 |
   | --- | --- |
   | 震惊 | 双眼睁大、瞳孔缩小、嘴张开 |
   | 疲惫嫌弃 | 眼半闭、瞳孔偏低、唇压成直线 |
   | 得意 | 下巴抬起、嘴角单侧上翘、眼睛半眯 |
   | 心虚 | 眼神躲开镜头、肩膀缩起、额角一滴汗 |

3. **构图写死**：`固定机位，平视，全身镜头，人物从头到脚完整入画，双手和双脚都留在画框里`。
   不写这句，模型会自作主张切半身，动作就白演了。
4. **负向也用中文**，单独一个 `CLIPTextEncode`。
5. **`motion` 留空**。填了会经 `ConditioningCombine` 稀释每一拍的提示（1.3.0 起留空自动旁路）。

### 例

```
一间安静的小房间，浅米色墙面，画面右侧有一盏暖色台灯，光从右前方斜照下来，落在木地板上。画面中间是一张矮木桌，桌上放着一只白碗。固定机位，平视，全身镜头，人物从头到脚完整入画。
小满：一个年轻女孩，黑色短发，蓝色眼睛，身材微胖，穿着宽松的米色连帽卫衣和深色短裤，赤脚。始终坐在矮桌后面，膝盖收在桌子下面，双脚踩在地板上，坐的位置和朝向整段不变。
矮木桌前，小满坐得很直，双手撑在桌沿，抬起下巴，嘴角只上扬几毫米，面前的白碗里是绿色的沙拉。
动漫赛璐璐风格，干净黑色线稿，平涂上色，暖色调，柔和阴影，边缘柔和，画面干净没有噪点。
```

负向：

```
最差画质，低画质，低分辨率，压缩噪点，模糊，错误的人体结构，畸形的手，多余的手指，水印，文字，签名，特写，半身像，裁掉腿，人物出画，镜头移动，变焦，多个人物，拼贴，分屏，服装变化，发色变化，瞳色变化，色块，色带，照片质感，三维渲染
```

## C · T5

FLUX.1 与 SD3 的 T5 分支读自然语言。

### 规则

1. **完整英文句子**，一段话讲清画面。
2. **不用 `(word:1.3)` 权重括号**，T5 基本不吃这套。
3. **一句话一件事**：主体、动作、环境、光线、镜头、材质，别在一个从句里塞三件事。
4. **可以长，但不要堆同义词**。堆 `beautiful, gorgeous, stunning` 只会让画面变糊。
5. FLUX 走 `FluxGuidance` 3.5 / `cfg` 1.0；SD3 用 `cfg` 4–7。

### 例

```
A young woman with short black hair and blue eyes sits upright behind a low wooden table in a
small bedroom at night. She wears an oversized beige hoodie and dark shorts, barefoot, knees
tucked under the table. A warm desk lamp on the right casts soft light across the wooden floor.
She rests both hands on the table edge, lifts her chin slightly, and the corner of her mouth
rises by a few millimetres. Anime cel-shaded style, clean black lineart, flat colour, soft shading.
```

## 画面里要出现文字时

需要海报、招牌、对话框里的字时，不要指望提示词自动排版。用 Layout：

- 位置用**绝对像素 bbox** `[x0, y0, x1, y1]`，从画布左上角量，不要用 0–1 归一化坐标。
- 画布宽高必须是 **16 的倍数**（MOSS-Image 的硬性要求）。
- `text` 字段写**要显示的原文**，不要写 `headline here` 这类占位符。
- 只描述看得见的东西；`怎么生成`、`第几步做什么` 这类工具指令不要写进画面描述。
- 不要从参考图里搬名字、水印、标语。

参考工具：`moss-image-prompt-enhancer`（本地 skill），把草稿 JSON 编译成可粘贴的 prompt。

## 逐拍三段式

剧情卡写成三段，插值才不会打架：

| 段 | 内容 | 改不改 |
| --- | --- | --- |
| `lock` | 场景 + 光线 + 机位 + 人物外观 + 固定姿势 | 全片一个字都不改 |
| `actions[i]` | 第 i 拍唯一的变量 | 每拍只改一处 |
| `style` | 画风 | 全片统一 |
| `negative` | 负向 | 全片统一 |

判断某一拍写得对不对，就问一句：**把这一拍单独拿去文生图，出来的是不是同一个人、同一个房间？**
不是的话，`lock` 里缺东西，不是 `action` 写太少。

## 常见翻车

| 现象 | 原因 | 改法 |
| --- | --- | --- |
| 每拍换脸 | `lock` 里没锁死发色 / 瞳色 / 服装 | 把这三样写进 `lock`，`action` 里不要重复描述外观 |
| 只动嘴，身体不动 | 构图被切成半身 | 加「全身镜头、从头到脚完整入画」，或降低 `denoise` |
| 画面出现补丁状色斑 | 关键帧 `denoise` 太高，无关区域被重绘 | UNet 降到 0.35–0.40；MOSS 保持 0.82–0.90 但别超 0.90 |
| 整片几乎不动 | `denoise` 太低 | 先加大 A/B 两拍的提示差异，再加 `denoise` |
| 堆了 `masterpiece` 反而更差 | Qwen-VL 把 quality tag 当噪声 | 全删，改写字面描述 |
| 文字乱码 / 位置错 | 没给 bbox，或坐标用了归一化 | 用绝对像素 bbox，宽高取 16 的倍数 |

## 下一步

- 想直接抄一份完整的十一拍范例：`assets/story.diet.json`
- 想换模型：先看 [模型与架构](models.md)，再回来挑方言
- 想调节奏：看 [工作流 · 节奏](workflows.md#节奏fps-与每拍停留)