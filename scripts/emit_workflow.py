# -*- coding: utf-8 -*-
"""emit_workflow.py — 把 3 关键帧工作流扩成 K 拍剧情工作流，并校验连线。

输入：一份现有的 3 关键帧 UI 工作流（assets/*.json 或你自己的）
      一张剧情卡（JSON，见 assets/story.example.json），或用命令行直接给

用法:
    python emit_workflow.py --base ../workflows/workflow-sdxl.json --story ../assets/story.example.json --out out.json
    python emit_workflow.py --base ../workflows/workflow-moss.json --story ../assets/story.example.json \
        --frames 60 --segs 15,15,15,15 --out out60.json      # 任意帧数
    python emit_workflow.py --base ../workflows/workflow-sdxl.json --beats 4 --segs 6,7,6,5 \
        --lock "masterpiece, 1girl, silver hair, blue eyes" --style "anime screencap" \
        --actions "neutral expression|eyes widened|mouth open|flat expression" --out out.json
    python emit_workflow.py --validate out.json                  # 只校验
    python emit_workflow.py --base ../workflows/workflow-sdxl.json --story ../assets/story.example.json \
        --dynamic --out out-dynamic.json      # 每拍一个插值节点，帧数是图里的 widget
    python emit_workflow.py --validate out.json --run --profile ../profiles/xl.json

输出结构：K 关键帧 -> N LatentInterpolate -> N VAEDecode -> ImageBatchMulti -> 三格式。
N 由 --frames 决定（默认 24，支持 8/12/24/30/60 任意值）；插值、解码、batch 节点会自动扩缩。
"""
import argparse
import copy
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_lib as L
import timing as T


class Ledger:
    def __init__(self, links):
        self.links = {l[0]: list(l) for l in links}
        self.next = (max(self.links) + 1) if self.links else 1

    def add(self, o, oslot, t, tslot, ty="LATENT"):
        lid = self.next
        self.next += 1
        self.links[lid] = [lid, o, oslot, t, tslot, ty]
        return lid

    def drop(self, lid):
        self.links.pop(lid, None)

    def out(self):
        return [self.links[k] for k in sorted(self.links)]


def node_by(nodes, nid):
    for n in nodes:
        if n["id"] == nid:
            return n
    raise KeyError(nid)


def input_origin(wf, node, name):
    """返回 (origin_node_id, origin_slot, link_id)"""
    links = {l[0]: l for l in wf["links"]}
    for inp in node.get("inputs") or []:
        if inp.get("name") == name and inp.get("link") is not None:
            l = links[inp["link"]]
            return l[1], l[2], l[0]
    raise KeyError("%s has no linked input %s" % (node.get("type"), name))


def positive_encoder(wf, sampler):
    """返回控制该 KSampler positive 的 CLIPTextEncode，自动穿透全局动作合并层。"""
    nodes = wf["nodes"]
    o = input_origin(wf, sampler, "positive")
    n = node_by(nodes, o[0])
    while n["type"] == "ConditioningCombine":
        o = input_origin(wf, n, "conditioning_2")
        n = node_by(nodes, o[0])
    return n


DYN_INTERP = "APNGLatentInterpolateN"
DYN_CONCAT = "APNGLatentConcat"
DYN_STATS = "APNGFrameStats"
DYN_CAMERA = "APNGCameraMove"
CAM_EASINGS = ("linear", "sine", "cubic", "quint", "back", "elastic", "bounce")


def _new_node(nid, ntype, pos, size, inputs, outputs, widgets, title, order):
    return {
        "id": nid, "type": ntype, "pos": pos, "size": size, "flags": {},
        "order": order, "mode": 0, "inputs": inputs, "outputs": outputs,
        "properties": {"Node name for S&R": ntype},
        "widgets_values": widgets, "title": title,
    }


