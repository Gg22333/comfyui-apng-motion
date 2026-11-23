# Motion library: turning one action into composable keyframes

This page is about content, not code: **why the same pipeline produces a sticker in one run and a frozen slideshow in another.**

Short answer: a sticker is not a tiny video. It is a **1–3 second micro-performance whose first and last pose connect**.
It needs 2–4 key poses, anticipation and a hold — not more frames.

---

## 1 · Platform specs decide the length

Check the destination before you render:

| Platform | Format and size | Duration / frames | Size cap | Hard requirement |
| --- | --- | --- | --- | --- |
| Telegram animated sticker | TGS (Lottie) 512×512 | ≤ 3 s, **60 fps** | — | must loop |
| Telegram video sticker | WebM 512×512 | ≤ 3 s, ≤ 30 fps | — | loop recommended |
| LINE animated sticker | **APNG** `.png` | 5–20 frames, ≤ 4 s, 1–4 loops | ≤ 1 MB each | frame 1 is the shop cover; identical frames get merged |
| WeChat sticker | GIF 240×240 | ≤ 3 s per sticker | ≤ 500 KB each | sets of 16 or 24 |
| Discord / web | APNG / WebP | no hard limit | ≤ 2 MB recommended | still-image fallback, alpha preferred |

Sources at the end. Two consequences:

1. **8–24 frames is enough.** LINE caps at 20 frames; a 240² WeChat GIF gains nothing from more.
   The project default, 24 frames @10 fps = 2.4 s, sits inside Telegram's 3 s line.
2. **60 frames is for the web**, Discord, GitHub previews and later WebM export — not for chat stickers.
   Telegram's 60 fps refers to vector TGS, not 60 bitmap frames; 60 bitmaps only multiply file size by ~2.5.

> Frame-count trade-offs and size/sampling math: [Usage](usage.md) and [Formats](formats.md).

---

## 2 · The five-beat grammar

Treat `actions` as stage directions, not image descriptions. A loopable action has five beats:

| Beat | Role | What to write | Common mistake |
| --- | --- | --- | --- |
| K0 rest | loop seam and chat-list cover | neutral face, facing viewer, mouth closed | starting at peak laugh, so the loop "changes face" |
| K1 anticipation | wind-up in the opposite direction | inhale, eyebrow lift, hand half raised | jumping straight to the action; reads as a teleport |
| K2 action | largest change; silhouette must change | mouth open, lean back, hand at peak | changing face, hands, body and background at once |
| K3 settle | overshoot and fall back | head recentres, hand lowers, smile softens | cutting straight to K0; the action looks clipped |
| back to K0 | final segment interpolates home | nothing to write | using `snap`, so the last frames rush |

Workflow mapping:

```
K0 ──seg1──► K1 ──seg2──► K2 ──seg3──► K3 ──seg4──► K0
```

`beats=4` means 4 keyframes and 4 segments; the last segment wraps to K0 (`dst = chain[(seg+1) % len(chain)]`).
So **K0 must be a pose that can end the clip**, or the seam jumps.

### 2.1 Segment budgets at 24 frames

| Beats | segs | Feel |
| --- | --- | --- |
| 3 | 8 / 8 / 8 | rest → one action → settle; safest |
| 4 | 6 / 7 / 6 / 5 | rest → wind-up → burst → settle; recommended |
| 5 | 5 / 6 / 5 / 4 / 4 | story-shaped, but crowded at 24; use 30/60 |

Rule: **short anticipation, long burst, medium settle.** `shock` uses 5/6/7/6 so the scare lands fast and holds.

---

## 3 · How to write the prompt

A keyframe prompt is assembled in a fixed order:

```
lock (constant) + action (what changes this beat) + style (look, last)
```

That is exactly what `compile_prompt()` does. Why:

1. **lock first** pins face, hair, outfit and framing; interpolation cannot swap the character.
2. **action in the middle** describes only the delta; do not repeat the lock.
3. **style last** because Moss's text encoder weights trailing tokens most; style at the end survives action words.

### 3.1 Change one thing per beat

| Goal | Write | Avoid |
| --- | --- | --- |
| laugh | `big smile, eyes half closed` | `laughing, jumping, waving, background changes` |
| shock | `eyes wide, mouth slightly open` | `turning around, camera zoom` |
| angry | `frowning, cheeks puffed` | `whole body shaking, red background` |
| wave | `raising right hand, palm open` | `walking toward viewer` |

**At most two body parts per beat** (eyes + mouth, or hand + brow). Three or more fight each other and produce ghosts and colour blotches in the in-betweens.

### 3.2 What goes into the global motion layer

`motion` (the "全局动作指导" node) is not a second action; it is a **shared constraint**:

```
same camera, same framing, stable lighting, no zoom, no camera move
```

You may add `subtle head motion`, `rain falling`, `steam rising`, `warm morning light`.
Do not write `camera pans`, `zoom in`, `character walks` — interpolation cannot handle camera motion and will smear the frame.

