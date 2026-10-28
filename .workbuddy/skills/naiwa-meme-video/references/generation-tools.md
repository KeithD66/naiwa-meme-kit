# 本地制作与火山方舟任务

统一视频镜头请求、供应商适配接口与草稿/主力/精修档位见
[VideoPipeline](video-pipeline.md)。三档路由按用户偏好配置，供应商未实现的联网适配器明确保留为候选。
角色3D资产生成与视频生成分别接入。

## 先辨别模型类型

`hyper3d-gen2-260112` 是影眸的静态 **3D** 模型，支持1–5张图片与英文补充描述，
可选 Quad 四边面或 Raw 三角面。项目按现成角色图准备请求，不用机械兽纯文案重造角色。
多图来源、原生四边面验收、独立额度及本地请求准备见 [Hyper3D接入](hyper3d.md)。
TAPose只控制重建姿态，不代表已有骨骼；生成的GLB也不保留原生四边面。

`doubao-seed3d-2-0-260328` 同样是图生 **3D**：单张真实参考，文本仅传
`--subdivisionlevel high --fileformat glb` 等规格参数，输出带纹理/PBR的静态模型 ZIP。
角色版本复用、15万 token 批次控制、模型审计、GLB/OBJ打包与24视图流程见
[Seed3D基础库](seed3d-foundation.md)。当前用户已授权本地试制；依据账本和授权执行，无需重复确认。
已有同版本主本时直接本地渲染参考，不按镜头重复调用。不同3D供应商的参数不可混用。

`hitem3d-2-0-251223` 是图生 **3D**，成功结果是 `content.file_url`，不是讲解视频。
文本项只接受 `--resolution`、`--ff` 等模型参数；把剧情写进去不会让它生成视频。
`--ff 2 --resolution 1536pro --request_type 3` 请求带纹理 GLB。
来源：[火山方舟创建3D任务](https://ark.volcengine.com/region:cn-beijing/docs/shumei-create-3d-generation-task-api)。

Seedance 才是视频模型。模型列表可见不等于已开通推理服务；不要为了适配错误示例反复创建计费任务。
视频任务的图片可用公网URL或文档支持的Base64附件，但仍须先符合本项目身份参考条件。
来源：[创建视频任务](https://ark.volcengine.com/region:cn-beijing/docs/create-video-generation-task-api)。

## 凭据与异步任务

`scripts/ark-task.py` 从 `ARK_API_KEY` 或 `ARK_API_KEY_FILE` 读取凭据。密钥文件放项目外，
不写入请求JSON、命令输出、Git或模型交接文档。API记录放 `assets/private/ark/`，
其中的临时签名下载URL也不作为公开资料入库。只向官方固定主机发送鉴权头。

```bash
ARK_API_KEY_FILE=/secure/local-key python3 scripts/ark-task.py submit \
  --request production/tcp-handshake/hitem3d-request.json \
  --record assets/private/ark/submit.json
ARK_API_KEY_FILE=/secure/local-key python3 scripts/ark-task.py get TASK_ID \
  --record assets/private/ark/status.json
```

`submit` 会实际创建可能计费的任务，须在当前用户授权范围内使用。POST网络超时不自动重试，
因为服务端可能已收单；先查已有任务再决定。GET查询可以按需重试。
成功后及时下载结果并记录哈希；`running` 不能写成已获得模型或视频。

## 3D参考重建不是“网络原版模型”

从已核验的现成图做Seed3D、Hitem3D或Hyper3D重建属于**衍生候选**，不是下载到了网络原型的官方3D资产。
保存 `derived_from_asset_id / source_sha256 / model / task_id / output_sha256`。
渲染后逐角度比较眼睛、嘴、腹斑、手脚与比例；存在漂移就不当默认身份参考。
单张图推测出的背面不能冒称原始网传背面已获验证。第三方原图的使用边界也不会因重建消失。
Seed3D 的 `character-card.json` 记录模型变换、哈希和能力，不构成身份或媒体授权。
其 GLB 为 PBR 材质主本，OBJ 交换件有明确的材质损失；相机转台不包含角色动画或骨骼绑定。

可用本地隔离环境渲染已有GLB，工具只做等比构图与相机旋转，不重绘角色：

```bash
python3.12 -m venv .venv-render
.venv-render/bin/pip install -r requirements-render.txt
.venv-render/bin/pip install --no-deps --upgrade PyOpenGL==3.1.10
.venv-render/bin/python scripts/render-reference.py assets/private/model.glb \
  --view front --size 768 --output assets/private/references/model-front.png
```

该隔离环境的旧pyrender声明锁定PyOpenGL 3.1.0，但Python 3.12纹理渲染需实测可用的3.1.10覆盖；按上面两步安装，避免解析器冲突。
`side/back` 默认是相机yaw 90/180度；用 `--yaw-offset` 调整模型朝向后须实际看图确认。旧Hitem3D奶蛙候选使用 -45度偏移，正/侧/背分别为 -45/45/135度；仍保留贴图接缝和推测背面的限制。Seed3D逐件校准，不能照搬旧模型角度。工具依赖本机可用的图形会话，显示休眠时可能无法创建上下文；保持会话可用后顺序渲染；可用 `caffeinate -u -t 45` 包住单张渲染命令，批量渲染需相应延长临时显示断言。
`--self-test` 仅用于普通几何体验证，不是角色素材。

## 现成原片加代码图解

当无合格多角度基准时，科普样片可直接用原片/原帧，包箭头、协议字段与中文字幕由代码绘制。
这条路线保持现成角色像素，不把模型另造的形象冒充网传奶蛙。

```bash
python3 scripts/render-tcp-demo.py --with-cues
```

本地渲染需 Pillow（`requirements-media.txt`）、FFmpeg 和中文字体；可用 `--font` 指定本机 CJK 字体。
TCP案例的分镜在 `production/tcp-handshake/storyboard.json`；视频在被忽略的 `outputs/`。
该渲染脚本不调用生成模型，也不合成旁白或角色笑声；不能将本地剪辑样片标为Seedance生成结果。