def apply_dynamic(wf, ledger, chain, segs, curve, fps, vae_o, camera=False):
    """静态 N 插值 + N 解码 -> 每拍一个插值节点 + 一次解码 + 帧报告。"""
    nodes = wf["nodes"]
    # 也清掉上一次 --dynamic 留下的节点，保证对动态图重复跑是幂等的
    kill = {n["id"] for n in nodes
            if n["type"] in ("LatentInterpolate", "VAEDecode", "ImageBatchMulti",
                             DYN_INTERP, DYN_CONCAT, DYN_STATS)
            or (n["type"] == "Note"
                and str((n.get("widgets_values") or [""])[0]).startswith("动态帧数模式"))}
    keep = []
    for n in nodes:
        if n["id"] in kill:
            for inp in n.get("inputs") or []:
                if inp.get("link") is not None:
                    ledger.drop(inp["link"])
        else:
            keep.append(n)
    nodes[:] = keep
    for lid in list(ledger.links):
        o, t = ledger.links[lid][1], ledger.links[lid][3]
        if o in kill or t in kill:
            ledger.drop(lid)

    nid = max(n["id"] for n in nodes)
    order = max(n.get("order", 0) for n in nodes)
    max_x = max((n.get("pos") or [0, 0])[0] for n in nodes)

    def add(ntype, pos, size, inputs, widgets, title,
            out_name="LATENT", out_type="LATENT"):
        nonlocal nid, order
        nid += 1
        order += 1
        n = _new_node(nid, ntype, pos, size, inputs,
                      [{"name": out_name, "type": out_type, "links": []}],
                      widgets, title, order)
        nodes.append(n)
        return n

    segs_n = len(segs)
    interps = []
    for i, cnt in enumerate(segs):
        if segs_n == 1:
            role = "first"
        elif i == 0:
            role = "first"
        elif i == segs_n - 1:
            role = "last"
        else:
            role = "middle"
        src = chain[i]
        dst = chain[i + 1] if i + 1 < len(chain) else chain[0]
        n = add(DYN_INTERP, [max_x + 420, 60 + i * 240], [320, 150],
                [{"name": "samples1", "type": "LATENT", "link": None},
                 {"name": "samples2", "type": "LATENT", "link": None}],
                [cnt, role, curve],
                "拍 %d：%s→%s（frames=%d）" % (i, name_of(src, i), name_of(dst, (i + 1) % len(chain)), cnt))
        n["inputs"][0]["link"] = ledger.add(src["id"], 0, n["id"], 0, "LATENT")
        n["inputs"][1]["link"] = ledger.add(dst["id"], 0, n["id"], 1, "LATENT")
        interps.append(n)

    acc = interps[0]
    for i, nxt in enumerate(interps[1:], start=1):
        n = add(DYN_CONCAT, [max_x + 800, 60 + segs_n * 240 + i * 110], [280, 60],
                [{"name": "samples1", "type": "LATENT", "link": None},
                 {"name": "samples2", "type": "LATENT", "link": None}],
                [], "拼 batch %d" % i)
        n["inputs"][0]["link"] = ledger.add(acc["id"], 0, n["id"], 0, "LATENT")
        n["inputs"][1]["link"] = ledger.add(nxt["id"], 0, n["id"], 1, "LATENT")
        acc = n

    dec = add("VAEDecode", [max_x + 1140, 60], [240, 46],
              [{"name": "samples", "type": "LATENT", "link": None},
               {"name": "vae", "type": "VAE", "link": None}],
              [], "解码全部帧", out_name="IMAGE", out_type="IMAGE")
    dec["inputs"][0]["link"] = ledger.add(acc["id"], 0, dec["id"], 0, "LATENT")
    dec["inputs"][1]["link"] = ledger.add(vae_o[0], vae_o[1], dec["id"], 1, "VAE")

    img_src = dec
    if camera:
        cam = add(DYN_CAMERA, [max_x + 1140, 140], [320, 260],
                  [{"name": "images", "type": "IMAGE", "link": None}],
                  [0.0, 0.0, 1.0, 0.0, "sine", True, "reflection"],
                  "镜头运动（x/y/zoom/angle；默认中立）",
                  out_name="IMAGE", out_type="IMAGE")
        cam["inputs"][0]["link"] = ledger.add(dec["id"], 0, cam["id"], 0, "IMAGE")
        img_src = cam

    stats = add(DYN_STATS, [max_x + 1500, 140], [340, 300],
                [{"name": "images", "type": "IMAGE", "link": None}],
                [fps, ",".join(str(x) for x in segs)],
                "帧报告（帧数 / 时长 / 相邻帧差 / 接缝）",
                out_name="STRING", out_type="STRING")
    stats["inputs"][0]["link"] = ledger.add(img_src["id"], 0, stats["id"], 0, "IMAGE")

    nid += 1
    order += 1
    nodes.append({
        "id": nid, "type": "Note",
        "pos": [max_x + 800, 60 + segs_n * 240 + (segs_n - 1) * 110 + 140],
        "size": [460, 240], "flags": {}, "order": order, "mode": 0,
        "widgets_values": [
            "动态帧数模式（APNG 节点）\n"
            "- 每拍一个「APNG Latent Interpolate N」：frames = 这一拍的帧数，改数字即改帧数\n"
            "- 总帧数 = 各拍 frames 之和；时长 = 总帧数 / fps（fps 在三个保存节点上）\n"
            "- role 按拍序固定为 first / middle / last，删拍加拍时记得同步\n"
            "- 「帧报告」节点打印相邻帧差与循环接缝差，阈值与 check_anim.py 一致\n"
            "- 改完 frames 要同步把 Frame Stats 的 segs 改成新的逗号列表"
            + ("\n- 镜头运动节点默认中立；x/y 是整段总位移（像素），zoom 是末帧倍率，angle 是总角度；"
               "loop=True 时首尾回到原位" if camera else "")
        ],
    })

    for n in nodes:
        if n["type"] not in ("SaveAnimatedPNG", "SaveAnimatedWEBP", "VHS_VideoCombine"):
            continue
        for inp in n.get("inputs") or []:
            if inp.get("name") == "images":
                if inp.get("link") is not None:
                    ledger.drop(inp["link"])
                inp["link"] = ledger.add(img_src["id"], 0, n["id"], 0, "IMAGE")
    return interps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="")
    ap.add_argument("--story", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--beats", type=int, default=0)
    ap.add_argument("--segs", default="")
    ap.add_argument("--frames", type=int, default=0,
                    help="总帧数，默认 24；8/12/24/30/60 都可，脚本自动扩缩插值与解码节点")
    ap.add_argument("--fps", type=float, default=0)
    ap.add_argument("--dwell", default="", help="每拍停留权重，逗号分隔；缺省全 1.0")
    ap.add_argument("--ease", type=float, default=-1, help="拍内缓动 0..0.8，默认取剧情卡或 0.3")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--lock", default="")
    ap.add_argument("--style", default="")
    ap.add_argument("--negative", default="")
    ap.add_argument("--actions", default="")
    ap.add_argument("--denoise", type=float, default=0)
    ap.add_argument("--dynamic", action="store_true",
                    help="动态帧数模式：每拍一个 APNG Latent Interpolate N + 一次解码（需要 comfyui_nodes 节点）")
    ap.add_argument("--camera", action="store_true",
                    help="动态模式配 --camera：解码后插入 APNG Camera Move（默认中立，图上再调）")
    ap.add_argument("--size", type=int, default=0, help="正方形边长；写 640 就是 640x640")
    ap.add_argument("--width", type=int, default=0)
    ap.add_argument("--height", type=int, default=0)
    ap.add_argument("--prompt-mode", choices=["tags", "moss_zh"], default="",
                    help="tags=英文逗号标签（SDXL）；moss_zh=中文散文段落（MOSS / Qwen-VL 编码器）")
    ap.add_argument("--motion", default=None,
                    help="全局动作指导，写进所有关键帧共享的 CLIPTextEncode")
    ap.add_argument("--curve", choices=["linear", "ease", "snap"], default="")
    ap.add_argument("--steps", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--cfg", type=float, default=0)
    ap.add_argument("--seed-mode", choices=["same", "offset"], default=None,
                    help="same=所有关键帧同 seed（少抖动，默认）；offset=逐帧 +1")
    ap.add_argument("--notes-only", action="store_true",
                    help="只给 --base 补/更新两个说明 Note，不动其它节点")
    ap.add_argument("--validate", default="")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--profile", default="")
    a = ap.parse_args()

    if a.notes_only:
        if not a.base:
            print("--notes-only 需要 --base")
            return 2
        wf = L.load_json(a.base)
        apply_notes(wf["nodes"])
        wf["last_node_id"] = max(n["id"] for n in wf["nodes"])
        L.save_json(a.out or a.base, wf)
        print("notes-only:", a.out or a.base, "nodes=%d" % len(wf["nodes"]))
        return 0

    if a.validate:
        wf = L.load_json(a.validate)
        probs = validate(wf)
        print(("OK  " if not probs else "FAIL  ") + a.validate)
        for p in probs:
            print("  -", p)
        if probs:
            return 1
        if not a.run:
            return 0
        return run_it(wf, a.profile, None)

    if not (a.base and a.out):
        print("需要 --base 与 --out（或用 --validate）")
        return 2

    wf = L.load_json(a.base)
    story = L.load_json(a.story) if a.story else {}

    kfs = story.get("keyframes") or []
    actions = story.get("actions") or ([x.strip() for x in a.actions.split("|")] if a.actions else [])
    beats = a.beats or story.get("beats") or (len(kfs) if kfs else 3)
    if actions and len(actions) != beats:
        print("actions 个数 %d != beats %d" % (len(actions), beats))
        return 2
    frames = a.frames or int(story.get("frames", 0) or 0) or 24
    if frames < beats or frames < 2:
        print("--frames %d 太小：必须 >= beats=%d 且 >= 2" % (frames, beats))
        return 2
    # 剧情卡的 segs 只在帧数没被命令行改写时沿用；--frames 改了帧数就按拍重新平均分。
    segs_arg = a.segs
    if not segs_arg and story.get("segs"):
        story_frames = int(story.get("frames", 0) or 0)
        # --frames 一旦改写总帧数，剧情卡里的 segs 就不能照抄（否则和之和会对不上）
        if (not a.frames) or (story_frames and story_frames == frames):
            segs_arg = ",".join(str(x) for x in story["segs"])
    segs = [int(x) for x in (segs_arg or "").split(",") if x.strip()]
    if not segs:
        segs = {24: {3: [8, 8, 8], 4: [6, 7, 6, 5], 5: [5, 6, 5, 4, 4]}}.get(frames, {}).get(beats)
        if not segs:  # 其它帧数：按拍平均分，余数给前几拍
            q, r = divmod(frames, beats)
            segs = [q + (1 if i < r else 0) for i in range(beats)]
    if len(segs) != beats:
        print("segs 段数 %d != beats %d" % (len(segs), beats))
        return 2
    if sum(segs) != frames:
        print("segs 之和必须等于 frames=%d，当前 %d" % (frames, sum(segs)))
        return 2

    lock = a.lock or story.get("lock", "")
    style = a.style or story.get("style", "")
    negative = a.negative or story.get("negative", "")
    fps = a.fps or story.get("fps", 10)
    if a.dwell:
        dwell = [float(x) for x in a.dwell.split(",") if x.strip()]
    else:
        dwell = story.get("dwell") or None
    ease = a.ease if a.ease >= 0 else float(story.get("ease", 0.3))
    prefix = a.prefix or story.get("prefix", "")
    denoise = a.denoise or story.get("denoise", 0)
    motion = story.get("motion", "") if a.motion is None else a.motion
    curve = a.curve or story.get("curve", "linear")
    steps = a.steps or int(story.get("steps", 0))
    cfg = a.cfg or float(story.get("cfg", 0))
    seed_base = a.seed or int(story.get("seed", 0))
    same_seed = (a.seed_mode or story.get("seed_mode", "same")) == "same"
    prompt_mode = a.prompt_mode or story.get("prompt_mode", "tags")
    if prompt_mode not in ("tags", "moss_zh"):
        print("prompt_mode 只能是 tags 或 moss_zh，当前 %r" % prompt_mode)
        return 2

    nodes = wf["nodes"]
    ledger = Ledger(wf["links"])

    # 尺寸：直接改 latent 节点，避免用户在图堆里找「尺寸」节点
    w = a.width or a.size or int(story.get("width", 0) or 0)
    h = a.height or a.size or int(story.get("height", 0) or 0)
    if w or h:
        for n in nodes:
            if n["type"] in ("EmptyLatentImage", "EmptyFlux2LatentImage", "EmptySD3LatentImage"):
                wv = list(n.get("widgets_values") or [])
                if len(wv) >= 2:
                    wv[0] = w or wv[0]
                    wv[1] = h or wv[1]
                    n["widgets_values"] = wv
                    print("size: %sx%s (%s)" % (wv[0], wv[1], n["type"]))

    samplers = sorted([n for n in nodes if n["type"] == "KSampler"], key=lambda n: n.get("order", 0))
    if len(samplers) < 2:
        print("base 里 KSampler 不足，至少要有 首帧 + 1 个关键帧")
        return 2
    k0 = samplers[0]
    key_samplers = [n for n in samplers[1:] if float(n["widgets_values"][-1]) < 1.0]
    if len(key_samplers) < 2:
        print("base 里关键帧 KSampler 不足 2 个")
        return 2

    model_o = input_origin(wf, k0, "model")
    neg_o = input_origin(wf, k0, "negative")
    latent_o = input_origin(wf, key_samplers[0], "latent_image")
    clip_o = input_origin(wf, positive_encoder(wf, k0), "clip")
    vae_o = None
    for n in nodes:
        if n["type"] == "VAEDecode":
            vae_o = input_origin(wf, n, "vae")
            break

    # 现有关键帧的提示词节点
    kf_enc = [positive_encoder(wf, s) for s in key_samplers]

    next_id = max(n["id"] for n in nodes) + 1
    max_x = max((n.get("pos") or [0, 0])[0] for n in nodes)
    max_order = max(n.get("order", 0) for n in nodes)
    base_dn = denoise or float(key_samplers[0]["widgets_values"][-1])
    tmpl = copy.deepcopy(key_samplers[0])

    def mk_encoder(text, y):
        nonlocal next_id, max_order
        enc = copy.deepcopy(kf_enc[0])
        enc["id"] = next_id
        next_id += 1
        enc["order"] = max_order + 1
        max_order += 1
        enc["pos"] = [max_x + 420, y]
        enc["widgets_values"] = [text]
        clip_link = ledger.add(clip_o[0], clip_o[1], enc["id"], 0, "CLIP")
        enc["inputs"] = [{"name": "clip", "type": "CLIP", "link": clip_link}]
        enc["outputs"] = [{"name": "CONDITIONING", "type": "CONDITIONING", "links": []}]
        nodes.append(enc)
        return enc

    def mk_sampler(enc, y, idx):
        nonlocal next_id, max_order
        s = copy.deepcopy(tmpl)
        s["id"] = next_id
        next_id += 1
        s["order"] = max_order + 1
        max_order += 1
        s["pos"] = [max_x + 800, y]
        s0 = seed_base or int(tmpl["widgets_values"][0])
        sv = s0 if same_seed else s0 + idx
        s["widgets_values"] = [sv, "fixed"] + list(tmpl["widgets_values"][2:-1]) + [base_dn]
        m = ledger.add(model_o[0], model_o[1], s["id"], 0, "MODEL")
        p = ledger.add(enc["id"], 0, s["id"], 1, "CONDITIONING")
        ng = ledger.add(neg_o[0], neg_o[1], s["id"], 2, "CONDITIONING")
        lt = ledger.add(latent_o[0], latent_o[1], s["id"], 3, "LATENT")
        s["inputs"] = [{"name": "model", "type": "MODEL", "link": m},
                       {"name": "positive", "type": "CONDITIONING", "link": p},
                       {"name": "negative", "type": "CONDITIONING", "link": ng},
                       {"name": "latent_image", "type": "LATENT", "link": lt}]
        s["outputs"] = [{"name": "LATENT", "type": "LATENT", "links": []}]
        nodes.append(s)
        return s

    # 关键帧链：K0 -> KF1 -> ... -> KFn
    chain = [k0] + list(key_samplers)
    while len(chain) < beats:
        i = len(chain) - 1  # 新增第 i 个关键帧
        text = compile_prompt(lock, style, actions[i] if i < len(actions) else "", prompt_mode)
        enc = mk_encoder(text, 600 + i * 280)
        chain.append(mk_sampler(enc, 600 + i * 280, i))
        kf_enc.append(enc)
    if len(chain) > beats:
        chain = chain[:beats]
    # 已有节点也要回写：关键帧共用首帧 latent，同 seed、同 denoise，否则帧间抖动
    base_seed = seed_base or int(k0["widgets_values"][0])
    for i, s in enumerate(chain):
        w = list(s["widgets_values"])
        w[0] = base_seed if same_seed else base_seed + i
        if i:
            w[-1] = base_dn
        s["widgets_values"] = w
    if not actions:
        actions = [""] * beats
    # 写提示词
    pos0 = positive_encoder(wf, k0)
    pos0["widgets_values"] = [compile_prompt(lock, style, actions[0], prompt_mode)]
    pos0["title"] = "K0 首帧提示"
    for i, enc in enumerate(kf_enc[: beats - 1], start=1):
        enc["widgets_values"] = [compile_prompt(lock, style, actions[i], prompt_mode)]
        enc["title"] = "K%d 提示" % i
    if negative:
        node_by(nodes, neg_o[0])["widgets_values"] = [negative]
    for i, s in enumerate(chain):
        act = (actions[i] if i < len(actions) else "").split(",")[0].strip()
        s["title"] = ("K0 首帧" if i == 0 else "K%d 关键帧" % i) + (("：%s" % act) if act else "")
        w = list(s["widgets_values"])
        if steps:
            w[2] = steps
        if cfg:
            w[3] = cfg
        s["widgets_values"] = w

    def ledger_origin(node, name):
        for inp in node.get("inputs") or []:
            if inp.get("name") == name and inp.get("link") is not None:
                l = ledger.links[inp["link"]]
                return l[1], l[2], l[0]
        raise KeyError("%s has no linked input %s" % (node.get("type"), name))

    # ---- 全局动作指导层（幂等：重复 emit 不会叠加节点）----
    # 每个关键帧 positive = ConditioningCombine(全局动作, 该帧提示)
    # 改一个节点全片生效；每帧提示仍然独立可调。
    genc = None
    for n in nodes:
        if n["type"] == "CLIPTextEncode" and str(n.get("title") or "").startswith("全局动作指导"):
            genc = n
            break
    if genc is None:
        genc = mk_encoder("", 100)
    genc["title"] = "全局动作指导（所有关键帧共享）"
    genc["widgets_values"] = [motion]
    genc["pos"] = [max_x + 420, 100]
    empty_motion = not (motion or "").strip()
    chain_encs = [positive_encoder(wf, k0)] + list(kf_enc)
    for i, s in enumerate(chain):
        # 全局动作留空时直接旁路：空提示参与 ConditioningCombine 会稀释本帧提示，
        # 小模型（Moss 8step）会直接掉画质。留空 = 不参与。
        if empty_motion:
            enc = chain_encs[i] if i < len(chain_encs) else None
            if enc is not None:
                for inp in s["inputs"]:
                    if inp["name"] == "positive":
                        if inp.get("link") is not None:
                            ledger.drop(inp["link"])
                        inp["link"] = ledger.add(enc["id"], 0, s["id"], 1, "CONDITIONING")
            continue
        origin = ledger_origin(s, "positive")
        onode = node_by(nodes, origin[0])
        if onode["type"] == "ConditioningCombine":
            comb = onode
            comb["title"] = "合并 K%d（全局动作 + 本帧）" % i
            l1 = ledger.add(genc["id"], 0, comb["id"], 0, "CONDITIONING")
            for inp in comb["inputs"]:
                if inp["name"] == "conditioning_1":
                    if inp.get("link") is not None:
                        ledger.drop(inp["link"])
                    inp["link"] = l1
        else:
            comb = {
                "id": next_id, "type": "ConditioningCombine",
                "pos": [max_x + 820, 600 + i * 280], "size": [315, 46],
                "flags": {}, "order": max_order + 1, "mode": 0,
                "inputs": [], "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": []}],
                "properties": {"Node name for S&R": "ConditioningCombine"},
            }
            comb["title"] = "合并 K%d（全局动作 + 本帧）" % i
            next_id += 1
            max_order += 1
            nodes.append(comb)
            l1 = ledger.add(genc["id"], 0, comb["id"], 0, "CONDITIONING")
            l2 = ledger.add(onode["id"], 0, comb["id"], 1, "CONDITIONING")
            comb["inputs"] = [
                {"name": "conditioning_1", "type": "CONDITIONING", "link": l1},
                {"name": "conditioning_2", "type": "CONDITIONING", "link": l2},
            ]
            for inp in s["inputs"]:
                if inp["name"] == "positive":
                    if inp.get("link") is not None:
                        ledger.drop(inp["link"])
                    inp["link"] = ledger.add(comb["id"], 0, s["id"], 1, "CONDITIONING")

    apply_notes(nodes)

    if a.dynamic:
        apply_dynamic(wf, ledger, chain, segs, curve, fps, vae_o, a.camera)
        print("dynamic: %d 拍 -> %d 个插值节点 + 1 次解码（帧数合计 %d）"
              % (len(segs), len(segs), sum(segs)))
    else:
        # N 个插值 / 解码（N = frames），不足则克隆补齐，多余则删掉
        interps, decodes = ensure_frames(wf, ledger, frames)
        ratios = L.build_curve(segs, curve=curve)
        idx = 0
        for seg, cnt in enumerate(segs):
            src = chain[seg]
            dst = chain[seg + 1] if seg + 1 < len(chain) else chain[0]
            for _ in range(cnt):
                n = interps[idx]
                for inp in n.get("inputs") or []:
                    if inp.get("link") is not None:
                        ledger.drop(inp["link"])
                l1 = ledger.add(src["id"], 0, n["id"], 0, "LATENT")
                l2 = ledger.add(dst["id"], 0, n["id"], 1, "LATENT")
                n["inputs"] = [{"name": "samples1", "type": "LATENT", "link": l1},
                               {"name": "samples2", "type": "LATENT", "link": l2}]
                n["widgets_values"] = [ratios[idx]]
                n["title"] = "插值 %d (%s→%s)" % (idx + 1, name_of(chain[seg], seg), name_of(dst, (seg + 1) % len(chain)))
                idx += 1

    # 输出节点
    for n in nodes:
        if n["type"] == "SaveAnimatedPNG":
            w = list(n["widgets_values"])
            w[1] = fps
            if prefix:
                w[0] = prefix + "/apng/" + (story.get("name") or "anim24")
            n["widgets_values"] = w
        elif n["type"] == "SaveAnimatedWEBP":
            w = list(n["widgets_values"])
            w[1] = fps
            if prefix:
                w[0] = prefix + "/webp/" + (story.get("name") or "anim24")
            n["widgets_values"] = w
        elif n["type"] == "VHS_VideoCombine":
            w = list(n["widgets_values"])
            w[0] = fps
            if prefix:
                w[2] = prefix + "/gif/" + (story.get("name") or "anim24")
            n["widgets_values"] = w

    # 重建连线与 outputs
    wf["links"] = ledger.out()
    by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        for o in n.get("outputs") or []:
            o["links"] = []
    for lid, o, oslot, t, tslot, ty in wf["links"]:
        src = by_id.get(o)
        if src and (src.get("outputs") or []):
            outs = src["outputs"]
            if oslot < len(outs):
                outs[oslot].setdefault("links", []).append(lid)
    for n in nodes:
        for inp in n.get("inputs") or []:
            if inp.get("link") is not None and inp["link"] not in ledger.links:
                inp["link"] = None
    wf["last_node_id"] = max(n["id"] for n in nodes)
    wf["last_link_id"] = max(ledger.links) if ledger.links else 0

    probs = validate(wf)
    L.save_json(a.out, wf)
    print("written:", a.out, "nodes=%d links=%d" % (len(nodes), len(wf["links"])))
    print("beats=%d frames=%d segs=%s fps=%s denoise=%s curve=%s" % (beats, frames, segs, fps, base_dn, curve))
    print("prompt_mode=%s  motion=%r" % (prompt_mode, motion))
    print_timing(frames, segs, fps, dwell, ease)
    if probs:
        print("VALIDATE FAIL")
        for p in probs:
            print("  -", p)
        return 1
    print("VALIDATE OK")
    for i in range(beats):
        print("  K%d: %s" % (i, (actions[i] or "")[:100]))
    if a.run:
        return run_it(wf, a.profile, None)
    return 0


