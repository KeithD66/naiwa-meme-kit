# Seed3D 角色基础库：先复用，再重建

本流程用于将已核验的现成图片重建为可反复渲染的本地静态角色资产。当前用户已授权本地参考重建、检查和剪辑，无需重复确认已有授权；发布、素材再分发和推送 GitHub 仍须明确授权。角色与声音继续取现成来源，禁止纯文字另造形象或仿配原声。

## 以后制作视频，从现有版本开始

1. 查 `library/seed3d-plan.json` 的 `character_id`、`version`、`source_asset_id` 和 `reference_sha256`，再查 `library/seed3d-registry.json`、`library/seed3d-assets.json` 与实际本地资产。先确定一只角色的具体版本，不把社区版、原序列、毛绒版混用。
2. 打开模型目录下 `package/character-card.json`、`package/safe-import-report.json` 和 `references/reference-pack.json`。核对来源、模型哈希、坐标变换、相机校准和实际视觉审核；技术检查通过不等于身份或版权通过。
3. 实际看原图、正面、侧面、背面及转台，逐项比较眼睛、嘴、腹斑、手脚、轮廓与贴图接缝。选中同一版本后，从这份模型派生每个镜头需要的参考，不要每个镜头重新调用图生 3D。
4. 将真实图片附件交给能接收参考的视频工具；一镜内固定 `character_id + version_id + source_model_sha256`。多个角色各自绑定附件、动作和原声音源。模型只收到文字路径或触发词时，尚未收到参考。

这些派生渲染、尺寸变化、构图和相机视角都可本地完成，不继续消耗 Seed3D token。静态角色动作尚需单独解决骨骼、拓扑与动作来源；现有转台只提供外观检查，不是雷霆舞步或捧腹动作素材。

## 文件分工与约定

| 路径 | 用途与判断边界 |
|---|---|
| `library/seed3d-inputs.json` | 固定来源、裁剪范围、准备图哈希及真实看图记录 |
| `library/seed3d-plan.json` | 本批角色、版本、实际送入参考图、请求规格和预算 |
| `production/seed3d/usage-ledger.json` | 本批任务 ID、预留量、API 报告量和估计依据；不是账号余额 |
| `assets/private/seed3d/tasks/JOB/` | 原始任务响应，含临时签名 URL，只留本地 |
| `assets/private/seed3d/models/JOB/source.zip`、`files/` | 原始下载包和未覆盖的服务产物 |
| `assets/private/seed3d/models/JOB/package/` | 标准化 GLB、OBJ 交换件、材质贴图、来源和往返检查 |
| `assets/private/seed3d/models/JOB/references/` | 多角度图、轮廓 mask、联系图、相机转台和渲染清单 |

`package/character.glb` 保留为 PBR 材质主本；`character.obj + character.mtl + PNG` 是 **diffuse 交换副本**，金属度、粗糙度等 PBR 表达会损失，具体列在 `obj_pbr_losses`。不要将 OBJ 当作完整 PBR 备份。打包检查几何、UV、贴图像素及文件哈希的往返一致性，不自动修补网格或宣称已可绑定动画。

工作坐标统一为 **+Y 向上、校准后 +Z 为正面、总高 2 个归一化单位、水平包围盒居中、最低几何 Y=0**。这里的 2 不是 2 米或真实角色身高；“脚底 pivot”实际使用最低几何点，不是语义脚部检测。原始朝向须实看后通过 `--front-yaw` 提供；未校准时卡片仍标 `unverified`。实际变换矩阵保留在角色卡里，原始文件保持不变。

默认参考包为 8 个水平方向 × 平视/俯视15°/仰视15°，共 **24 张视图与 24 张轮廓 mask**；保存统一构图、正交相机和每张相机矩阵。`turntable.mp4` 默认 6 秒，是相机围绕静态网格转动，`mesh_animation=false`，没有创建骨骼或角色动作。

