# 奶蛙短视频项目工作流

源技能为 `skill/SKILL.md`，项目安装副本为 `.workbuddy/skills/naiwa-meme-video/`。
更新源后同步副本并用 `diff -qr` 检查。所有工具、library、prompts 和 templates 路径均相对本项目根目录。

## 当前授权与范围

最新请求已授权使用 `doubao-seed3d-2-0-260328` 与用户声明的 2M 免费额度，为生态库
建立可复用的图像约束 3D 资产、材质/尺度/相机约定与参考帧流程。分批试制并登记实际用量；
先验证单件再扩批，保留余量，不开通付费服务或盲目重提超时任务。额度台账是本地累计，
不能冒称 API Key 可读取账户剩余免费额度。当前授权允许现成参考的本地重建与检查，
不因历史脚本确认状态重复请示。仍不从文字重设计角色，不将重建候选冒充网传原始模型。
此批控制器限制最多 5 个任务槽位、150,000 token；凭据只从环境或项目外临时文件读取。
任务和预算恢复用 `seed3d-batch.py status/adopt/sync/download`，不重复 POST、不靠 DELETE 中止运行任务。

用户随后追加 `hyper3d-gen2-260112` 供项目使用。它补充真实多图输入和原生Quad四边面候选，
仍以现成角色图约束身份，额度与Seed3D独立核算；未声明该模型账号余额。
离线请求准备见 `scripts/hyper3d-request.py`、`library/hyper3d-plan.json` 与
`skill/references/hyper3d.md`。准备器不提交任务；原生Quad与三角化预览件分开保存。

用户已要求扩充素材库，并进一步授权制作奶蛙 TCP 科普视频。按最新请求继续所需的本地研究、
策划和制作，不再把早期 `production/001-script.md` 的脚本确认关口当成永久制作禁令。
已有授权无需重复询问；用户后续指令优先于历史任务状态。用户当前要求写入 VideoPipeline
分层编排并同步整个项目，授权将项目代码、配置、研究记录和文档提交并推送到本项目 GitHub。
第三方二进制素材继续保留于忽略目录；视频公开发布与素材再分发仍需对应授权。
生成服务的文件上传按最新请求、附件授权与素材使用范围判断，不重复索取已有授权。

制作授权不补足缺失素材或媒体权利。Seed3D 的同源重建和多角度包是本地候选，
逐版核验身份、相机与来源权利后选择具体制作路线；不自动认证全库 AI 视频已就绪。
现成原片、定格与重排仍可用于保持角色和现成梗原声。

## 执行入口

先读 `skill/SKILL.md`，再按任务加载相关参考：

- 角色、同名与多人生态：`characters.md`、`ecosystem.md`、`library/characters.json`。
- 角色一致性：`identity-lock.md`、`ip-assets.md`、`prompts/naiwa-character-prompts.md`。
- Seed3D角色主本、预算恢复与多角度复用：`seed3d-foundation.md`、`library/seed3d-plan.json`。
- Hyper3D同图对照、多图来源与四边面原件验收：`hyper3d.md`、`library/hyper3d-plan.json`。
- Codex统一编排、草稿/主力/精修档位与供应商能力匹配：`video-pipeline.md`、`library/video-providers.json`。
- 固定原声：`audio.md`、`library/audio-cues.json`。
- 雷霆梗与节奏：`memes.md`、`editing-language.md`、`library/recipes.json`。
- 对外用途：`licensing.md`、`SOURCES.md` 和实际来源 NOTICE。

上述 md 参考位于 `skill/references/`。具体命令见主 README：
`fetch-assets.sh --list`、`fetch-assets.sh wallpaper curated`、`library.py index/search/inspect/doctor/preview/handoff`。
`handoff` 只输出交接草案，不执行生成、剪辑或发布。

## 必须保留的用户要求

- 用网络流传版奶蛙的真实现成素材；禁止凭名称或纯文字重造形象、合成仿原作配音。
  角色描述用于核对，不替代实际上传的图片／视频附件。
- 奶蛙固定身份要点为金黄梨形、无独立脖子、灰绿圆眼黑瞳、细横嘴、乳白腹斑及原有手脚结构。
  笑态按同一来源的真实开口／闭眼参考，不能因横嘴约束而禁止招牌大笑。
- 每个角色独立绑定参考、动作和声音；奶蛋 andi 不默认归奶蛙，唐牛不改称牛来，奶粉先消歧。
- AI 视频前先核验现成三视图，或取得许可的 `.obj` 渲参考帧。正面照、连续笑帧、16注视方向不是三视图。
  Neta 现有候选有标签／形象问题；嘉立创具体模型本次未核实，不写成已经到位。
- 复用 Seed3D 时固定同角色、同版本及源哈希；GLB 为 PBR 主本，OBJ 为有材质损失的 diffuse 交换副本。
  工作模型高 2 个归一化单位、Y-up、校准后 Z-front、最低几何为 pivot，不宣称真实尺寸。
  24 视图/24 mask/相机转台可本地派生，不再消耗推理额度；没有骨骼动作或官方身份认证。
  首个奶蛙候选嘴形略弯、单图推断的背面，以及噜噜/肥嘟嘟社区版标签均须保留，不覆盖旧基准。
- `wallpaper/emotes/奶蛙-立绘-站立.png` 已看图确认为奶龙，禁止作为奶蛙身份参考；
  上游标题与目录只是检索线索，不能覆盖实际视觉结论。
- 本地路径、URL 或 LoRA 触发词不是工具已收到附件／加载权重的证明；工具不支持参考时不改用纯文字造角色。
- 固定梗音频逐条选现成文件并试听、记录入出点；未试听不标 `auditioned_match`，元数据读取不等于听过。
- 第三方二进制保留于被忽略的 `assets/`。无 LICENSE 及受其限制的衍生素材仅本地参考，不再分发。
  `codex-pet-naiwa` 明确排除第三方媒体，`NaiLoong` 的桌宠也继承该来源问题。
- 代码 MIT／Apache、公开流传、非商用都不自动赋予媒体或角色权利。水豚噜噜权利入口为铁罐（北京）文化传媒有限公司；
  豆包、美团袋鼠、牛来等按用户要求仅非商用玩梗，具体用途仍逐件核对。

## 实际状态与交付

下载清单、`library/catalog.json` 与研究 JSON 分别记录固定文件、当前本地状态与检索证据。
远程索引、已下载、已查看、身份匹配、声音匹配和许可通过分开记录；不用文件名、目录或布尔值代替核验。
`doctor` 只查完整性，`preview` 不自动批准，`handoff` 始终 draft_only 并保留 blockers。
完成交接后仍要检查实际附件、当前授权、工具能力和具体素材缺项，再执行已授权的制作。

每条视频记录镜头、角色动作、字幕、梗、BGM、录音文件与入出点。科普内容需核实概念和图示；
制作记录应能追溯到原文件及其哈希。未经用户明确授权，不发布、上传公开素材包或推送 GitHub。
