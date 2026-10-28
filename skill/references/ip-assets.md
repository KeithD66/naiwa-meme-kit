# 形象 / 三视图 / 3D 模型来源

> AI 视频要保持角色一致性，关键是"三视图 / 固定形象参考 + 参考图驱动的图生视频"。全部用现成素材。

## 三视图（turnaround）— AI 视频一致性的锚
- **neta.art 奶蛙宇宙**：提供官方锁定的 front / side / back 三视图（"one official turnaround fixes the frog's geometry"），是角色一致性的标准参照。地址：`https://neta.art/app/milk-frog-wiki`（百科）、`https://neta.art/explore/work/en/milk-frog-avatar-wallpaper`（48 头像 + 94 馆藏）。
- **用法**：把三视图作为 image-to-video（图生视频）或 LoRA 推理的首帧/参考帧，保证多角度不崩。

## 3D 模型（可转视角 / 打光 / 渲三视图）
- **嘉立创 3D 打印模型库 · 奶蛙**：`奶蛙.obj` / `奶趴.obj` / `奶蛋.obj` / `奶心.obj` / `奶史.obj`（彩色 + 白色两套，JLC 全彩树脂参数）。
  - 地址：`https://model.jlc-3dp.cn/modelDetail/037262f117974eacb739974e67344c53.html`
  - **用法**：.obj 导入 Blender，固定相机渲出任意角度 → 作为图生视频参考帧，解决"转身就崩"。
- **Sketchfab**：搜 "milk frog" / 3D 蛙类，勾选 Downloadable，优先 CC0 / CC-BY（CC-BY 需署名）。

## 图像生成模型 / LoRA
| 资源 | 底模 | 触发词 | 备注 |
|---|---|---|---|
| Civitai #2802348 Krea2 奶娃奶龙 | Krea 2 | `NAIWA` | V2 更干净，218MB |
| Civitai #3006514 MOSS 多角色 | MOSS-Image | `naiwa` 等 5 个 | 一个 LoRA 出全家同框 |
| 数据集 `XiC1/nailong-dataset` | — | — | 约500张奶龙表情包，可作训练/参考集 |

## 现成图片素材（开箱即用）
- `Nailong-Studio/NaiLong-Universe`：94 名画馆藏 + 44 壁纸 + 33 表情包 + 22 动图 + 30 变体（MIT）。**尚未下载**（网络中断），需要时从 GitHub 拉取。
- `lin-alg/NaiLoong`：社区表情包站（代码 MIT，图片社区共有）。
- `timerring/codex-pet-naiwa`：逐帧动画（idle/waving/jumping/running/waiting/review/failed + 16 方向），可作逐帧参考。

## 图生视频工具
- 抖音 Seedance、即梦、Runway / Pika / 可灵 / Vidu：上传参考帧 + 描述动作，生成奶蛙短视频。
- 工作流：三视图/参考帧 → 图生视频 → 配梗音频 → 剪辑（关键节点大笑收尾）。