Leaving it empty is fine: the workflow bypasses `ConditioningCombine` so the per-frame prompt is not diluted (since 1.3.0).

### 3.3 Keep negatives narrow

The default negative already covers `photo, photorealistic, 3d render, collage, grid, multiple girls, different outfit, camera move, zoom, color shift`.
Do not pile on `ugly, bad`; that suppresses ordinary expressions too.

---

## 4 · The library (17 presets)

`assets/motion-presets.json` ships with the repo. Each preset carries beats, frames, segments, fps, denoise, four actions, a motion layer and a scene hint.

### 4.1 Emotions

| id | Name | Beats | Use |
| --- | --- | --- | --- |
| `laugh` | Laugh | hold back → burst → lean back → settle | laughing hard |
| `cry` | Cry | pout → tears → sob → wipe | comfort me |
| `shock` | Shock | calm → pupils shrink → lean back → freeze | outrageous news |
| `angry` | Angry | frown → puff cheeks → fists → turn away | fake anger |
| `smug` | Smug | brow raise → side-eye → arms crossed → chuckle | "told you so" |
| `sigh` | Sigh | half-lidded → exhale → shoulders drop → deadpan | dead air |
| `panic` | Panic | blank → look around → hands on cheeks → forced smile | everything is on fire |
| `sleepy` | Sleepy | yawn → doze → jolt awake | early shift |
| `love` | Heart hands | shy → raise hands → heart → hold | affection |

### 4.2 Gestures

| id | Name | Beats | Use |
| --- | --- | --- | --- |
| `wave` | Wave | raise → wave → lower | greeting |
| `nod` | Nod | smile → nod → nod again → settle | agreed |
| `shake` | Shake | sigh → shake → shake again → resigned | nope |
| `thumbsup` | Thumbs up | raise → thumb → wink → lower | approval |
| `think` | Think | look up → chin → idea → nod | let me think |

### 4.3 Five-beat stories

| id | Name | Beats | Use |
| --- | --- | --- | --- |
| `rainy-walk` | Rainy walk | notice rain → umbrella → puddle → look back | 60 frames / 30 fps scene |
| `morning-coffee` | Morning coffee | desk → find coffee → drink → refreshed → stand | five-beat emotional curve |

Stories are not "one expression"; they act out a **state change**: sleepy → awake, calm → delighted.
The structure is unchanged: one step per beat, and the last segment still interpolates back to K0.

### 4.3.1 Eleven-beat full-body story (`moss_zh`)

`diet-betrayal` · Diet Betrayal · 60 frames / 30 fps / 640×640 · `prompt_mode: moss_zh` · `segs = 5,5,4,7,6,7,5,6,5,5,5`

| Beat | Frame | Action |
| --- | --- | --- |
| K0 | 0 | sits straight, hands on the table edge, chin up, salad bowl in front |
| K1 | 5 | shoulders drop, hands slide to the sides of the bowl, head lowers |
| K2 | 10 | elbows on the table, head down to the bowl, flat mouth, fork hanging |
| K3 | 14 | head lifts slowly, turns right, eyes toward the floor beside the table |
| K4 | 21 | leans right, right hand on the table, left hand reaches for the phone, cold screen light |
| K5 | 27 | pulls the phone back, sits up, stares at the screen, mouth relaxes |
| K6 | 34 | shoulders shrink, lifts a fried-chicken bucket from under the table, hugs it, puffed cheeks |
| K7 | 39 | looks into the bucket, one hand inside it, shoulders relax |
| K8 | 45 | leans back, drumstick to the mouth, eyes closed in crescents, small smile |
| K9 | 50 | puts the chicken down, hands on the table, whole body relaxes |
| K10 | 55 | sits up, pushes the empty bucket away, holds the bowl, fist raised, tears at the eye corners |
| loop | 55→59 | 5 frames interpolate back to K0 so the loop meets the cover |

```bash
python scripts/make_story.py --preset diet-betrayal --out assets/story.diet.json
python scripts/emit_workflow.py --base workflows/workflow-moss.json \
    --story assets/story.diet.json --size 640 --out my-60.json
```

Constraints that matter for this preset:

- **One step per beat.** Eleven beats are not padding: they split "face down on the table → reach for the
  phone" and "look at the screen → lift the bucket" into two smaller moves. A single segment with that
  much pose distance interpolates into a ghost.
- **Big moves get more frames.** K3→K4 and K5→K6 get 7 frames each in `segs`; shoulder/head beats get 4–5.
  Judge by the pose distance at the two ends, not by how long the sentence is.
- **Start every action with 「矮木桌前，」 (at the low table).** A scene anchor at the front of the sentence
  makes it much harder for the model to drop the table and the bowl. The background is reduced to wall,
  lamp and table so each redraw has less freedom.
- **Lower body stays behind the table.** Move the legs and latent interpolation produces double legs.
- **Keyframe denoise 0.85 (range 0.82–0.90).** Moss is an 8-step DMD distilled model; below 0.80 the
  keyframes barely move (measured whole-film adjacent diff 0.03). Get the motion from the prompt and the
  frame budget, not from pushing denoise further.
