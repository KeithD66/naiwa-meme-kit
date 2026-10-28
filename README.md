# 奶蛙恶搞短视频创作套件 · naiwa-meme-kit

创作「奶蛙」（大笑奶龙 / 变异奶龙）主题中文抽象恶搞短视频的**可复用资源库**——
形象 prompt、梗宇宙角色档案、热梗库、音频来源、三视图与 3D 模型、图生视频工作流、二创版权红线。

> **铁律**：所有形象素材来自开源库或网络现成资源，**本仓库不自行创作任何形象**。
> 同样地，本仓库**不内置第三方二进制素材**，改为脚本按需拉取（原因见 [SOURCES.md](SOURCES.md)）。

## 快速开始

```bash
git clone <本仓库>
cd naiwa-meme-kit
./scripts/fetch-assets.sh        # 拉取上游开源素材到 assets/repos/
```

然后在任意项目里复用这套技能：

```bash
cp -r skill/ <你的项目>/.workbuddy/skills/naiwa-meme-video/
```

## 目录

```
├── README.md                  # 本文件
├── SOURCES.md                 # ⭐ 全部素材来源与许可证对照
├── LICENSE                    # MIT（仅覆盖本仓库的文本与代码）
├── skill/                     # 可复用的 WorkBuddy skill
│   ├── SKILL.md               # 六步创作工作流
│   └── references/
│       ├── characters.md      # 角色档案（奶蛙 + 梗宇宙成员）
│       ├── memes.md           # 2026 热梗库
│       ├── audio.md           # 音频与 BGM 来源
│       ├── ip-assets.md       # 三视图 / 3D / LoRA / 图生视频
│       └── licensing.md       # 版权红线
├── prompts/
│   └── naiwa-character-prompts.md   # ⭐ 形象 prompt 速查卡（可直接喂模型）
├── scripts/
│   └── fetch-assets.sh        # 一键拉取上游素材
└── assets/                    # 素材落地目录（repos/ 不入库）
```

## 奶蛙长什么样

**金黄梨形 3D 吉祥物**：头身一体无脖子、灰绿色圆形大眼 + 黑瞳、一字横嘴、乳白色大肚皮、橄榄褐四指手、三趾大脚。
招牌动作是捧腹大笑配「齁齁齁」。

完整特征 prompt 见 [`prompts/naiwa-character-prompts.md`](prompts/naiwa-character-prompts.md)。

## 六步工作流

1. **定角色** — `skill/references/characters.md` + `prompts/`
2. **选热梗** — `skill/references/memes.md`（含「雷霆舞步」流派）
3. **取形象** — LoRA（`NAIWA`）/ 三视图 / `.obj` / 现成素材
4. **配音** — `skill/references/audio.md`
5. **成片** — 参考帧 → 图生视频 → 大笑收尾 → 剪辑
6. **过版权** — `skill/references/licensing.md`

## AI 视频角色一致性

要让奶蛙「转身不崩」，靠三视图 / 3D 参考帧：

- **三视图**：[neta.art 奶蛙宇宙](https://neta.art/app/milk-frog-wiki) 官方 front / side / back
- **3D 模型**：嘉立创 3D 模型库 `奶蛙.obj` 等 5 款，导入 Blender 渲任意角度当参考帧
- **LoRA**：Civitai #2802348（触发词 `NAIWA`）、#3006514（触发词 `naiwa`）

详见 `skill/references/ip-assets.md`。

## 梗宇宙成员

奶蛙、水豚噜噜、豆包、牛来、美团袋鼠、奶龙/奶包/奶鲸/纸人——
特征与版权风险见 `skill/references/characters.md`。

**⚠️ 提醒**：水豚噜噜（元气造物）、豆包（字节跳动）、美团袋鼠（美团）、牛来（电影 IP）**均有官方版权方**，仅可玩梗二创，勿商用。

## 版权

- 本仓库文本与代码：**MIT**
- 素材：见 [`SOURCES.md`](SOURCES.md)。核心原则——**代码 MIT ≠ 图片可商用**；
  上游 `naiwa-pet`（438 帧）与 `awesome_pets` 无 LICENSE 文件，**仅本地使用，勿再分发**。

## 待办

- [ ] 「唐牛」形象确认后建档（现检索到的均为《食神》反派或短剧角色，不像 3D 抽象形象）

---

用爱发电的二创工具箱。玩梗归玩梗，别商用别人的 IP。
