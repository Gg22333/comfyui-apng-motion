# 排错

## 生成阶段

| 症状 | 根因 | 处理 |
| --- | --- | --- |
| `emit_workflow.py` 报「关键帧 KSampler 不足 2 个」 | base 不是三关键帧结构 | 用 `assets/workflow-*.json` 当模板 |
| 报「base 里 LatentInterpolate 是 N 个，必须是 24」 | base 被改过 | 恢复模板或手工补到 24 |
| 报「segs 之和必须 24」 | 段数分配写错 | 3 拍 `8/8/8`、4 拍 `6/7/6/5`、5 拍 `5/6/5/4/4` |
| 报「同一对 latent 上 ratio 有重复值」 | 同一段里撞了同一个小数 | 用 `make_curve.py` 重算（已做全局去重） |
| `VALIDATE FAIL: 三个保存节点没有全接在同一个 batch` | 输出被拆到不同 batch | 三个输出都接 `ImageBatchMulti` 的输出 |

## 运行阶段

| 症状 | 根因 | 处理 |
| --- | --- | --- |
| `--run` 报「服务器缺节点」 | 缺插件 | `doctor.py` 看缺哪个；装 `comfyui-kjnodes` |
| `--run` 卡住 / 一直 pending | 队列里有任务或模型正在加载 | 打开 ComfyUI 看队列 |
| `connection reset` | 本机 HTTP 被拦截或节点定义过大 | 脚本已内置 curl 兜底与 node_schema 回落 |
| 端口冲突 | 上次验证实例没退 | `netstat -ano | findstr :8188` → `Stop-Process -Id` |

## 输出阶段

| 症状 | 根因 | 处理 |
| --- | --- | --- |
| N 帧只剩更少（24 → 19） | 曲线有完全相同的 ratio，Pillow 合并 | 见 `docs/architecture.md` 曲线一节 |
| 只有一张静态 PNG | `images` 只有 1 张 | `ImageBatchMulti` 的 inputcount 必须 24，24 路全接 |
| 成品落在 `output/APNG/` 根目录 | prefix 被旧值覆盖 | 改完 prefix 后 **F5 刷新页面**再 Queue |
| 只有 APNG/WebP，没有 GIF | 没装 VHS | 装 `ComfyUI-VideoHelperSuite` 后重启 |
| 眼睛颜色缓慢变化 | 关键帧写了 `eyes closed` 或光照词变化 | 改 `eyes half closed`，负向加 `color shift, different eye color` |
| 双人一互动就糊 | 用微动档做互动 | 上 ControlNet 骨骼序列 |
| Windows 照片不动 | 它不支持 APNG | 看 GIF，或用浏览器 / BandiView |

## 校验脚本

```bash
python scripts/check_anim.py <file> --expect 24
```

| 字段 | 期望 |
| --- | --- |
| `frames` | 24 |
| `loop` | 0 |
| `identical_pairs` | 0 |
| `diff_avg` | 0.3–3.0（越小越细腻） |
| `color_drift` | < 6（超过说明颜色在漂） |