## 何时才新增一次重建

现有版本没有可用网格、质量确实无法满足目标，或选定了另一个真实来源版本时，再考虑新任务。先查看参考并登记来源、版本和权利状态，准备脚本只裁剪既有像素、按 alpha 合白底、等比缩放与留白，不补画轮廓、重绘表情或生成缺失身体。原图已符合接口时也可直接提交，计划中的哈希必须对应实际附件。

```bash
python3 scripts/prepare-seed3d-references.py --only naidan
python3 scripts/seed3d-batch.py status
```

本批计划使用 `doubao-seed3d-2-0-260328`，请求 high/GLB。声明可用免费量 2M，此批限制 **最多 5 个提交槽位、150,000 token**；四项计划在每成功项 30,000 token 的官方定价下预计 120,000 token。`status` 只显示本批累计和本批预算余量，不声称已读取整个账号剩余额度。具体成功项和实际总量始终读当前账本，不在技能里固化过时结果。

首个 `seed3d-naiwa-v1` 使用与旧 Hitem3D 对照相同的 `naiwa-frame-0000`，已成功并报告 30,000 token。它的嘴形略弯等差异应作为候选限制保留，不能覆盖旧版原图基准。奶蛋、噜噜社区版和肥嘟嘟社区版有各自的版本 ID；社区形象不自动等于官方标准模型。

## 受控提交、恢复与下载

凭据仅通过 `ARK_API_KEY` 或项目外临时文件 `ARK_API_KEY_FILE` 提供，不写进 JSON、命令输出、Git或交接文档。以下 `/secure/local-key` 表示已经安全保存的外部文件路径，命令里不填密钥字面值：

```bash
ARK_API_KEY_FILE=/secure/local-key python3 scripts/seed3d-batch.py submit seed3d-naidan-v1
ARK_API_KEY_FILE=/secure/local-key python3 scripts/seed3d-batch.py sync seed3d-naidan-v1
python3 scripts/seed3d-batch.py status
python3 scripts/seed3d-batch.py download seed3d-naidan-v1
```

`submit` 会计入提交槽位并在 POST 前原子预留预算。同一 job 不能再次 submit；已由其它脚本提交的任务先纳入同一账本，不重提：

```bash
python3 scripts/seed3d-batch.py adopt seed3d-naiwa-v1 TASK_ID
ARK_API_KEY_FILE=/secure/local-key python3 scripts/seed3d-batch.py sync seed3d-naiwa-v1
python3 scripts/seed3d-batch.py download seed3d-naiwa-v1
```

只有 `submit/sync` 需要推理凭据，`status/adopt/download` 使用本地记录；download 使用之前保存的签名 URL。POST 超时可能已经收单，保留预留、停止重提，找回任务 ID 后 adopt/sync。已有 task ID 就直接 sync；GET 暂时失败不会创建第二个任务。明确失败后仍保留记录，不靠删账本绕过槽位或预算。成功缺 usage 时按官方固定 30,000 标估计，不能称实测；意外计量会阻止继续提交。运行中的任务不能通过 DELETE 停止，删除成功任务记录也不会退还消耗。

成功响应的 `content.file_url` 下载内容是 ZIP，文件仅保留 24 小时，应及时下载；专门 API 页的任务元数据保留 7 天。下载器限制 HTTPS 官方媒体主机、包大小、路径、符号链接及 OBJ/MTL/GLB 外部依赖，不执行包内代码。URL 到期时先 sync 尝试刷新记录；已经被平台清理的结果不保证能恢复，不自动重新生成。

真正账号额度可在官方控制台查看；控制面 `GetModelActivation` 需要 AK 签名，不是本次推理 Bearer key 的能力。无需为本地批次索取额外 AK，也不改动账号开通、安心体验或付费设置。已授权范围内继续本地工作，依据预算与错误状态停止扩批。会话结束清除本次临时凭据，不将其保留为项目依赖。

