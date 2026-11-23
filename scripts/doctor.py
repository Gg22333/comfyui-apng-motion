# -*- coding: utf-8 -*-
"""doctor.py — 检查一个 profile 能不能真的跑这套工作流。

用法:
    python doctor.py                       # 检查 profiles/ 下全部
    python doctor.py --profile profiles/xl.json
    python doctor.py --profile ... --probe 8190   # 指定端口探活

检查项：main.py / python / 工作流文件 / 必需插件 / 工作流引用的模型文件 /
输出目录可写 / 运行中实例是否具备所需节点类型。
退出码：0 全通过；1 有 FAIL。
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_lib as L

REQUIRED_TYPES = ["LatentInterpolate", "SaveAnimatedPNG", "SaveAnimatedWEBP",
                  "VHS_VideoCombine", "ImageBatchMulti", "KSampler", "VAEDecode"]
WANT_NODES = ["comfyui-kjnodes", "ComfyUI-VideoHelperSuite"]
LOADER_KEYS = {
    "CheckpointLoaderSimple": ("ckpt_name", "checkpoints"),
    "UNETLoader": ("unet_name", "diffusion_models"),
    "CLIPLoader": ("clip_name", "text_encoders"),
    "VAELoader": ("vae_name", "vae"),
}


def check(rows, level, name, detail):
    rows.append((level, name, detail))
    return level == "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="")
    ap.add_argument("--probe", type=int, default=0)
    a = ap.parse_args()
    skill = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = [a.profile] if a.profile else L.find_profiles(skill)
    if not paths:
        print("没有 profile，先跑 detect_env.py")
        return 2
    bad = 0
    for p in paths:
        prof = L.load_json(p)
        rows = []
        name = prof.get("name", os.path.basename(p))
        root = prof.get("comfy_root", "")
        check(rows, "PASS" if os.path.isfile(os.path.join(root, "main.py")) else "FAIL",
              "main.py", root)
        py = prof.get("python", "")
        check(rows, "PASS" if py and os.path.isfile(py) else "WARN", "python", py or "(未找到，仅用 HTTP 也能跑)")
        wf = prof.get("workflow", "")
        check(rows, "PASS" if wf and os.path.isfile(wf) else "FAIL", "workflow", wf or "(未找到)")

        nd = os.path.join(root, "custom_nodes")
        have = set(os.listdir(nd)) if os.path.isdir(nd) else set()
        for n in WANT_NODES:
            check(rows, "PASS" if n in have else "FAIL", "custom_node", n)

        wfj = None
        if wf and os.path.isfile(wf):
            wfj = L.load_json(wf)
            present = {x["type"] for x in wfj.get("nodes", [])}
            for t in ("LatentInterpolate", "SaveAnimatedPNG", "SaveAnimatedWEBP", "VHS_VideoCombine"):
                check(rows, "PASS" if t in present else "FAIL", "node_in_workflow", t)
            # 工作流引用的模型
            mroot = os.path.join(root, "models")
            for n in wfj.get("nodes", []):
                spec = LOADER_KEYS.get(n["type"])
                if not spec:
                    continue
                key, sub = spec
                val = (n.get("widgets_values") or [None])[0]
                fp = os.path.join(mroot, sub, val) if val else ""
                check(rows, "PASS" if fp and os.path.isfile(fp) else "FAIL",
                      "model:%s" % sub, val)

        outd = os.path.join(root, "output")
        try:
            os.makedirs(os.path.join(outd, "APNG", "final"), exist_ok=True)
            probe = os.path.join(outd, "APNG", "final", ".doctor.tmp")
            open(probe, "w").close()
            os.remove(probe)
            check(rows, "PASS", "output_writable", outd)
        except OSError as e:
            check(rows, "FAIL", "output_writable", str(e))

        port = a.probe or int(prof.get("port", 8188))
        prof2 = dict(prof, port=port)
        try:
            info = L.get_object_info_for(L.base_url(prof2), REQUIRED_TYPES)
            ok = True
        except Exception as e:
            info, ok = None, False
            check(rows, "WARN", "live_server", "%s:%s 未响应（%s）" % (prof2["host"], port, type(e).__name__))
        if ok:
            check(rows, "PASS", "live_server", "%s:%s" % (prof2["host"], port))
            for t in REQUIRED_TYPES:
                check(rows, "PASS" if t in info else "FAIL", "server_node", t)

        print("\n=== %s (%s) ===" % (name, root))
        for lv, nm, det in rows:
            print("[%-4s] %-20s %s" % (lv, nm, det))
        bad += sum(1 for r in rows if r[0] == "FAIL")
    print("\nFAIL 总数:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

