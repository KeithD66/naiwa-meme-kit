# 奶蛙恶搞短视频创作套件 · naiwa-meme-kit

把网络流传的奶蛙、固定原声和联动角色整理成视频模型能接收的**真实素材交接**：
先检索现成文件，再核对身份和音源，最后绑定附件、动作与剪辑节奏。

本库针对奶蛙雷霆、抽象恶搞及含奶蛙的中文科普短视频。角色素材与梗原声均来自可追溯的现成资源；
不从文字重新设计奶蛙，不合成声音冒充原作。文字描述和 LoRA 触发词只辅助检查，不能替代图像附件。

## 快速开始

需要 Git、Bash、Python 3。`ffprobe` 可补充时长、尺寸、采样率等元数据；没有它仍可建立基本索引。

```bash
git clone https://github.com/KeithD66/naiwa-meme-kit.git
cd naiwa-meme-kit
./scripts/fetch-assets.sh --list
./scripts/fetch-assets.sh
python3 scripts/library.py index
python3 scripts/library.py doctor
python3 scripts/library.py preview
```

`fetch-assets.sh` 无参数时拉取其列出的上游仓库及固定哈希精选清单。媒体保留在被 Git 忽略的
`assets/repos/` 与 `assets/private/curated/`。已有完整仓库保留本地版本，不自动覆盖修改或更新到最新。
脚本不运行上游桌宠、安装器或网站代码。`preview` 输出本地图册 HTML，可用浏览器看图和试听。

只补充原图库与精选素材：

```bash
./scripts/fetch-assets.sh wallpaper curated
python3 scripts/fetch-curated.py --dry-run
```

网络慢时可给单次命令设置 `GITHUB_PROXY`。原始来源与内容哈希仍保留在清单中，代理不改变媒体权利。
下载失败会返回非零状态；查看下载报告后重跑，不能把失败项写成已到位。

## 查图、查声音和检查实际文件

```bash
python3 scripts/library.py search --character naiwa --kind image --local
python3 scripts/library.py search --character naiwa --kind audio --local
python3 scripts/library.py search --character naidan --kind audio --local
python3 scripts/library.py search --query 捧腹 --limit 10
python3 scripts/library.py inspect naiwa-frame-0000
```

- `index` 根据本地文件、上游目录与精选清单重建 `library/catalog.json`，记录来源、路径、哈希及审核状态。
- `search --local` 只查实际落地项；未下载的远程目录会明确显示为 `remote_index`。
- `inspect` 显示完整单条记录。先打开实际文件看图／试听，不能只相信标题、文件名或目录标签。
- `doctor` 检查文件哈希、存在状态与索引中的仓库版本；通过不代表身份、录音版本或发布许可已通过。
- `preview` 生成图册；浏览或播放本身不会自动把审核字段变为通过。

审核结论可以绑定文件哈希保存；重建索引时，文件变化会使旧审核失效：

```bash
python3 scripts/library.py review naiwa-frame-0000 \
  --visual visual_checked --identity-bundle-id naiwa-pet-network-3d \
  --reference-role neutral --note '实际查看后的具体依据'
python3 scripts/library.py index
```

这条命令只是记录真实看图结果，不能代替看图、试听或媒体授权。

声音先按 `library/audio-cues.json` 的 cue 查候选，再锁定具体录音及入出点。
例如 `naiwa.laugh`、`naiwa.hola_ganbadie`、`naidan.andi` 各有自己的归属和版本问题。
**andi 属奶蛋语音表；它不是奶蛙默认口癖。** 未试听的文件一律是候选，不能称为已确认原版。

## 给视频模型交接

先看 [身份锁定](skill/references/identity-lock.md) 与
[提示模板](prompts/naiwa-character-prompts.md)，按 `templates/video-brief.json` 准备镜头信息。
可以建立一个只引用现成素材的草案：