NOTE_PARAMS_TITLE = "【可调参数清单】"
NOTE_PROMPTS_TITLE = "【提示词写法（按架构分方言）】"

NOTE_PARAMS_TEXT = (
    "【可调参数清单】\n"
    "全片动作：\"全局动作指导（所有关键帧共享）\" 这个 CLIPTextEncode。\n"
    "  填动作、镜头、光照、风格；改一处，K0..Kn 全部生效。留空=不加额外条件。\n"
    "每帧表情：K0 / K1 / K2 ... 各自的 CLIPTextEncode，可独立改。\n"
    "采样：每个 KSampler 的 seed / steps / cfg / denoise / sampler / scheduler 都能单独改。\n"
    "  关键帧 denoise 按【架构】给，不按模型名给：\n"
    "    UNet 系（SD1.5 / SDXL）        0.35-0.45   steps 20-30   cfg 5-7\n"
    "    DiT 系（FLUX / SD3 / Krea）    0.45-0.55   steps 20-28   cfg 1.0\n"
    "    DiT + DMD（MOSS-Image）        0.82-0.90   steps 8       cfg 1.0\n"
    "  越高越自由，但容易出现色斑。蒸馏模型加 steps 只会更糊，不要加。\n"
    "节奏：N 个 LatentInterpolate 的 ratio 就是缓动曲线（N = frames）。线性最均匀，缓动两端慢。\n"
    "速度：三个保存节点的 fps 必须改成同一个值。fps × N = 时长。\n"
    "  但 ComfyUI 只能给一个全局 fps，每拍停留表达不出来 —— 出片后跑\n"
    "  python scripts/retime.py <apng> --story <剧情卡> 重写逐帧延时，像素一个都不动。\n"
    "命名：三个保存节点分别写到 APNG/final/apng、webp、gif。\n"
    "画质：APNG 用 compress_level；WebP 用 lossless/quality；GIF 由 VHS 的 loop/pingpong 控制。\n"
    "避坑：关键帧必须共用同一 seed 和同一首帧 latent；denoise 过高会让无关区域重绘，插值时出现色斑。\n"
    "帧数、fps、每拍停留、提示词怎么写：看右边【提示词写法】这个 Note。"
)

