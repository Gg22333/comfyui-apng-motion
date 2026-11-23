# -*- coding: utf-8 -*-
"""emit_workflow.py — 把 3 关键帧工作流扩成 K 拍剧情工作流，并校验连线。

输入：一份现有的 3 关键帧 UI 工作流（assets/*.json 或你自己的）
      一张剧情卡（JSON，见 assets/story.example.json），或用命令行直接给

用法:
    python emit_workflow.py --base ../assets/workflow-sdxl.json --story ../assets/story.example.json --out out.json
    python emit_workflow.py --base ../assets/workflow-sdxl.json --beats 4 --segs 6,7,6,5 \
        --lock "masterpiece, 1girl, silver hair, blue eyes" --style "anime screencap" \
        --actions "neutral expression|eyes widened|mouth open|flat expression" --out out.json
    python emit_workflow.py --validate out.json                  # 只校验
    python emit_workflow.py --validate out.json --run --profile ../profiles/xl.json

输出结构不变：K 关键帧 -> 24 LatentInterpolate -> 24 VAEDecode -> ImageBatchMulti -> 三格式。
"""
import argparse
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_lib as L


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="")
    ap.add_argument("--story", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--beats", type=int, default=0)
    ap.add_argument("--segs", default="")
    ap.add_argument("--fps", type=float, default=0)
    ap.add_argument("--prefix", default="")
    ap.add_argument("--lock", default="")
    ap.add_argument("--style", default="")
    ap.add_argument("--negative", default="")
    ap.add_argument("--actions", default="")
    ap.add_argument("--denoise", type=float, default=0)
    ap.add_argument("--validate", default="")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--profile", default="")
    a = ap.parse_args()

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
        return run_it(wf, a.profile)

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
    segs = [int(x) for x in (a.segs or ",".join(str(x) for x in story.get("segs", []))).split(",") if x.strip()]
    if not segs:
        segs = {3: [8, 8, 8], 4: [6, 7, 6, 5], 5: [5, 6, 5, 4, 4]}.get(beats)
        if not segs:
            print("请给 --segs（%d 段，和要为 24）" % beats)
            return 2
    if sum(segs) != 24:
        print("segs 之和必须 24，当前 %d" % sum(segs))
        return 2
    if len(segs) != beats:
        print("segs 段数 %d != beats %d" % (len(segs), beats))
        return 2

    lock = a.lock or story.get("lock", "")
    style = a.style or story.get("style", "")
    negative = a.negative or story.get("negative", "")
    fps = a.fps or story.get("fps", 10)
    prefix = a.prefix or story.get("prefix", "")
    denoise = a.denoise or story.get("denoise", 0)

    nodes = wf["nodes"]
    ledger = Ledger(wf["links"])

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
    clip_o = input_origin(wf, node_by(nodes, input_origin(wf, k0, "positive")[0]), "clip")
    vae_o = None
    for n in nodes:
        if n["type"] == "VAEDecode":
            vae_o = input_origin(wf, n, "vae")
            break

    # 现有关键帧的提示词节点
    kf_enc = []
    for s in key_samplers:
        eid = input_origin(wf, s, "positive")[0]
        kf_enc.append(node_by(nodes, eid))

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
        seed = int(tmpl["widgets_values"][0]) + idx
        s["widgets_values"] = [seed, "fixed"] + list(tmpl["widgets_values"][2:-1]) + [base_dn]
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
        text = compile_prompt(lock, style, actions[i] if i < len(actions) else "")
        enc = mk_encoder(text, 600 + i * 280)
        chain.append(mk_sampler(enc, 600 + i * 280, i))
        kf_enc.append(enc)
    if len(chain) > beats:
        chain = chain[:beats]
    if not actions:
        actions = [""] * beats
    # 写提示词
    pos0 = node_by(nodes, input_origin(wf, k0, "positive")[0])
    pos0["widgets_values"] = [compile_prompt(lock, style, actions[0])]
    for i, enc in enumerate(kf_enc[: beats - 1], start=1):
        enc["widgets_values"] = [compile_prompt(lock, style, actions[i])]
    if negative:
        node_by(nodes, neg_o[0])["widgets_values"] = [negative]
    for i, s in enumerate(chain):
        s["title"] = ("首帧 采样" if i == 0 else "关键帧 %d 重绘" % i)

    # 24 个插值
    interps = sorted([n for n in nodes if n["type"] == "LatentInterpolate"], key=lambda n: n.get("order", 0))
    if len(interps) != 24:
        print("base 里 LatentInterpolate 是 %d 个，必须是 24" % len(interps))
        return 2
    ratios = L.build_curve(segs)
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
    print("beats=%d segs=%s fps=%s denoise=%s" % (beats, segs, fps, base_dn))
    if probs:
        print("VALIDATE FAIL")
        for p in probs:
            print("  -", p)
        return 1
    print("VALIDATE OK")
    for i in range(beats):
        print("  K%d: %s" % (i, compile_prompt(lock, style, actions[i])[:120]))
    if a.run:
        return run_it(wf, a.profile)
    return 0


def name_of(n, i):
    return "K0" if i == 0 else "K%d" % i


def compile_prompt(lock, style, action):
    parts = [p.strip().rstrip(",") for p in (lock, style, action) if p and p.strip()]
    return ", ".join(parts)


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
    interps = [n for n in nodes if n["type"] == "LatentInterpolate"]
    if len(interps) != 24:
        probs.append("LatentInterpolate 数量 %d != 24" % len(interps))
    decodes = [n for n in nodes if n["type"] == "VAEDecode"]
    if len(decodes) != 24:
        probs.append("VAEDecode 数量 %d != 24" % len(decodes))
    ratios = []
    for n in interps:
        w = n.get("widgets_values") or []
        if not w:
            probs.append("插值节点 %s 没有 ratio" % n["id"])
            continue
        ratios.append(w[0])
        if len([i for i in n.get("inputs") or [] if i.get("link") is not None]) != 2:
            probs.append("插值节点 %s 输入不足 2 个" % n["id"])
    # 只有「同一对 latent」上出现重复 ratio 才会产生像素相同的相邻帧。
    # 不同段（K0→A 与 A→B）用同一个数值是安全的：样本对不同，画面必然不同。
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
    for n in nodes:
        if n["type"] in ("SaveImage", "PreviewImage"):
            probs.append("不该出现 %s（只存成品）" % n["type"])
    batch = [n for n in nodes if n["type"] == "ImageBatchMulti"]
    if len(batch) != 1:
        probs.append("ImageBatchMulti 数量 %d != 1" % len(batch))
    else:
        b = batch[0]
        got = len([i for i in b.get("inputs") or [] if i.get("link") is not None])
        if got != 24:
            probs.append("ImageBatchMulti 只接了 %d 路，应为 24" % got)
        outs = [l for o in (b.get("outputs") or []) for l in (o.get("links") or [])]
        saver_types = {"SaveAnimatedPNG", "SaveAnimatedWEBP", "VHS_VideoCombine"}
        hit = set()
        for lid in outs:
            l = links.get(lid)
            if l and by_id.get(l[3], {}).get("type") in saver_types:
                hit.add(by_id[l[3]]["type"])
        if len(hit) != 3:
            probs.append("三个保存节点没有全接在同一个 batch 上: %s" % sorted(hit))
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


def run_it(wf, profile_path):
    prof = L.load_json(profile_path) if profile_path else {}
    if not prof:
        print("--run 需要 --profile")
        return 2
    base = L.base_url(prof)
    types = sorted({n["type"] for n in wf["nodes"]})
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
    print("done. outputs:")
    for f in files:
        print(" ", f)
    for f in files:
        if f.lower().endswith((".png", ".webp", ".gif")):
            p = os.path.join(prof["comfy_root"], "output", f.replace("/", os.sep))
            if os.path.isfile(p):
                chk = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_anim.py")
                os.system('"%s" "%s" "%s" --expect 24' % (prof.get("python") or sys.executable, chk, p))
    return 0


if __name__ == "__main__":
    sys.exit(main())