```bash
python3 scripts/library.py handoff \
  --character naiwa \
  --reference naiwa-frame-0000 \
  --reference naiwa-frame-0200 \
  --audio nai-hub-nailong_laugh \
  --mode existing-edit \
  --recipe existing-loop-remix \
  --output production/handoffs/naiwa-draft
```

输出 `brief.json` 和 `MODEL-HANDOFF.md`，列出实际文件、SHA-256、角色及阻塞项。
`handoff` **始终只产 `draft_only`，`generation_allowed` 为 false**；不调用生成模型、
不剪辑、不上传附件，也不发布。示例笑声未试听时会保留相应 blocker。
后续工具仍须真正上传或读取文件；把本地路径写进 prompt 不代表模型收到了图片。

制作范围以用户当前授权为准。处理具体素材缺口、实际看图／试听和工具能力后再执行；
不能手改布尔值或清空 blockers 冒充已核验。

多人交接可重复 `--character`，并明确每个素材归属，不将奶蛋声音分给奶蛙：

```bash
python3 scripts/library.py handoff \
  --character naiwa --character naidan \
  --reference naiwa=naiwa-frame-0000 \
  --reference naidan=eco-asset-naidan-existing-idle-png \
  --audio naidan=nai-hub-andi \
  --position naiwa=left --position naidan=right \
  --mode existing-edit --recipe call-response-duo \
  --output production/handoffs/duo-example
```

仍未看图或试听的素材会作为 blocker 留在草案里；相机方位和左右站位不是身份认证。

## Codex + VideoPipeline 分层编排

Codex统一准备镜头和真实角色附件，通过 `VideoPipeline` 按工作档位路由：

| 档位 | 有序候选 |
|---|---|
| 草稿 `draft` | 海螺/Lite → Grok → Veo |
| 主力 `standard` | 可灵720p → Wan → 即梦 |
| 精修 `polish` | Seedance → Veo Fast |

顺序是本项目的工作偏好，不是画质或价格排名，也不会自动触发付费回退。
`video_pipeline` 包提供统一请求、角色版本/文件哈希绑定、能力匹配和供应商适配器接口。
当前CLI离线列路由与规划镜头；供应商的具体模型及联网适配器仍需配置和验证。

```bash
python3 scripts/video-pipeline.py providers
python3 scripts/video-pipeline.py plan --request templates/video-pipeline-request.json
```

配置在 `library/video-providers.json`；示例使用本机已有的奶蛙同版本3D渲图，缺少媒体时报告缺项。
原声独立安排在后期，角色3D模型不冒充视频生成模型。详见
[VideoPipeline工作流](skill/references/video-pipeline.md)。

## 当前角色一致性边界

现成原序列提供闭嘴与捧腹笑等本地参考，可用于本地原片剪辑、定格和重排。
Seed3D 新增了同源图像重建与多角度渲染候选。每个版本仍须实看身份、推断背面和使用范围，
角色卡与技术检查不会自动认证网传原版、官方许可或视频动作稳定性。

- Neta 现成三视图候选有正侧标签对调、眼色与嘴形差异，不作为默认生产参考。
- `wallpaper/emotes/奶蛙-立绘-站立.png` 实际看图是奶龙，已作为错误角色排除；索引写“奶蛙”也不能免检。
- 嘉立创给定页面未核实到原文所称的具体奶蛙 `.obj` 文件或下载许可；不把它写成已有模型。
- 16 个注视方向、正面照与连续捧腹帧都不能自动算成角色三视图。
- 图生视频先取得并核验同版本三视图，或用取得许可的模型渲参考帧；工具必须能接收真实附件。
- 工具只能纯文字生视频时，不降级为让它重造奶蛙；继续使用现成原片剪辑或整理缺项。

LoRA 已查到模型卡线索和兼容条件，权重未默认安装。写 `NAIWA` 不会让视频服务自动加载 LoRA。
细节见 [素材与权重](skill/references/ip-assets.md)。