NOTE_PROMPTS_TEXT = (
    "【提示词写法（按架构分方言，不按模型名）】\n"
    "\n"
    "先认清三件事，再决定怎么写：\n"
    "  架构：UNet 还是 DiT —— 决定 denoise 区间，不影响文字写法\n"
    "  文本编码器：CLIP / T5 / Qwen-VL —— 决定提示词方言\n"
    "  步数范式：常规 20-30 步 还是 DMD/Turbo 蒸馏 —— 决定 steps\n"
    "  注意：MOSS-Image 是 DiT 的一种，不是 DiT 之外的另一类。\n"
    "        SDXL 是 UNet，不是 DiT。\n"
    "\n"
    "■ 方言 A · CLIP 标签（SD1.5 / SDXL）\n"
    "  格式：角色与场景标签, 这一拍动作, 画风标签\n"
    "  · 英文逗号分隔，重要标签往前放。\n"
    "  · 画风必须放最后：anime screencap, clean lineart, flat cel shading。\n"
    "  · 写画面不写效果：写「eyes wide, pupils small」不写「shocked」。\n"
    "  · 负向单独一个 CLIPTextEncode，不要混进正向。\n"
    "  例：1girl, solo, full body, black short hair, blue eyes, beige hoodie,\n"
    "      sitting on floor, bedroom at night, warm lamp light /\n"
    "      这一拍动作 /\n"
    "      anime screencap, clean lineart, flat cel shading\n"
    "\n"
    "■ 方言 B · 中文散文（MOSS-Image / Krea 2 / Qwen-Image 的 Qwen-VL 系）\n"
    "  格式：中文散文，换行分段，每段以「。」结尾\n"
    "  · 不堆 quality tag：masterpiece / best quality 对它是噪声。\n"
    "  · 场景 → 人物 → 这一拍 → 画风，四件事说全。\n"
    "  · 用可测量的身体描述代替形容词：\n"
    "      震惊 = 双眼睁大、瞳孔缩小、嘴张开\n"
    "      疲惫嫌弃 = 眼半闭、瞳孔偏低、唇压成直线\n"
    "  · 构图写死：固定机位、平视、全身镜头、从头到脚完整入画。\n"
    "  · 负向同样用中文，放单独的 CLIPTextEncode。\n"
    "\n"
    "■ 方言 C · T5 自然语言（FLUX / SD3 / SD3.5）\n"
    "  格式：完整英文句子，一段话讲清画面\n"
    "  · 不用 (word:1.3) 权重括号，T5 不吃这套。\n"
    "  · 一句话一件事：主体、动作、环境、光线、镜头、材质。\n"
    "  · 可以长，但不要堆同义词。\n"
    "  · FLUX 走 FluxGuidance 3.5 / cfg 1.0；SD3 用 cfg 4-7。\n"
    "\n"
    "■ 画面里要出现文字时（Layout）\n"
    "  · 用绝对像素 bbox [x0,y0,x1,y1]，不要归一化坐标。\n"
    "  · 宽高必须是 16 的倍数。\n"
    "  · 不要写「headline here」这类占位符，直接写要显示的原文。\n"
    "  · 只描述可见内容，不要把「怎么生成」这种工具指令写进画面描述。\n"
    "\n"
    "■ 逐拍三段式（写剧情卡时照这个来）\n"
    "  lock   场景 + 人物 + 机位，全片一个字都不改\n"
    "  action 这一拍唯一的变量；每拍只改一个变量\n"
    "  style  画风收尾，全片统一\n"
    "  改两个变量，插值出来就是两张不同的脸。\n"
    "\n"
    "■ 帧数、fps、每拍停留\n"
    "           慢（叙事）        标准             快（弹幕感）\n"
    "   8 帧   6fps / 1.33s    8fps / 1.00s    10fps / 0.80s\n"
    "  24 帧   8fps / 3.00s   10fps / 2.40s    12fps / 2.00s\n"
    "  30 帧  10fps / 3.00s   15fps / 2.00s    20fps / 1.50s\n"
    "  60 帧  20fps / 3.00s   25fps / 2.40s    30fps / 2.00s   ← 本仓库默认 20fps\n"
    "  · GIF 的帧延时只能量化到 10ms：24fps 会被写成 40ms，整片变 2.4s 而不是 2.5s。\n"
    "    要 GIF 干净就选 20 / 25 / 30fps；APNG / WebP 是毫秒精度，不受限。\n"
    "  · 每拍至少 0.20s，低于这个数观感是一闪而过。\n"
    "  · 改帧数：python scripts/emit_workflow.py --frames N --segs a,b,c,...\n"
    "    segs 之和必须等于 N；每拍至少 1 帧。\n"
    "\n"
    "■ 换故事不改节点\n"
    "  只改三个地方：全局动作指导、K0..Kn 各自提示、segs。\n"
    "  节点数量、连线、保存路径都不用动。"
)


