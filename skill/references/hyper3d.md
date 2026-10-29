# Hyper3D：多图输入与四边面角色候选

`hyper3d-gen2-260112` 是影眸的静态 3D 生成模型。对本项目有价值的补充是
1–5 张图片输入、Quad 四边面网格、面数控制和 PBR 材质。生成视频、现成梗音效、
骨骼绑定和角色动作仍需其它来源或工具。
PBR是可请求的模型能力，逐件仍须检查实际交付；本次OBJ没有交付材质或贴图。

## 本次实际结果

用户已确认有独立免费额度并明确授权执行一次同图试制，总量与账号余额仍未知。
`hyper3d-naiwa-quad-v1` 已成功，任务 `cgt-20261029144646-854ct` 的API实际报告
30,000 tokens，`production/hyper3d/usage-ledger.json` 中预留为0。
这份任务已经完成，恢复或查看时使用已有ID和文件，不能再次POST。

本次下载是 **direct OBJ**，没有ZIP封装；官方查询文档所说“打包为ZIP”与这件实物不同。
保留文档捕获和本次观测，不将一次OBJ结果外推为其它模型格式也一定直接返回。
原始文件为：

```text
assets/private/hyper3d/models/hyper3d-naiwa-quad-v1/files/model.obj
SHA-256: 964f21ce8f09bb4d860dab7950ef302bf09497756f2d870030e72a5d4923455f
```

`native-audit.json` 的源索引检查记录43,947个面，全为四顶点面；原生三角面及五边以上n-gon为0，
等价三角形87,894个。单连通分量，边界边/非流形边为0，没有做焊接、修复或重新拓扑。
这些是几何统计，不证明关节环线、无自交或变形质量。

文件有UV，但没有 `mtllib`、`usemtl`、材质、顶点颜色或贴图。因此本件只能先作为
**无材质的几何检查件**。实际查看源图与灰预览后，身份已被拒绝：源图只有捧腹双臂，
生成件保留捧腹臂又多出一对展开臂，成为四臂。结论是 **`rejected_extra_limbs` +
`missing_materials`**，不能作默认奶蛙模型或视频身份参考。`TAPose=false` 未避免额外肢体，
原因未确定，不据此推测参数如何被服务处理。

本件仅保留为失败样本/benchmark，不追加重试；`production/hyper3d/visual-reviews.json`
记录实际视觉证据。43,947个全Quad面证明的是原生拓扑统计，不能推翻形象失败。
PBR/HighPack请求也不能替代材质交付。原生OBJ与 `geometry-preview-package/` 的三角化灰预览分别保留，后者用于
几何查看，不是带纹理PBR主本或原生四边面档案。
本地图册为 `assets/private/hyper3d/index.html`，包含输入对照、灰模、转台和原件下载。
`library/hyper3d-registry.json` 记录实测状态，`library/hyper3d-assets.json` 已接入素材检索；
这53项文件均保留几何检查用途与身份拒绝标签，不升级为视频身份参考。

```bash
python3 scripts/build-hyper3d-library.py
python3 scripts/library.py index
python3 scripts/library.py search --query Hyper3D --local
```

24视图、24轮廓mask和6秒相机转台均由同一灰模本地渲染，无新推理。
`comparison/uniform-neutral/comparison.jpg` 与报告统一三模型的高度、相机和中性显示材质，
用于比较几何。中性材质只在内存中应用，原模型颜色和文件不变；不能据灰模图比较贴图质量。
打包器已修复无MTL但有UV的OBJ会被加载器自动注入2×2灰图的问题：现在明确记录
无源贴图、仅有中性显示材质，不再把占位图当供应商PBR交付。

## 何时使用

- 需要试验比现有高面数模型更方便编辑的角色网格时，选 Quad，保存原生 OBJ。
- 有同版本、同姿态的真实多角度素材时，可准备多张图片；当前 Ark 文档没有暴露
  相机/视角角色或 MultiView 模式，不能声称已验证多视图几何约束。
- 只需要另一个镜头或角度时，继续复用已有模型本地渲染。

本项目继续以现成角色图为输入。用户粘贴的机械兽纯文字示例用于辨认 API，
不作为新增生态角色的指令。不能拿 Seed3D 推断的背面充当真实网传背面来准备多图。

## 同图对照与离线准备

`library/hyper3d-plan.json` 固定了一个奶蛙候选：与现有 Hitem3D、Seed3D
相同的 `naiwa-frame-0000`，Quad 50,000 面、PBR、HighPack、OBJ、TAPose=false。
50k 对应官方 Quad high 档；默认 medium 是 18k，调低面数不减少单次固定调用费。
不设置 `[100,100,100]` 边界，避免强行改变梨形角色比例。