## 可复用的 Seed3D 角色基础库

先选角色版本和来源哈希，再复用静态主本派生参考；不为每个镜头重新生成形象。
本批奶蛙、奶蛋、噜噜社区版与肥嘟嘟社区版四项 high/GLB 本地重建均已完成下载与打包，
API合计报告120,000 token；共保存96张视图、96张轮廓mask和4段相机转台。
结果与限制见 [本批交付记录](production/seed3d/batch-report.json)，后续累计量仍读当前账本。
奶蛙候选的嘴形略弯等差异仍保留，不覆盖原帧基准；社区版也不视为官方认证模型。

工具链：准备现成图 → 受控任务/下载 → 离线模型审计 → 标准化打包 → 多角度渲染。
保存原 ZIP、PBR GLB 主本、diffuse OBJ 交换件及材质损失报告，工作坐标为高2个归一化单位、
+Y向上、校准后+Z正面、最低几何为pivot。默认渲出24视图、24轮廓mask和6秒**相机**转台，
不包含骨骼或角色动作。派生新视角无需再调用推理。

```bash
python3 scripts/seed3d-batch.py status
ARK_API_KEY_FILE=/secure/local-key python3 scripts/seed3d-batch.py sync seed3d-naiwa-v1
python3 scripts/seed3d-batch.py download seed3d-naiwa-v1
```

凭据放环境或项目外临时文件，签名下载URL只保留在忽略的私有目录。本批上限为5个任务槽位、
150,000 token；2M是用户声明额度，不是实测账号余额。本批四项各报告30,000 token，
合计120,000 token；声明额度减去本批为1,880,000 token，不代表已查询账户余额。
POST超时保留预留、不重提；运行中不能DELETE刹车。
恢复命令、完整打包示例与审核规则见 [Seed3D长期工作流](skill/references/seed3d-foundation.md)。
现有媒体及受限衍生包仅本地参考；发布、再分发和商用权利仍按具体来源核对。

## Hyper3D 四边面候选接入

`hyper3d-gen2-260112` 可补充1–5张图输入和Quad四边面编辑底模；TAPose仅请求静态姿态，
不包含骨骼或角色动画。用户确认有独立免费额度并授权开始后，同一奶蛙原图的Quad
50k/PBR/HighPack/OBJ对照已完成一次，API报告30,000 tokens、预留归零。原图WebP按相同
RGBA像素转PNG，已有Hitem3D与Seed3D作为同源对照；独立免费额度的总量和实际余额未核验。

实际产物是直接返回的OBJ，共43,947个原生四边面（100%，原生三角面和五边以上n-gon均为0），
等价三角形87,894个。按原始顶点索引统计为单连通分量，无边界边或非流形边。
文件有UV，却没有材质、颜色、MTL引用或贴图；**请求PBR/HighPack不代表本次已交付纹理**。
实际对照源图和灰预览后还发现：源图只有捧腹双臂，生成件保留捧腹臂的同时多出一对展开臂，
成为四臂。身份结论为 **`rejected_extra_limbs` + `missing_materials`**，拒绝作默认奶蛙模型或
视频身份参考。`TAPose=false` 未避免额外肢体，原因未确定；全Quad拓扑通过不能覆盖身份失败。
本件保留为失败样本/benchmark，不追加重试；视觉证据见`production/hyper3d/visual-reviews.json`。

```bash
.venv-render/bin/python scripts/hyper3d-request.py prepare hyper3d-naiwa-quad-v1 --dry-run
.venv-render/bin/python scripts/hyper3d-request.py prepare hyper3d-naiwa-quad-v1
```