def print_timing(frames, segs, fps, dwell=None, ease=0.3):
    """打印时间表：每拍多少帧、多少毫秒、整片多长。"""
    if dwell is not None and len(dwell) != len(segs):
        print("WARN: dwell 长度 %d != 段数 %d，已忽略" % (len(dwell), len(segs)))
        dwell = None
    try:
        s = T.summary(frames, segs, fps, dwell=dwell, ease=ease, quantum=1)
    except ValueError as exc:
        print("WARN: 时间表算不出来（%s），检查 fps / segs / dwell" % exc)
        return
    print("timing  : fps=%g  total=%.2f s  frame=%d..%d ms  ease=%g"
          % (s["fps"], s["total_s"], s["frame_ms_min"], s["frame_ms_max"], ease))
    print("beats   : " + "  ".join("%.0fms" % x for x in s["beats_ms"]))
    thin = [i for i, x in enumerate(s["beats_ms"]) if x < 200]
    if thin:
        print("WARN    : 第 %s 拍短于 0.20 s，观感是一闪而过；调高对应 dwell 或降 fps"
              % ",".join("K%d" % i for i in thin))
    print("         ComfyUI 只能给一个全局 fps；逐帧停留请在出片后跑 "
          "python scripts/retime.py <apng> --story <剧情卡>")


