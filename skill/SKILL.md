---
name: naiwa-meme-video
description: 创作"奶蛙"（大笑奶龙/变异奶龙）主题的中文互联网抽象恶搞短视频时使用。涵盖角色形象特征与 prompt、梗宇宙成员（奶蛙、水豚噜噜、豆包、牛来、美团袋鼠等）、热梗库、音频与 BGM 来源、三视图/3D 模型获取、图生视频工作流，以及二创版权红线。所有形象素材一律使用开源库或网络现成资源，不自行创作。
agent_created: true
---

# Naiwa Meme Video（奶蛙恶搞短视频创作）

## Overview

创作以"奶蛙"为主角的中文互联网抽象恶搞短视频。目标产出"奶蛙雷霆视频"一类：奶蛙（及梗宇宙成员）+ 热梗题材 + 魔性音频 + 反差/大笑收尾。

**铁律：所有形象、音频、梗素材一律来自开源库或网络现成资源，绝不自行创作形象。**

## 快速开始

```bash
./scripts/fetch-assets.sh      # 拉取上游开源素材到 assets/repos/
```

本仓库**不内置任何第三方二进制素材**（原因见 `SOURCES.md`）。

## 创作工作流

1. **定角色与动作** — 读 `references/characters.md` 取角色特征，`prompts/naiwa-character-prompts.md` 取现成英文 prompt。
   视觉基准：黄梨形身体、奶油色大肚皮、灰绿色圆形大眼、一字横嘴、3D 卡通质感。
2. **选热梗做题材/BGM** — 读 `references/memes.md`，挑当月热梗或"雷霆舞蹈"流派模板。
3. **取形象素材** — 读 `references/ip-assets.md`：
   - 出图 → Civitai LoRA（触发词 `NAIWA` / `naiwa`）
   - 多角度一致 → 嘉立创奶蛙 `.obj` 导入 Blender 渲参考帧，或 neta.art 三视图
   - 现成图 → `assets/repos/`（先跑 fetch-assets.sh）
4. **配音** — 读 `references/audio.md`，用现成梗音频，不自行合成冒充。
5. **成片** — 三视图/参考帧 → 图生视频（Seedance / 即梦 / 可灵 / Runway 等）→ 关键节点大笑收尾 → 剪辑。
6. **过版权** — 发布前对照 `references/licensing.md` 确认素材授权与形象风险等级。

## References（按需加载）

- `references/characters.md` — 角色档案：奶蛙 + 梗宇宙成员特征、英文 prompt
- `references/memes.md` — 2026 热梗库：来源 / 玩法 / 适配场景
- `references/audio.md` — 音频与 BGM 来源
- `references/ip-assets.md` — 形象 / 三视图 / 3D 模型 / LoRA / 图生视频工具
- `references/licensing.md` — 版权红线与各形象风险等级

## 复用方式

把整个 `skill/` 目录拷到任意项目的 `.workbuddy/skills/naiwa-meme-video/`，即可在该项目下唤起本技能。

## 关键提醒

- 用户口中的"奶娃" = 奶蛙。
- "奶蛙雷霆视频"指奶蛙套"唐佳琪雷霆舞步"舞蹈流派的二创（见 memes.md）。
- ⚠️ "唐牛"形象尚未确认，涉及唐牛的需求先向用户要参考图。
