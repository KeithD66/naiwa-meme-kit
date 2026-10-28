# 保持网络流传版奶蛙的身份

目标是沿用同一个现成角色。文字描述、角色名称与 LoRA 触发词都不能替代实际图像输入。
参考可以降低漂移，不能保证每一帧正确；仍须逐镜头验收。

## 先认素材，再写动作

1. 用 `python3 scripts/library.py search --help` 查看本地检索方式；选定条目后 `inspect`，
   确认实际文件、来源、SHA-256 和使用范围。目录索引不等于图片已经下载。
2. 必须打开实际图片或原片检查。文件名含「奶蛙」「官方」「standard」不是视觉证据。
   将选定资产 ID、路径、SHA-256 和看图结论记入本次制作交接包。
3. 同一身份组只选一个版本。网传 3D、像素桌宠、名画改绘、幼年版和异色版分别归档；
   不把奶龙、真实牛奶蛙或绿色青蛙填入奶蛙参考位。
4. 分开绑定身份参考、动作参考和背景参考。舞步视频只提供运动，不提供舞者的脸、
   服饰或身体；不能为了模仿舞步重新设计奶蛙。
5. 按用户规则，AI 视频开始前须取得并核验现成三视图，或从取得许可的 `.obj` 渲参考帧。
   捧腹笑序列、注视方向和正面照都不是自动合格的 front/side/back。
   缺少合格多角度基准时，暂不启动 AI 动作生成；可继续检索、策划和检查现成原片。
6. 工具必须能接收实际图片/角色参考。只有纯文字生成的工具不能满足本项目的身份要求，
   不得偷偷降级为 text-to-video；写一个本地路径不代表模型已经收到图片附件。

## 本地网络版入口

| 资产 ID | 实际路径 | 本次检查与用途 | 限制 |
|---|---|---|---|
| `naiwa-frame-0000` | `assets/repos/naiwa-pet/public/pets/naiwa/frames/frame_0000.webp` | 已看图：全身微侧、双手在肚前、圆眼、细横嘴、浅腹部、深色手脚 | 无 LICENSE，仅本地；不是完整三视图，未证明为最早原始出处 |
| `naiwa-frame-0200` | `assets/repos/naiwa-pet/public/pets/naiwa/frames/frame_0200.webp` | 已看图：同一序列的闭眼仰头、张嘴露齿、捧腹大笑 | 同上；笑态不能被静态“一字嘴”规则错误禁止 |
| `naiwa-original-video` | `assets/repos/naiwa-pet/naiwa.mp4` | 源视频入口，可继续看连续动作与角度 | 本次未逐帧看全片，仅本地；不承诺全片都通过 |
| `naiwa-codex-sprite` | `assets/repos/codex-pet-naiwa/naifrog/spritesheet.webp` | 桌宠动作图集 | 包装库 MIT 不覆盖 Credits 第三方媒体 |
| `naiwa-look-directions` | `assets/repos/codex-pet-naiwa/naifrog/previews/look-directions.png` | 本次只看预览首帧；README 称有 16 个注视方向 | 眼睛朝向不是相机绕角色的三视图 |

这些条目是现成素材定位，不表示已批准生成或取得分发授权。实际状态以 `library.py inspect` 为准。

## 默认不要混入身份参考的来源

- 两张 `assets/private/references/neta-mature-*.webp` 候选均把侧视标成 FRONT、正视标成 SIDE；
  眼色和嘴形亦有差异。只作候选，不默认进入身份组，不自行生成“修正版”补齐。
  Neta 页说明世界由其工具生成；站内 official 不是角色权利人认证。
- wallpaper 含像素、艺术、异色、幼年等不同造型。先查实际同名附录（如 `.png.txt`）来源说明再看图，
  不因同名或许可清楚就用再绘版替代用户要的网传 3D。
- LoRA 只有兼容且实际加载权重才生效。写 `NAIWA` 不会让通用视频服务自动加载模型。