def _note_key(text):
    """Note 的稳定标识：去掉标题里的括号说明，旧标题也能复用同一个节点。"""
    t = str(text or "").lstrip().split("\n")[0]
    for sep in ("（", "("):
        i = t.find(sep)
        if i > 0:
            return t[:i]
    return t[:12]


def apply_notes(nodes):
    """补/更新画布上的两个说明 Note（幂等）。就地修改 nodes。"""
    nid = max(n["id"] for n in nodes)
    order = max(n.get("order", 0) for n in nodes)
    max_x = max((n.get("pos") or [0, 0])[0] for n in nodes)

    specs = [
        (NOTE_PARAMS_TITLE, NOTE_PARAMS_TEXT, [max_x + 420, 1080], [520, 380]),
        (NOTE_PROMPTS_TITLE, NOTE_PROMPTS_TEXT, [max_x + 1000, 1080], [760, 780]),
    ]
    for title, text, pos, size in specs:
        hit = None
        key = _note_key(title)
        for n in nodes:
            if n["type"] == "Note" and _note_key((n.get("widgets_values") or [""])[0]) == key:
                hit = n
                break
        if hit is None:
            nid += 1
            order += 1
            nodes.append({
                "id": nid, "type": "Note", "pos": pos, "size": size,
                "flags": {}, "order": order, "mode": 0, "widgets_values": [text],
            })
        else:
            hit["widgets_values"] = [text]
            hit["pos"] = pos
            hit["size"] = size


def ensure_frames(wf, ledger, frames):
    """把插值/解码/batch 三件套扩到或缩到 frames 帧，并重排画布位置。

    返回 (interps, decodes)，顺序即播放顺序。
    """
    nodes = wf["nodes"]
    batch = next(n for n in nodes if n["type"] == "ImageBatchMulti")
    interps = sorted([n for n in nodes if n["type"] == "LatentInterpolate"], key=lambda n: n.get("order", 0))
    decodes = sorted([n for n in nodes if n["type"] == "VAEDecode"], key=lambda n: n.get("order", 0))
    pair = {}
    for d in decodes:
        for inp in d.get("inputs") or []:
            lid = inp.get("link")
            if inp.get("name") == "samples" and lid in ledger.links:
                pair[ledger.links[lid][1]] = d
    cur = len(interps)
    next_id = max(n["id"] for n in nodes) + 1
    max_order = max(n.get("order", 0) for n in nodes)

    if frames > cur:
        tpl_i = interps[-1]
        tpl_d = pair[tpl_i["id"]]
        vae_o = None
        for inp in tpl_d.get("inputs") or []:
            if inp.get("name") == "vae" and inp.get("link") in ledger.links:
                l = ledger.links[inp["link"]]
                vae_o = (l[1], l[2])
        if vae_o is None:
            raise KeyError("VAEDecode 没有接 VAE，无法克隆解码节点")
        for k in range(frames - cur):
            ni = copy.deepcopy(tpl_i)
            ni["id"], next_id = next_id, next_id + 1
            ni["order"], max_order = max_order + 1, max_order + 1
            ni["title"] = "插值 %d" % (cur + k + 1)
            ni["inputs"] = [{"name": "samples1", "type": "LATENT", "link": None},
                            {"name": "samples2", "type": "LATENT", "link": None}]
            ni["outputs"] = [{"name": "LATENT", "type": "LATENT", "links": []}]
            nd = copy.deepcopy(tpl_d)
            nd["id"], next_id = next_id, next_id + 1
            nd["order"], max_order = max_order + 1, max_order + 1
            nd["title"] = "解码 %d" % (cur + k + 1)
            s_link = ledger.add(ni["id"], 0, nd["id"], 0, "LATENT")
            v_link = ledger.add(vae_o[0], vae_o[1], nd["id"], 1, "VAE")
            nd["inputs"] = [{"name": "samples", "type": "LATENT", "link": s_link},
                            {"name": "vae", "type": "VAE", "link": v_link}]
            nd["outputs"] = [{"name": "IMAGE", "type": "IMAGE", "links": []}]
            nodes.append(ni)
            nodes.append(nd)
            interps.append(ni)
            pair[ni["id"]] = nd
    elif frames < cur:
        gone = set()
        for ni in interps[frames:]:
            nd = pair.get(ni["id"])
            for n in (ni, nd):
                if n is None:
                    continue
                gone.add(n["id"])
                for inp in n.get("inputs") or []:
                    if inp.get("link") in ledger.links:
                        ledger.drop(inp["link"])
                    inp["link"] = None
        nodes[:] = [n for n in nodes if n["id"] not in gone]
        interps = interps[:frames]

    decodes = [pair[n["id"]] for n in interps]

    # batch 输入按播放顺序重建
    for inp in list(batch.get("inputs") or []):
        if inp.get("link") is not None:
            ledger.drop(inp["link"])
    batch["inputs"] = []
    for i, nd in enumerate(decodes):
        lid = ledger.add(nd["id"], 0, batch["id"], i, "IMAGE")
        batch["inputs"].append({"name": "image_%d" % (i + 1), "type": "IMAGE", "link": lid})
    batch["widgets_values"] = [len(interps)]

    # 画布排版：6 列一行，插值在上、解码在下
    for i, ni in enumerate(interps):
        col, row = i % 6, i // 6
        ni["pos"] = [1280 + col * 300, 60 + row * 220]
        decodes[i]["pos"] = [1310 + col * 300, 170 + row * 220]
    rows = (len(interps) + 5) // 6
    batch["pos"] = [1280, 60 + rows * 220 + 40]
    return interps, decodes