```bash
.venv-render/bin/python scripts/hyper3d-request.py prepare hyper3d-naiwa-quad-v1 --dry-run
.venv-render/bin/python scripts/hyper3d-request.py prepare hyper3d-naiwa-quad-v1
```

准备工具核对现成源图、来源版本、姿态、实际哈希及视觉审核证据，不读密钥、不联网。
第一条只校验；第二条将真实请求和不含 Base64 的摘要保存在
`assets/private/hyper3d/requests/hyper3d-naiwa-quad-v1/`。
它不提交任务，也不预留或扣减推理额度。

Hyper3D 接收 JPG/JPEG/PNG；现有 WebP 源图按原尺寸转 RGBA PNG，
保留原文件 SHA、提交 PNG SHA 和解码 RGBA 像素哈希，不裁剪、缩放、补画或重设姿态。
多图必须属于同一原图版本与姿态，并记录其来源一致性证据；重复图和跨姿态笑帧不能拼成三视图。

## 参数、额度与执行边界

- Raw 自定义面数为 500–1,000,000；Quad 为 1,000–200,000。
  `quality_override` 覆盖 `subdivisionlevel`，不要叠加后再按档位解释。
- `HighPack` 承诺更高纹理分辨率，不能据此推断附送高模、多格式文件或骨骼。
- `TAPose=true` 是请求重建为 T/A 静态姿态，会推断原图遮挡部分；不是自动绑定。
  当前候选保留原姿态，实际是否遵从仍须看结果。
- 官方固定每成功任务 30,000 tokens，当前按量价 1.80 元；模型列表所列免费额度
  不是当前账号余额，Seed3D 的 2M 也不自动共用。本计划限制一次试验、30,000 tokens，
  本次已报告30,000、预留归零；用户确认有独立免费额度，但未给总量，不把官方初始赠额
  直接当作其当前余额，也不从单价推断已扣现金。新的调用再根据具体授权、额度和价格执行。

通用 `ark-task.py` 支持一次显式 POST 和按任务 ID 查询，见 [生成工具说明](generation-tools.md)。
它没有 Hyper3D 专用的原子额度台账或跨进程防重复提交能力；不能把请求准备器当成计费控制器。
实际提交前登记独立执行记录，已有任务 ID 就查询；POST 超时保留不确定状态，不自动重发。
结果及时下载到私有目录，记录 task_id、输入/原生输出哈希与实际用量。
已有成功结果不因缺纹理而自动重提；先审查本件和交付差异，再决定有明确目的的新试验。
任务文件按官方文档仅保留24小时，应及时转存，原始响应中的签名URL只留私有目录。
`running` 不支持取消；成功后DELETE只删除任务记录，不退还用量。

## 生成后的验收与复用

保留实际下载的原件，以及确实交付的贴图和依赖。不要为满足清单而假定存在ZIP/MTL/贴图。
先用现有检查器读取原生 OBJ：

```bash
python3 scripts/inspect-model.py assets/private/hyper3d/models/JOB/files/model.obj \
  --root assets/private/hyper3d/models/JOB/files \
  --output assets/private/hyper3d/models/JOB/native-audit.json
```

路径以实际返回文件为准。`source_face_vertex_histogram` 记录原生面的顶点数分布，
`quad_face_fraction` 记录四顶点面的占比；请求写了 Quad 不证明实际返回全四边面。
GLB 与 trimesh 派生件会三角化，不能替代四边面原件。原生 OBJ 的 PBR 材质与
多格式组合是否齐全，以真实文件为准，不能由请求参数推断。

现有 `package-character.py` 只为 OBJ 自动映射 diffuse 通道；遇到其它 PBR 通道会阻止导入，
应保留原件并明确材质映射，不删通道绕过检查。预览派生件与原生拓扑件分别登记用途。

同图比较眼睛、横嘴、腹斑、手脚、轮廓、纹理接缝与肢体连接；对齐坐标、相机和灯光后再排名。
单图背面保持推断标签。通过检查也仅增加独立候选版本，不覆盖原图或现有模型，
不自动认证骨骼、蒙皮、舞步、商用或素材分发许可。

证据汇总：`research/hyper3d-official.json`。
官方来源：[创建 API](https://docs.volcengine.com/docs/ark/shadoweye-create-3d-generation-task-api?lang=zh)、
[模型列表](https://docs.volcengine.com/docs/ark/model-list?lang=zh)、
[模型价格](https://docs.volcengine.com/docs/ark/model-pricing?lang=zh)。
