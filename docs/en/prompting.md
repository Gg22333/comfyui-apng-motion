# Prompting

This is the single source of truth for prompt writing in this repo. Every other page summarises and
links here instead of repeating its own version.

Answer one question first: **which text encoder does your model use?** That decides the dialect, not
the model name.

| Text encoder | Who uses it | Dialect | Remember it as |
| --- | --- | --- | --- |
| CLIP | SD 1.5, SDXL, Illustrious, NoobAI, Pony | [tags](#a--clip) | comma-separated tags, style last |
| Qwen-VL family | MOSS-Image, Krea 2, Qwen-Image, Anima | [prose](#b--qwen-vl) | paragraphs, one full stop each |
| T5 | FLUX.1, SD3 / SD3.5 | [sentences](#c--t5) | full English sentences, no weight syntax |

If you cannot tell, look at the loader: `CheckpointLoaderSimple` is almost always CLIP; with
`UNETLoader` + `CLIPLoader`, check the `type` widget; `DualCLIPLoader` with `t5xxl` is the T5 route.
See [Models and architectures](models.md).

## A · CLIP

### Skeleton

```
subject and appearance, scene and light, <this beat's action>, style
```

### Rules

1. **English, comma-separated**, most important tags first. The first 20 tokens carry the most weight.
2. **Style last**: `anime screencap, clean lineart, flat cel shading`.
3. **Describe the picture, not the effect.** `shocked` is an effect; `eyes wide, pupils small, mouth
   open` is a picture.
4. **One tag, one thing.** `a girl sitting on a chair` loses to `1girl, sitting, chair`.
5. **Negative goes in its own `CLIPTextEncode`**, never mixed into the positive.

### Example

```
1girl, solo, full body, black short hair, blue eyes, beige hoodie, dark shorts,
barefoot, bedroom at night, warm lamp light, sitting behind a low wooden table,
hands on the table edge, chin up, mouth corner slightly raised,
anime screencap, clean lineart, flat cel shading
```

### Change exactly one variable between keyframes

In an eleven-beat story, every word outside the action paragraph stays identical. Change two variables
and the interpolation gives you two different people.

## B · Qwen-VL

MOSS-Image, Krea 2, Qwen-Image and Anima use Qwen-family multimodal encoders. They read **meaning**,
not comma weights.

### Skeleton

Four paragraphs, newline-separated, each ending with a full stop:

```
<scene + light + camera>.
<subject appearance + clothing + position>.
<this beat's action, down to body parts>.
<style>.
```

### Rules

1. **No quality tags.** `masterpiece, best quality, 8k` is noise to it and pulls the image back toward
   generic stock output.
2. **Measure the body instead of naming the emotion:**

   | Intent | Write this |
   | --- | --- |
   | Shocked | eyes wide open, pupils small, mouth open |
   | Tired disgust | eyes half closed, gaze low, lips pressed into a line |
   | Smug | chin lifted, one mouth corner raised, eyes narrowed |
   | Guilty | gaze away from the lens, shoulders drawn in, a bead of sweat at the temple |

3. **Nail the framing**: `fixed camera, eye level, full-body shot, head to toe inside the frame, both
   hands and both feet visible`. Omit it and the model crops to half body, and the performance is lost.
4. **Negative in Chinese too**, in its own `CLIPTextEncode`.
5. **Leave `motion` empty.** A filled `motion` goes through `ConditioningCombine` and dilutes every
   keyframe prompt (empty is auto-bypassed since 1.3.0).

### Example

```
A quiet small bedroom with pale beige walls. A warm desk lamp on the right throws light down across
the wooden floor. A low wooden table sits in the middle with a white bowl on it. Fixed camera, eye
level, full-body shot, head to toe inside the frame.
Xiaoman: a young woman with short black hair and blue eyes, slightly round build, oversized beige
hoodie, dark shorts, barefoot. She stays seated behind the table, knees under it, feet on the floor,
position and facing unchanged for the whole clip.
At the low table, Xiaoman sits up very straight, both hands on the table edge, chin lifted, the corner
of her mouth raised by a few millimetres, a green salad in the white bowl in front of her.
Anime cel-shaded style, clean black lineart, flat colour, warm palette, soft shading, clean frame.
```

Negative:

```
worst quality, low quality, low resolution, compression noise, blur, bad anatomy, deformed hands,
extra fingers, extra limbs, watermark, text, signature, close-up, half body, cropped legs, subject out
of frame, camera movement, zoom, multiple people, collage, split screen, clothing change, hair colour
change, eye colour change, colour blocks, banding, photographic, 3D render
```

## C · T5

The T5 branch of FLUX.1 and SD3 reads natural language.

### Rules

1. **Complete English sentences**, one paragraph describing the frame.
2. **No `(word:1.3)` weighting**; T5 largely ignores it.
3. **One idea per sentence**: subject, action, environment, light, lens, material — not three clauses
   in one breath.
4. **Long is fine, synonyms are not.** `beautiful, gorgeous, stunning` just muddies the image.
5. FLUX runs `FluxGuidance` 3.5 at `cfg` 1.0; SD3 uses `cfg` 4–7.

### Example

```
A young woman with short black hair and blue eyes sits upright behind a low wooden table in a
small bedroom at night. She wears an oversized beige hoodie and dark shorts, barefoot, knees
tucked under the table. A warm desk lamp on the right casts soft light across the wooden floor.
She rests both hands on the table edge, lifts her chin slightly, and the corner of her mouth
rises by a few millimetres. Anime cel-shaded style, clean black lineart, flat colour, soft shading.
```

## When text must appear in the frame

Do not expect a prompt to typeset a poster or a sign. Use Layout:

- Positions are **absolute pixel bboxes** `[x0, y0, x1, y1]`, measured from the canvas top-left — not
  0–1 normalised coordinates.
- Canvas width and height must be **multiples of 16** (a hard MOSS-Image requirement).
- The `text` field holds **the literal string to render**, never a placeholder like `headline here`.
- Describe only what is visible; keep tool instructions such as "step three: draw the border" out of
  the image description.
- Do not import names, watermarks or slogans from a reference image.

Reference tool: the `moss-image-prompt-enhancer` skill compiles a draft JSON into a pasteable prompt.

## Three-part beat structure

Write story cards in three parts so interpolation does not fight itself:

| Part | Contents | Changes? |
| --- | --- | --- |
| `lock` | scene + light + camera + appearance + fixed pose | not a single character, ever |
| `actions[i]` | the one variable of beat i | one change per beat |
| `style` | art style | constant for the clip |
| `negative` | negatives | constant for the clip |

The test for any beat: **if you render this beat alone, is it the same person in the same room?**
If not, `lock` is missing something — it is not that `action` is too short.

## Common failures

| Symptom | Cause | Fix |
| --- | --- | --- |
| A different face every beat | `lock` does not pin hair, eyes and clothing | put all three in `lock`; do not repeat appearance in `action` |
| Only the mouth moves, body frozen | framing collapsed to half body | add "full-body, head to toe inside the frame", or lower `denoise` |
| Patchy colour blotches | keyframe `denoise` too high, unrelated regions redrawn | UNet 0.35–0.40; MOSS 0.82–0.90 but not above 0.90 |
| The whole clip barely moves | `denoise` too low | widen the prompt difference between beats first, then raise `denoise` |
| `masterpiece` makes it worse | Qwen-VL treats quality tags as noise | delete them, describe literally |
| Garbled text or wrong placement | no bbox, or normalised coordinates | absolute pixel bbox, 16-multiple canvas |

## Next

- Copy a complete eleven-beat example: `assets/story.diet.json`
- Swapping models: read [Models and architectures](models.md) first, then pick a dialect
- Adjusting pacing: see [Workflows · Pace](workflows.md#pace-fps-and-per-beat-dwell)