## 每个镜头绑定身份

用 `python3 scripts/library.py handoff --help` 查看交接包参数。每个角色单独写资产 ID、
实际附件、位置和动作。交接包路径供工具定位文件，传给模型时仍须提供真实附件。

```json
{
  "shot_id": "s03",
  "mode": "image_to_video",
  "characters": [{
    "character_id": "naiwa",
    "reference_asset_ids": ["naiwa-frame-0000", "naiwa-frame-0200"],
    "identity_version": "network-3d-local-study",
    "screen_position": "center",
    "action": "holding belly, small shoulder movement",
    "visual_review": "sampled_files_checked",
    "multiview_ready": false
  }],
  "render_status": "blocked_until_multiview_reference_ready"
}
```

这是记录示例，不是满足前置条件的生成任务。使用交接包当前真实路径、SHA-256、
许可状态与 blockers，不手改 `multiview_ready` 绕过缺失素材。

## 动作和多角色控制

先固定机位、正面/已有微侧、小幅运动、短镜头。雷霆感优先交给剪辑的切镜、定格、强变焦
和现成音频卡点；不要一开始就同时大幅旋转、形变、口型表演、换装和快速运镜。
具体时长/强度依工具，不假设服务间共享参数名、seed 或参考强度。

需要转身时先核验对应角度的现成参考，不由正面猜背面。新镜头继续用原始身份参考，
不默认拿已经漂移的 AI 末帧当新标准。多角色分别绑定参考、位置与动作；奶蛙的眼圈、
肚皮和手脚不能迁移到水豚/袋鼠/牛。未知角色先消歧，不凭名字猜一个黄色身体。

## 逐镜头验收和重试

至少看首帧、动作极值、表情切换、遮挡后重现与尾帧；快速动作需更密地检查。

| 检查点 | 通过要求 | 退回示例 |
|---|---|---|
| 轮廓 | 同一头身比例、梨形体态、无独立脖子 | 变奶龙大头、瘦高人形或青蛙 |
| 五官 | 同一眼圈/瞳孔关系；静态细横嘴 | 人嘴、大白眼、额外眼睛；笑时换脸 |
| 腹部 | 同一面积、边界、位置 | 消失、变衣服、漂到背面 |
| 手脚 | 既有深色末端与可见结构 | 人手、增指、多腿、粘连；遮挡后多肢 |
| 笑态 | 按同一身份的现成笑态开口/闭眼 | 为保横嘴不能笑，或笑起来成为另一角色 |
| 联动 | 各自身份与参考归属稳定 | 串脸、串色、位置交换后换身份 |

任一项失败就退回。重试顺序：降低动作/旋转 → 换同一身份更贴近目标角度的现成参考
→ 拆短镜头 → 现成动作剪辑替代。不要重设计奶蛙、改成奶龙、另造三视图或合成仿原作声音补洞。

完整提示模板见 `prompts/naiwa-character-prompts.md`，可追溯证据见
`research/identity-resources.json` 和 `ip-assets.md`。

## 已落地的 Seed3D 本地重建候选

本项目另有经用户授权、从现成参考重建的 Seed3D 资产流程，见
[seed3d-foundation.md](seed3d-foundation.md)。用 `library/seed3d-registry.json`
查角色版本及实际完整状态，`library/seed3d-assets.json` 查模型、相机参考与哈希。
这些是可重复使用的本地衍生候选，不是已经下载到网传角色的官方原始模型；
旧的嘉立创/网络三视图线索状态不因重建成功而自动通过。

同一网格可以本地反复渲染多个视角，避免一镜头重造一个角色。选择时保留原图作身份锚，
把重建渲染用于几何/视角补充；奶蛙嘴形漂移、社区版角色、低分辨率原图和推测背面须明确记录。
多角度参考与相机转台不等于骨骼绑定、角色动作或公开分发许可。