## 审计、标准化和渲染示例

先从下载 `manifest.json` 找到真实 GLB 路径；下面是首个奶蛙包的已知目录示例。其它输出目录和校准角度须按实物确定。技术审计失败就先处理具体问题，不把不安全的模型交给通用导入器：

```bash
python3 scripts/inspect-model.py \
  assets/private/seed3d/models/seed3d-naiwa-v1/files/pbr/mesh_textured_pbr.glb \
  --root assets/private/seed3d/models/seed3d-naiwa-v1/files \
  --output assets/private/seed3d/models/seed3d-naiwa-v1/raw-audit.json

.venv-render/bin/python scripts/package-character.py \
  assets/private/seed3d/models/seed3d-naiwa-v1/files/pbr/mesh_textured_pbr.glb \
  --source-root assets/private/seed3d/models/seed3d-naiwa-v1/files \
  --job-id seed3d-naiwa-v1 --character-id naiwa --up-axis y --front-yaw 0

caffeinate -u -t 300 .venv-render/bin/python scripts/render-character-pack.py \
  assets/private/seed3d/models/seed3d-naiwa-v1/package/character.glb \
  --character-id naiwa --version-id naiwa-pet-network-3d-seed3d-v1 \
  --output assets/private/seed3d/models/seed3d-naiwa-v1/references
```

隔离渲染环境安装与 macOS 显示上下文问题见 [generation-tools.md](generation-tools.md)。每件先实看确认正面，奶蛙示例的 0° 不能套给其它模型。准备/打包/渲染均不调用推理 API；需要其它分辨率或参考构图时，从同一主本重复本地渲染即可。

## 审核不能被文件名替代

角色卡记录来源、变换和能力，不是角色官方认证或授权书；参考包仍须视觉审核。原图看不到的侧背、肢体连接和隐藏纹理均为单图推断。社区噜噜和肥嘟嘟保持社区版标签，奶蛋不添画“标准四肢”，奶蛙轻微嘴形漂移不因打包成功而消失。当前这些媒体及受限衍生包仅本地参考，不再分发或商用。

原声仍按 [audio.md](audio.md) 与 `library/audio-cues.json` 找到现成文件、试听并记录入出点；3D 包不附带自动生成台词或声音。最终视频的身份稳定性还要检查首帧、动作极值、遮挡恢复和尾帧；静态多角度图不能保证动作不崩。

官方接口和计费证据位于 `research/seed3d-official.json`、`research/seed3d-official-notes.md`；使用前有变化时核验 [创建 API](https://docs.volcengine.com/docs/ark/create-3d-generation-task-api?lang=zh)、[查询 API](https://docs.volcengine.com/docs/ark/get-3d-generation-task-api?lang=zh) 与 [模型价格](https://docs.volcengine.com/docs/ark/model-pricing?lang=zh)。不要把 Hitem3D 参数或科研演示的多视角/绑定功能移入当前 Seed3D API。

## 当前批次的视觉结论与局部修订

`production/seed3d/visual-reviews.json` 的每条审核绑定工作GLB的SHA；以注册表当前状态为准。
奶蛙保留为嘴形略漂移的对照候选；光滑奶蛋与肥嘟嘟为本地静态候选；噜噜原包腰后有源图没有的细杆，不能默认当标准版。

噜噜另有固定源SHA限定的 `scripts/remove-reviewed-artifact.py`：只删除已人工核对的外伸区域，
不焊接、不补洞、不加骨骼，原始产物不改。`library/seed3d-local-variants.json` 登记独立修订及侧面预览，
同目录 `repair-report.json` 保留原始→修订哈希链、删除面与材质/UV验证。修订仍有短残根和86条开放切口，
不是完全修复、可物理模拟或动画就绪的主本。只有用户具体选用并检查后才进入对应制作，
不要因生成成功、打包成功或存在清理脚本就覆盖原始身份基准。