以上仅复现离线准备，不会再次提交。已有任务`cgt-20261029144646-854ct`及独立账本
`production/hyper3d/usage-ledger.json`，不要重复POST。官方按量单价1.80元/成功任务，
不能据此声称本次已扣现金；该模型额度与Seed3D分别计算。
原生件保留在`assets/private/hyper3d/models/hyper3d-naiwa-quad-v1/files/model.obj`，
其原始四边面与`geometry-preview-package/`中的三角化灰预览分开。
本地图册为`assets/private/hyper3d/index.html`；`python3 scripts/build-hyper3d-library.py`
可从已下载结果重建索引与图册，不调用推理。24视图、24 mask及转台均作几何失败样本检查。
文档说下载ZIP，本次却直接得到OBJ，未来按实际响应检查，不能据一次推断所有格式。
用法、验收与限制见
[Hyper3D工作流](skill/references/hyper3d.md) 和 `library/hyper3d-plan.json`。

## 角色生态与雷霆节奏

[角色档案](skill/references/characters.md)和 [生态方法](skill/references/ecosystem.md)
覆盖奶蛙、奶蛋、噜噜、胖袋鼠、牛来及待确认的其它名称。奶粉保留角色／粉丝双义；
唐牛不自动改成牛来，奶鼠不自动改成美团老鼠。每个配角分别绑定自己的现成参考与声音。

`library/recipes.json` 提供呆脸→雷霆→破功、口癖接力、三次升级、假结束返场等剪辑结构。
[声画编排](skill/references/editing-language.md)规定镜头与声音的落点，
[梗与证据](skill/references/memes.md)区分可用线索和待核验热点。
唐嘉琦舞步的 BGM 候选是《MONTAGEM ALQUIMIA》，具体速度版本与许可仍须核对；
旧资料中的《Monica / jim okimia》不作为已确认曲名。

## 目录与复用

| 路径 | 用途 |
|---|---|
| `skill/` | 技能入口与按需加载的角色、身份、音频、节奏、版权参考 |
| `library/` | 角色路由、cue、配方、固定下载清单与生成的本地目录 |
| `research/` | 原始来源核对、版本、证据状态与未解决项 |
| `prompts/`、`templates/` | 动作提示、制作 brief 与模型交接模板 |
| `scripts/` | 拉取、索引、检查、检索、图册与交接工具 |
| `video_pipeline/` | 视频统一请求、分层路由与供应商适配抽象 |
| `assets/repos/`、`assets/private/` | 本地第三方素材，均不入 Git |
| `production/` | 每条视频的策划、审核与制作记录 |

本项目已把 `skill/` 同步到 `.workbuddy/skills/naiwa-meme-video/`。复用到其它项目时，
保留技能引用的 `library/`、`scripts/`、`templates/`、`prompts/` 与 `research/`，
并从该项目根目录执行工具；只复制 SKILL.md 不能带走实际素材或工具。

本仓库自己的代码与文档使用 MIT。第三方角色、图片、音频、模型各看实际权利来源；
公开流传、非商用和包装仓库开源均不是统一授权。详见 [SOURCES.md](SOURCES.md) 与
[版权边界](skill/references/licensing.md)。无 LICENSE 及受其限制的衍生媒体仅本地参考，不再分发。

## TCP科普验证案例

`production/tcp-handshake/` 保存26秒分镜、协议字段与制作记录。
`python3 scripts/render-tcp-demo.py --with-cues` 用现成奶蛙帧、原录音和代码图解输出本地MP4；
不靠文字另造角色，不冒称Seedance生成结果。`hitem3d` 是3D模型，
与视频生成的区别、异步任务与本地GLB渲染见
[生成工具说明](skill/references/generation-tools.md)。密钥与生成媒体不进入Git。

Seed3D 已生成的角色包与审核结论可在本地 `assets/private/seed3d/index.html` 查看；
注册表是 `library/seed3d-registry.json`，它区分API成功、文件齐全与视觉是否可用。
`library.py index` 已同时纳入这些资产；mask、texture与真正的参考图分开检索。
需要复用时先从现有版本渲染，不为每个镜头新建网格。