- **Leave `motion` empty.** A negation such as "do not move the camera" is read as "keep everything as is"
  and suppresses the beat's action too.
- Chinese prose, one idea per paragraph, every paragraph ends with 「。」; `prompt_mode: moss_zh`.

### 4.4 Action vocabulary (paste into `actions`)

Popular sticker packs reuse a small vocabulary. Use **one action phrase + one expression phrase per beat**;
do not copy a whole list into every beat.

| Category | Ready-to-use phrases |
| --- | --- |
| Greeting / farewell | `wave hello` · `salute` · `bow` · `peace sign` · `blowing a kiss` · `goodbye wave` |
| Yes / approval | `nod` · `thumbs up` · `OK sign` · `clapping` · `fist pump` · `arms crossed with a nod` |
| No / refusal | `shake head` · `palm out` · `cross arms` · `turn away` · `shrug` · `push away` |
| Emotional burst | `laughing hard` · `crying` · `screaming` · `gasping` · `jaw dropped` · `rage` · `pouting` · `sulking` |
| Daily state | `yawning` · `sleepy` · `eating` · `drinking` · `working` · `studying` · `gaming` · `scrolling phone` |
| Affection | `heart hands` · `hug` · `headpat` · `blushing` · `shy look` · `wink` · `leaning on shoulder` |
| Comedy / meme | `facepalm` · `sweat drop` · `anger vein` · `blank stare` · `side-eye` · `smirk` · `dizzy swirls` |
| Rhythm / body | `bounce` · `sway` · `tilt head` · `lean back` · `lean forward` · `recoil` · `freeze` · `tremble` |

Three hard rules:

1. **Sticker motion is symbolic, not anatomical.** `sweat drop`, `anger vein`, `blank stare` work better than millimetre-level brow descriptions.
2. **One action phrase per beat.** `waving, jumping, winking` together only produces mush after interpolation.
3. **Action words go in action; camera words go in motion.** `close-up` and `from above` are framing changes, not actions.

---

## 5 · Usage

List presets:

```bash
python scripts/make_story.py --list
```

Build a story card, then hand it to `emit_workflow.py`:

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

Override frames, fps or segment budgets:

```bash
python scripts/make_story.py --preset wave --lock "..." --frames 12 --fps 12 --out story.wave12.json
python scripts/make_story.py --preset rainy-walk --lock "..." --frames 60 --fps 30 --out story.rain60.json
python scripts/make_story.py --preset shock --lock "..." --frames 24 --segs 4,6,8,6 --out story.shock.json
```

`make_story.py` validates `frames >= beats`, `len(segs) == beats`, `sum(segs) == frames`, and that every preset has one action per beat.
Scene presets append their `lock_hint` to your lock; pass `--no-hint` to suppress it.

---

## 6 · Per-platform settings

| Target | frames | fps | Extra steps |
| --- | --- | --- | --- |
| Telegram animated sticker | 24–60 | 30 (then convert to TGS/WebM) | 512×512, ≤ 3 s |
| LINE animated sticker | 8–20 | 8–10 | fit within 370×320, compress to ≤ 1 MB |
| WeChat sticker | 24 | 10 | 240×240, GIF ≤ 500 KB |
| Discord / web | 24–60 | 15–30 | WebP preferred, transparent |
| GitHub preview | 24–60 | 15–30 | 384², see `make_preview.py` |

Size rules of thumb: for the same content, 60 frames ≈ 2.5× the 24-frame clip; WebP q90 ≈ 1/7 of APNG. See [Formats](formats.md).

---

## 7 · Seven common failures

| Symptom | Cause | Fix |
| --- | --- | --- |
| loop seam "changes face" | K0 is not a rest pose, or the last beat does not return | put a neutral pose in `actions[0]`; use the 4-beat template |
| ghosting / blotches in between | three or more body parts changed in one beat | change 1–2 parts; drop denoise to 0.4 |
| hands melt | large hand motion at low frame count | give hand beats more frames; crop to upper body |
| frame smears | `motion` contains camera move / zoom | keep `same camera, same framing` |
| style eaten by action words | style before action | keep `lock + action + style` |
| 24 frames exported as 19 | duplicate ratios on the same latent pair | use `make_curve.py`; never hand-write duplicates |
| GIF colour blocks flicker | per-frame palette plus dithering | use `make_preview.py`'s global palette and `dither=NONE` |

---

## 8 · References

- Telegram Stickers (512×512, ≤ 3 s, must loop, 60 fps): <https://core.telegram.org/stickers>
- LINE Creators Market · Animated Stickers (APNG, 5–20 frames, ≤ 4 s, ≤ 1 MB, first frame is the cover):
  <https://creator.line.me/en/guideline/animationsticker/>
- WeChat Sticker Open Platform (GIF 240×240, ≤ 500 KB, sets of 16 or 24): <https://sticker.weixin.qq.com/>
- APNG spec and GIF89a delay units: see the references in [Formats](formats.md)