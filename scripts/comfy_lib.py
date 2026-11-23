# -*- coding: utf-8 -*-
"""comfy_lib.py — 各脚本共用的小工具：profile、HTTP、曲线、UI->API 转换。

设计目标：换一台机器也能跑。所有环境相关的值只从 profile 读，不在代码里写死路径。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EPSS = 0.004
LINKY = {"MODEL", "CLIP", "VAE", "LATENT", "IMAGE", "CONDITIONING", "MASK", "CONTROL_NET",
         "CLIP_VISION", "STYLE_MODEL", "AUDIO", "VHS_FILENAMES", "UPSCALE_MODEL"}


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def find_profiles(skill_dir):
    pdir = os.path.join(skill_dir, "profiles")
    if not os.path.isdir(pdir):
        return []
    return [os.path.join(pdir, n) for n in sorted(os.listdir(pdir)) if n.endswith(".json")]


def base_url(profile):
    return "http://%s:%d" % (profile.get("host", "127.0.0.1"), int(profile.get("port", 8188)))


def http_json(url, payload=None, timeout=30, retries=2):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    last = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
            return json.loads(raw) if raw.strip() else {}
        except Exception as e:
            last = e
            time.sleep(0.4)
    alt = _curl_json(url, payload, timeout)
    if alt is not None:
        return alt
    raise last


def _curl_json(url, payload=None, timeout=30):
    """urllib 被重置时的兜底。Windows 自带 curl.exe，其他系统一般也有 curl。"""
    exe = shutil.which("curl") or shutil.which("curl.exe")
    if not exe:
        return None
    cmd = [exe, "-sS", "--max-time", str(int(max(5, timeout)))]
    tmp = None
    try:
        if payload is not None:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
            tmp.write(json.dumps(payload).encode("utf-8"))
            tmp.close()
            cmd += ["-X", "POST", "-H", "Content-Type: application/json", "--data-binary", "@" + tmp.name]
        cmd.append(url)
        r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace",
                           timeout=timeout + 20)
        if r.returncode != 0 or not (r.stdout or "").strip():
            return None
        return json.loads(r.stdout)
    except Exception:
        return None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


def get_stats(base, timeout=3):
    return http_json(base + "/system_stats", timeout=timeout)


def get_object_info(base, timeout=60):
    return http_json(base + "/object_info", timeout=timeout)


def bundled_schema():
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "assets", "node_schema.json")
    try:
        return load_json(p)
    except Exception:
        return {}


def get_object_info_for(base, types, timeout=30):
    """按类型单独取；个别节点（如 VHS）整包过大时，回落到随包带的 node_schema.json。"""
    out = {}
    for t in types:
        if t in out:
            continue
        try:
            out.update(http_json(base + "/object_info/" + urllib.parse.quote(t), timeout=timeout))
        except Exception:
            continue
    missing = [t for t in types if t not in out]
    if missing:
        bs = bundled_schema()
        for t in missing:
            if t in bs:
                out[t] = bs[t]
    return out


def queue_prompt(base, prompt, client_id="apng-skill"):
    return http_json(base + "/prompt", {"prompt": prompt, "client_id": client_id})


def wait_history(base, prompt_id, timeout=1800, poll=2.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = http_json(base + "/history/" + prompt_id, timeout=30)
        if prompt_id in h:
            return h[prompt_id]
        time.sleep(poll)
    raise TimeoutError("history timeout after %ss" % timeout)


def build_curve(segs, starts=None, ends=None, powers=None):
    n = len(segs)
    if n == 3 and starts is None and ends is None and powers is None:
        starts, ends, powers = [1.0, 0.92, 0.88], [0.08, 0.0, 0.01], [3.0, 1.2, 2.5]
    else:
        starts = starts or ([1.0] + [0.94, 0.92, 0.90, 0.88, 0.86][: n - 1])
        ends = ends or ([0.05, 0.04, 0.03, 0.02, 0.02][: n - 1] + [0.01])
        powers = powers or [1.8] * n
    raw = []
    for cnt, s, e, p in zip(segs, starts, ends, powers):
        for i in range(cnt):
            t = i / (cnt - 1) if cnt > 1 else 1.0
            raw.append(s + (e - s) * (t ** p))
    used = set()
    out = []
    for r in raw:
        v = round(min(max(r, 0.0), 1.0), 3)
        if v in used:  # 全局唯一，不只看相邻：两段各出一个 0.665 也会被 Pillow 合并
            for k in range(1, 250):
                hit = None
                for cand in (round(v + k * 0.004, 3), round(v - k * 0.004, 3)):
                    if 0.0 <= cand <= 1.0 and cand not in used:
                        hit = cand
                        break
                if hit is not None:
                    v = hit
                    break
        used.add(v)
        out.append(v)
    return out


def _widget_keys(info):
    req = (info.get("input") or {}).get("required") or {}
    opt = (info.get("input") or {}).get("optional") or {}
    order = info.get("input_order") or {}
    names = list(order.get("required") or req.keys()) + list(order.get("optional") or opt.keys())
    out = []
    for name in names:
        spec = req.get(name) or opt.get(name)
        if not isinstance(spec, list) or not spec:
            continue
        t = spec[0]
        if isinstance(t, list):
            out.append((name, False))
            continue
        if t in LINKY:
            continue
        meta = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
        out.append((name, bool(meta.get("control_after_generate"))))
    return out


def ui_to_api(wf, info_map):
    nodes = {n["id"]: n for n in wf.get("nodes", [])}
    links = {l[0]: l for l in wf.get("links", [])}
    api = {}
    for nid, n in nodes.items():
        if n.get("mode") == 4:
            continue
        cls = n["type"]
        if cls in ("Note", "Reroute", "PrimitiveNode"):
            continue
        info = info_map.get(cls)
        if not info:
            raise KeyError("profile has no node type: %s" % cls)
        inputs = {}
        for inp in n.get("inputs") or []:
            lid = inp.get("link")
            if lid is None or lid not in links:
                continue
            l = links[lid]
            inputs[inp["name"]] = [str(l[1]), l[2]]
        vals = list(n.get("widgets_values") or [])
        vi = 0
        for name, extra in _widget_keys(info):
            if vi >= len(vals):
                break
            inputs[name] = vals[vi]
            vi += 1 + (1 if extra else 0)
        api[str(nid)] = {"class_type": cls, "inputs": inputs}
    return api


def outputs_of(hist):
    files = []
    for _nid, out in (hist.get("outputs") or {}).items():
        for key in ("images", "gifs", "videos"):
            for item in out.get(key) or []:
                fn = item.get("filename")
                if fn:
                    files.append(os.path.join(item.get("subfolder") or "", fn).replace("\\", "/"))
    return files




