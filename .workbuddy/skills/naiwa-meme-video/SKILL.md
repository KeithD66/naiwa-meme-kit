---
name: naiwa-meme-video
description: 制作奶蛙及其联动生态的中文抽象雷霆、搞笑或科普短视频时使用。检索现成角色与固定原声，复用同版本3D参考，核验身份并绑定真实附件交接给视频或剪辑工具；不从文字重造形象，不仿配原作声音。
---

# 奶蛙雷霆视频工作流

目标是让观众认出同一只网传奶蛙和熟悉原声。先选现成素材，再写动作与节奏。
当前用户授权优先；技能不额外要求重复确认已授权的本地制作，也不自动授权发布或商用。

## 先定位项目与素材

本技能依赖项目根目录的 `library/`、`scripts/`、`prompts/`、`templates/`、`research/`。
安装在 `.workbuddy/skills/naiwa-meme-video/` 时仍以项目根执行命令，不把技能目录当素材根。
复用到其它项目要一并保留这些依赖，第三方媒体仍通过获取脚本落地。

```bash
./scripts/fetch-assets.sh --list
./scripts/fetch-assets.sh wallpaper curated
python3 scripts/library.py index
python3 scripts/library.py search --character naiwa --local
python3 scripts/library.py inspect naiwa-frame-0000
```

首次完整拉取可不传目标。下载与哈希通过只证明文件到位，不证明它就是目标角色或声音。

## 核心约束

- 角色形象、梗原声、舞步素材取自可追溯的现成来源。禁止仅靠文字生成一个“差不多的奶蛙”，
  禁止用合成笑声或仿配声音填缺。字幕、剧情与科普信息可按任务编写。
- 必须查看真实图片／原片和试听声音。网络目录、文件名、LoRA 触发词、本地路径都不能替代实际附件。
  已发现 wallpaper 的“奶蛙-立绘-站立.png”实际为奶龙；不得将标题命中直接升级为身份通过。
- 每条视频先选一个角色版本；网传 3D、像素、艺术改绘、异色版分组，不能混作同一身份。
- AI 图生视频先有经核验的同版本三视图，或从取得许可的 `.obj` 渲参考帧；
  16 注视方向与捧腹原序列不自动等于三视图。Seed3D 已提供本地重建与多角度候选，
  仍须检查身份、推断背面与具体使用范围，不自动升级为默认或官方基准。
- 已有合适的角色 3D 版本时，固定版本及源哈希，本地派生参考，不为每个镜头重新重建。
  转台只有相机转动，不代表模型已绑定、跳舞或具备角色动作。
- 工具不能收参考附件时，不偷偷转纯文字生视频。可按当前授权改用现成原片剪辑、定格与重排。
- 素材与其许可逐文件记录。无 LICENSE 及其受限衍生媒体仅本地参考，不打包再分发；
  代码 MIT／Apache、公开流传、非商用均不自动放行媒体。

## 按本次工作加载参考

| 任务 | 必读资源 |
|---|---|
| 选角色、纠正同名与串角色 | [characters.md](references/characters.md)、[ecosystem.md](references/ecosystem.md)、`library/characters.json` |
| 固定奶蛙身份或做图生视频 | [identity-lock.md](references/identity-lock.md)、[ip-assets.md](references/ip-assets.md)、`prompts/naiwa-character-prompts.md` |
| 找声音、选现成录音版本 | [audio.md](references/audio.md)、`library/audio-cues.json` |
| 选梗、编排炸裂反差 | [memes.md](references/memes.md)、[editing-language.md](references/editing-language.md)、`library/recipes.json` |
| 接入火山方舟、3D参考或本地科普样片 | [generation-tools.md](references/generation-tools.md) |
| Seed3D受控重建、复用角色模型与多角度参考包 | [seed3d-foundation.md](references/seed3d-foundation.md)、`library/seed3d-plan.json` |
| Hyper3D同图对照、真实多图输入与原生四边面候选 | [hyper3d.md](references/hyper3d.md)、`library/hyper3d-plan.json` |
| Codex统一视频编排、草稿/主力/精修路由与适配器接入 | [video-pipeline.md](references/video-pipeline.md)、`library/video-providers.json` |
| 准备对外使用 | [licensing.md](references/licensing.md)、项目 `SOURCES.md`、所选媒体原始 NOTICE |

奶粉保留角色／粉丝双义；唐牛不改称牛来；奶鼠不自动等于美团老鼠。
奶蛋的 andi 不归入奶蛙默认口癖。未知角色先继续查来源，不凭名设计。

## 从检索到可审查交接

1. 用 `library.py index/search/inspect` 找本地素材与对应来源；必要时补下载再重建索引。
2. 实际看图／看片／试听，用 `library.py review` 保存与文件哈希绑定的结论；文件变化后旧结论失效。记录角色版本、匹配与许可状态；
   远程索引、已下载、已查看、身份匹配、声音匹配、可发布分别判断。
3. 用 `templates/video-brief.json` 和镜头模板写画面、动作参考、字幕、cue、入出点与当前缺口。
   向工具上传真实文件，并分开绑定身份、动作和背景；多人分别绑定。
4. 用 `library.py handoff --help` 建立交接草案。`existing-edit` 引用现成原片，
   `image-to-video` 还要核验多角度前置。多人可重复 `--character`，用 `--reference 角色ID=素材ID` 和 `--audio 角色ID=素材ID` 分别绑定。输出仅 `draft_only`，不执行生成、剪辑或发布。
5. 按当前用户授权与实际工具能力处理 blockers，再进入制作；不靠编辑状态字段绕过缺项。
   生成后按 `identity-lock.md` 检查首帧、动作极值、遮挡重现和尾帧；不合格就缩动作、拆镜头或回到现成片段。
6. 以 `editing-language.md` 检查声画落点、断乐、变焦和循环；音轨仍是现成录音，
   不因“更炸裂”随意换曲、造口癖或把音量推到削波。

`python3 scripts/library.py doctor` 检查索引完整性；`preview` 生成本地图册。
二者都不会自动批准角色、声音、生成权限或对外分发。