def name_of(n, i):
    return "K0" if i == 0 else "K%d" % i


def compile_prompt(lock, style, action, mode="tags"):
    """把 场景/人物 (lock) + 这一拍动作 (action) + 画风 (style) 拼成一条提示词。

    tags（SDXL / 传统 CLIP）
        "lock, action, style" —— 英文逗号标签流。
        风格放最后：SDXL 的 CLIP 对末尾 token 权重最高，画风写在中段会被动作词冲掉，
        出图掉进写实照相模式（实测：拼贴照、色块闪）。

    moss_zh（MOSS-Image / Qwen-VL 文本编码器）
        中文散文，换行分段，每段以「。」收尾。
        这类编码器读自然语言语义，不读逗号标签权重；堆 quality tag 反而退化。
        顺序：场景与画风 -> 人物 -> 这一拍 -> 画风收口。
    """
    if mode == "moss_zh":
        segs = []
        for p in (lock, action, style):
            p = (p or "").strip()
            if not p:
                continue
            if p[-1] not in "。！？.!?":
                p += "。"
            segs.append(p)
        return "\n".join(segs)
    parts = [p.strip().rstrip(",") for p in (lock, action, style) if p and p.strip()]
    return ", ".join(parts)


def _validate_static(nodes, links, by_id, savers):
    probs = []
    if any(n["type"] == DYN_CAMERA for n in nodes):
        probs.append("%s 目前只支持 --dynamic 模式" % DYN_CAMERA)
    interps = [n for n in nodes if n["type"] == "LatentInterpolate"]
    nframes = len(interps)
    if nframes < 2:
        probs.append("LatentInterpolate 只有 %d 个，至少 2" % nframes)
    decodes = [n for n in nodes if n["type"] == "VAEDecode"]
    if len(decodes) != nframes:
        probs.append("VAEDecode 数量 %d != 插值数 %d" % (len(decodes), nframes))
    for n in interps:
        w = n.get("widgets_values") or []
        if not w:
            probs.append("插值节点 %s 没有 ratio" % n["id"])
            continue
        if len([i for i in n.get("inputs") or [] if i.get("link") is not None]) != 2:
            probs.append("插值节点 %s 输入不足 2 个" % n["id"])
    # 只有「同一对 latent」上出现重复 ratio 才会产生像素相同的相邻帧。
    groups = {}
    for n in interps:
        w = n.get("widgets_values") or []
        if not w:
            continue
        key = []
        for inp in n.get("inputs") or []:
            lid = inp.get("link")
            if lid in links:
                key.append(links[lid][1])
        groups.setdefault(tuple(key), []).append(w[0])
    for key, vals in groups.items():
        if len(set(vals)) != len(vals):
            probs.append("同一对 latent %s 上 ratio 有重复值，Pillow 会合并帧" % (key,))
    batch = [n for n in nodes if n["type"] == "ImageBatchMulti"]
    if len(batch) != 1:
        probs.append("ImageBatchMulti 数量 %d != 1" % len(batch))
    else:
        b = batch[0]
        got = len([i for i in b.get("inputs") or [] if i.get("link") is not None])
        if got != nframes:
            probs.append("ImageBatchMulti 接了 %d 路，应与插值数 %d 一致" % (got, nframes))
        wv = b.get("widgets_values") or []
        if wv and int(wv[0]) != got:
            probs.append("ImageBatchMulti 计数 %s 与实际接线 %d 不一致" % (wv[0], got))
        outs = [l for o in (b.get("outputs") or []) for l in (o.get("links") or [])]
        hit = set()
        for lid in outs:
            l = links.get(lid)
            if l and by_id.get(l[3], {}).get("type") in ("SaveAnimatedPNG", "SaveAnimatedWEBP", "VHS_VideoCombine"):
                hit.add(by_id[l[3]]["type"])
        if len(hit) != 3:
            probs.append("三个保存节点没有全接在同一个 batch 上: %s" % sorted(hit))
    if len(savers) != 3:
        probs.append("保存节点数量 %d != 3" % len(savers))
    return probs


