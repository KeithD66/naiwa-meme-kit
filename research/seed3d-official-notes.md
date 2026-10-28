# Seed3D 2.0 官方接口核验

核验日：2026-10-29。模型：`doubao-seed3d-2-0-260328`。这里只记录公开官方资料，未读取密钥、查询用户账号、调用推理或修改账号设置。结构化证据见 `seed3d-official.json`。

## 适合为项目做什么

把已经核验身份的现成单张图片重建为带纹理和 PBR 材质的静态 3D 候选，再本地整理尺度、朝向、模型质量报告和多角度渲染。这能形成以后反复使用的角色参考包，但单图看不到的背面仍是模型推测，不能冒称网传标准三视图或官方模型。

当前 Ark API 不是视频、自动角色绑定或动作生成接口。字节 [Seed3D 2.0 研究介绍](https://seed.bytedance.com/en/seed3d_2_0) 和 [发布文章](https://seed.bytedance.com/en/blog/seed3d-2-0-released-higher-precision-and-greater-usability) 展示过部件拆分、关节结构和场景组合；这些研究能力不能当作本次生产接口已经提供的参数。

## 请求与输入边界

[创建 3D 生成任务 API](https://docs.volcengine.com/docs/ark/create-3d-generation-task-api?lang=zh) 明确输入为 **1 张图**，不支持联合传多视角图片；文本只传参数，不能靠描述要求重造、摆姿或补画角色。

接口：`POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks`。`model` 与 `content` 必填。图片放在 `content[].image_url.url`，可用公网 URL 或 `data:image/png;base64,...` 等小写格式的 Base64 URI。

图片要求：jpeg/png/webp/bmp/tiff/gif；每边 300–6000px；宽高比 0.4–2.5；单张小于 30MB，请求体不超过 64MB，大文件不要用 Base64。使用实际参考图，示例中的花朵 URL 不是本项目角色参考。

| 参数 | 可选值 | 文档默认值 |
|---|---|---|
| `--subdivisionlevel` | low=100,000 面；medium=500,000 面；high=1,000,000 面 | medium |
| `--fileformat` | glb、obj、usd、usdz | glb |

当前官方示例使用 `content` 里的 text：`--subdivisionlevel high --fileformat obj`。参数表另列 `subdivision_level`、`file_format`。两种拼写不要混进同一文本 flag；优先复用已核验的官方示例形式。

文档明确 flag 是弱校验，错误参数会被忽略。因此提交前应本地严格验证，完成后检查查询结果中的 `fileformat`、`subdivisionlevel` 和真实网格。当前创建接口没有 `seed`、负面提示词、多图输入、骨骼绑定、动画、纹理重做、材质模式切换等公开参数，也不继承 Hitem3D 的 `--ff 2`、`--request_type` 或 `--resolution`。

## 查询、下载和取消

[查询 API](https://docs.volcengine.com/docs/ark/get-3d-generation-task-api?lang=zh)：`GET /contents/generations/tasks/{id}`。状态为 `queued`、`running`、`cancelled`、`succeeded`、`failed`。成功下载链接字段是 `content.file_url`；**下载体为 ZIP**，包内模型格式才是请求的 OBJ/GLB 等。文件 24 小时后清理，应立即转存原始 ZIP、解压文件、响应和 SHA-256。专门 API 页说任务元数据保存 7 天。

计量在 `usage.completion_tokens`；`usage.total_tokens` 与之相等，3D 不统计输入 token。还应留存任务 ID、模型、返回参数、创建/更新时间和错误码。带签名下载 URL 的原始响应留在忽略目录，公开研究台账只保留可审查摘要。

[取消/删除 API](https://docs.volcengine.com/docs/ark/delete-3d-api?lang=zh)：`DELETE /contents/generations/tasks/{id}`。只有 queued 可以取消；running 不支持停止。成功或失败任务的 DELETE 只是删除任务记录，不能退款或中止已完成的消耗，因此不可将 DELETE 当作预算刹车。

## 计费与 2M 免费额度

[官方模型价格](https://docs.volcengine.com/docs/ark/model-pricing?lang=zh) 的 3D 表格列 Seed3D 2.0 每次 **30,000 token**，`0.80 元/万 token`，折合 `2.40 元/次`；当前表格没有按 Seed3D 分面等级或输出格式区分价格。其后规则是“按成功输出 3D 文件数计费”，所以失败且没有成功产物不在该计费基础内。成功但视觉不满意仍是成功产物，不视为免费失败；需要保留实际终态和 usage 对账。

[官方模型列表](https://docs.volcengine.com/docs/ark/model-list?lang=zh) 列本模型免费额度 2,000,000 token，最大 RPM 300、最大并发 5。如果额度完整且未被其它调用消耗，数学上能覆盖 66 次成功生成，余 20,000 token。这是预算换算，不代表应批量烧满或账号当前实测余额。

[免费推理额度规则](https://docs.volcengine.com/docs/ark/free-inference-quota?lang=zh) 说明不同模型分开、同一主账号下共享；只抵按 token 后付费的在线推理，不抵插件/知识库或批量推理。用户给出的 2M 是本次预算依据，仍需维护本任务的独立台账。

存在官方 [GetModelActivation](https://docs.volcengine.com/docs/ark/get-model-activation-api?lang=zh) 控制面接口，可用 `WithFreeUsage` 请求 `Item.FreeResourcePackItems` 的 `Consumed`、`Total`、`SyncTime` 等额度信息，以及 `Item.InitialInferenceFreeUsage`。但它 **仅支持 Access Key 签名鉴权**，不能拿用户本次 Ark Bearer API key 就声称已经查到真实余额。

[安心体验模式](https://docs.volcengine.com/docs/ark/free-tokens-only-mode?lang=zh) 是账号配置，受新用户资格限制，关闭后不能重开；其通用页面还写 50 万，与模型列表特定的 200 万不是同一个可直接套用的数值。账号是否已启用、能否启用均未知，本研究不更改它。[计费说明](https://docs.volcengine.com/docs/ark/model-service-pricing?lang=zh) 也提醒账单及抵扣可能延迟，并提到模型用量上限设置。

所以**仅凭本地台账和推理 key 无法保证整个账号绝不产生额外账单**。可控做法是单个真实参考试制，确认 usage=30,000 后才开展小批；对所有未决或 POST 超时任务先预留消耗，禁止自动重试 POST，保留明显额度余量。其它会话的消耗、已有使用和资源包有效期尚未实测；没有 `max_tokens` 一类参数可在这次推理请求内锁定账号免费余额。

## 官方页面中的矛盾

[3D 生成教程](https://docs.volcengine.com/docs/ark/3d-generation?lang=zh) 的一处示例注释将 medium 写成 100,000 面，与专门创建 API 的 500,000 面不符；末段又称任务数据仅留 24 小时，与查询 API 的元数据 7 天不符。执行采用专门 API 的字段定义，同时检查真实结果，并立即保存全部文件，避免依赖远端保留时间。

材料和角色版权仍继承输入来源约束。模型服务提供生成能力，不会替项目补齐角色或原图许可；本地重建候选与其多角度图继续遵守本项目的本地参考限制。