def _validate_dynamic(nodes, links, by_id, savers):
    probs = []
    interps = [n for n in nodes if n["type"] == DYN_INTERP]
    if not interps:
        probs.append("动态模式没有 %s" % DYN_INTERP)
    total = 0
    for n in interps:
        w = n.get("widgets_values") or []
        if len(w) < 3:
            probs.append("插值节点 %s widgets 不全（应为 frames/role/curve）" % n["id"])
            continue
        try:
            cnt = int(w[0])
        except (TypeError, ValueError):
            probs.append("插值节点 %s frames=%r 不是整数" % (n["id"], w[0]))
            continue
        total += cnt
        if cnt < 1:
            probs.append("插值节点 %s frames=%d 必须 >= 1" % (n["id"], cnt))
        if w[1] not in ("first", "middle", "last"):
            probs.append("插值节点 %s role=%r 非法" % (n["id"], w[1]))
        if w[2] not in ("linear", "ease", "snap"):
            probs.append("插值节点 %s curve=%r 非法" % (n["id"], w[2]))
        for inp in n.get("inputs") or []:
            if inp.get("link") is None:
                probs.append("插值节点 %s 的 %s 没接" % (n["id"], inp["name"]))
    if any(n["type"] == "LatentInterpolate" for n in nodes):
        probs.append("动态模式里还留着 LatentInterpolate，两套混用")
    if any(n["type"] == "ImageBatchMulti" for n in nodes):
        probs.append("动态模式不需要 ImageBatchMulti")
    decs = [n for n in nodes if n["type"] == "VAEDecode"]
    if len(decs) != 1:
        probs.append("动态模式应该只有 1 个 VAEDecode，当前 %d" % len(decs))
    if len(savers) != 3:
        probs.append("保存节点数量 %d != 3" % len(savers))
    cams = [n for n in nodes if n["type"] == DYN_CAMERA]
    if len(cams) > 1:
        probs.append("动态模式最多 1 个 %s，当前 %d" % (DYN_CAMERA, len(cams)))
    for cam in cams:
        w = cam.get("widgets_values") or []
        if len(w) < 7:
            probs.append("镜头节点 %s widgets 不全（应为 x/y/zoom/angle/easing/loop/border）" % cam["id"])
        else:
            for idx in (0, 1, 2, 3):
                try:
                    float(w[idx])
                except (TypeError, ValueError):
                    probs.append("镜头节点 %s 第 %d 个参数不是数字" % (cam["id"], idx + 1))
            if w[4] not in CAM_EASINGS:
                probs.append("镜头节点 %s easing=%r 非法" % (cam["id"], w[4]))
            if not isinstance(w[5], bool):
                probs.append("镜头节点 %s loop 必须是布尔" % cam["id"])
            if w[6] not in ("reflection", "border", "zeros"):
                probs.append("镜头节点 %s border=%r 非法" % (cam["id"], w[6]))
        if not any(i.get("name") == "images" and i.get("link") is not None for i in cam.get("inputs") or []):
            probs.append("镜头节点 %s 没接 images" % cam["id"])
    if decs:
        dec_id = decs[0]["id"]
        expected_src = cams[0]["id"] if cams else dec_id
        if cams:
            cam_src = None
            for inp in cams[0].get("inputs") or []:
                if inp.get("name") == "images" and inp.get("link") in links:
                    cam_src = links[inp["link"]][1]
            if cam_src != dec_id:
                probs.append("%s 没有接在唯一的 VAEDecode 上" % DYN_CAMERA)
        for s_ in savers:
            src = None
            for inp in s_.get("inputs") or []:
                if inp.get("name") == "images" and inp.get("link") in links:
                    src = links[inp["link"]][1]
            if src != expected_src:
                probs.append("%s 没有接在唯一的 VAEDecode%s 上" % (
                    s_["type"], " / 镜头节点" if cams else ""))
    stats = [n for n in nodes if n["type"] == DYN_STATS]
    if len(stats) != 1:
        probs.append("%s 数量 %d != 1" % (DYN_STATS, len(stats)))
    else:
        w = stats[0].get("widgets_values") or []
        txt = str(w[1]) if len(w) > 1 else ""
        segs = [x for x in txt.replace("，", ",").split(",") if x.strip()]
        if segs:
            try:
                ss = sum(int(x) for x in segs)
            except ValueError:
                ss = None
            if ss is not None and ss != total:
                probs.append("帧报告 segs 之和 %d 与各拍 frames 之和 %d 不一致" % (ss, total))
        if decs:
            expected_src = cams[0]["id"] if cams else decs[0]["id"]
            src = None
            for inp in stats[0].get("inputs") or []:
                if inp.get("name") == "images" and inp.get("link") in links:
                    src = links[inp["link"]][1]
            if src != expected_src:
                probs.append("帧报告没有接在最终图像源（解码/镜头节点）上")
    return probs


def validate(wf):
    probs = []
    nodes = wf.get("nodes") or []
    by_id = {n["id"]: n for n in nodes}
    links = {l[0]: l for l in wf.get("links") or []}
    for lid, o, oslot, t, tslot, ty in wf.get("links") or []:
        if o not in by_id or t not in by_id:
            probs.append("link %s 指向不存在的节点 %s->%s" % (lid, o, t))
            continue
        src = by_id[o]
        if not (src.get("outputs") or []) or oslot >= len(src["outputs"]):
            probs.append("link %s origin slot %s 越界 (%s)" % (lid, oslot, src["type"]))
        dst = by_id[t]
        if not (dst.get("inputs") or []) or tslot >= len(dst["inputs"]):
            probs.append("link %s target slot %s 越界 (%s)" % (lid, tslot, dst["type"]))
    for n in nodes:
        for inp in n.get("inputs") or []:
            if inp.get("link") is not None and inp["link"] not in links:
                probs.append("%s 的输入 %s 指向不存在的 link %s" % (n["type"], inp["name"], inp["link"]))
    for n in nodes:
        if n["type"] in ("SaveImage", "PreviewImage"):
            probs.append("不该出现 %s（只存成品）" % n["type"])
    savers = [n for n in nodes if n["type"] in ("SaveAnimatedPNG", "SaveAnimatedWEBP", "VHS_VideoCombine")]
    if any(n["type"] == DYN_INTERP for n in nodes):
        probs.extend(_validate_dynamic(nodes, links, by_id, savers))
    else:
        probs.extend(_validate_static(nodes, links, by_id, savers))
    ks = [n for n in nodes if n["type"] == "KSampler"]
    if ks:
        base = None
        for n in ks[1:]:
            src = None
            for inp in n.get("inputs") or []:
                if inp.get("name") == "latent_image" and inp.get("link") in links:
                    l = links[inp["link"]]
                    src = (l[1], l[2])
            if src is None:
                probs.append("关键帧 %s 的 latent_image 没接" % n["id"])
            elif base is None:
                base = src
            elif src != base:
                probs.append("关键帧的 latent 来源不一致：%s vs %s" % (src, base))
    return probs


def run_it(wf, profile_path, segs=None):
    prof = L.load_json(profile_path) if profile_path else {}
    if not prof:
        print("--run 需要 --profile")
        return 2
    base = L.base_url(prof)
    # Note / Reroute / PrimitiveNode 只活在前端，/object_info 里没有，不能算缺节点
    front_only = {"Note", "Reroute", "PrimitiveNode", "MarkdownNote"}
    types = sorted({n["type"] for n in wf["nodes"]} - front_only)
    info = L.get_object_info_for(base, types)
    missing = [t for t in types if t not in info]
    if missing:
        print("服务器缺节点:", missing)
        return 2
    api = L.ui_to_api(wf, info)
    r = L.queue_prompt(base, api)
    pid = r.get("prompt_id")
    print("queued:", pid)
    if not pid:
        print(r)
        return 2
    hist = L.wait_history(base, pid)
    files = L.outputs_of(hist)
    dyn = [n for n in wf["nodes"] if n["type"] == DYN_INTERP]
    if dyn:
        nframes = sum(int((n.get("widgets_values") or [0])[0]) for n in dyn)
    else:
        nframes = len([n for n in wf["nodes"] if n["type"] == "LatentInterpolate"]) or 24
    print("done. outputs:")
    for f in files:
        print(" ", f)
    for f in files:
        if f.lower().endswith((".png", ".webp", ".gif")):
            p = os.path.join(prof["comfy_root"], "output", f.replace("/", os.sep))
            if os.path.isfile(p):
                chk = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_anim.py")
                # os.system 在 Windows 上对多段带引号路径会报 "filename syntax is incorrect"
                cmd = [prof.get("python") or sys.executable, chk, p, "--expect", str(nframes)]
                if segs:
                    cmd += ["--segs", ",".join(str(x) for x in segs)]
                subprocess.call(cmd)
    return 0


if __name__ == "__main__":
    sys.exit(main())


