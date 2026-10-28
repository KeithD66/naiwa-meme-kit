# 现成形象、动作、三视图与权重来源

核验日期：2026-10-29。先读 `identity-lock.md`。角色名称与 prompt 不是已加载的身份模型。

## 本地入口

| 资源 | 当前内容与用途 | 许可/限制 |
|---|---|---|
| `assets/repos/naiwa-pet/` | 438 连续帧、`naiwa.mp4`、`audio.m4a`；已看 frame0000/0200 可比对闭嘴捧肚与仰头大笑 | 无 LICENSE，仅本地；连续帧不是完整三视图 |
| `assets/repos/codex-pet-naiwa/naifrog/` | 动作图集及 idle/jumping/look-directions 预览；README 将 jumping 标作捧腹笑 | 原创内容 MIT，Credits 第三方媒体明确排除 |
| `assets/repos/NaiLoong/data/naiwa/` | 121 静态、71 动图远程目录，含站姿、捧腹笑、跳舞线索 | 原图并未随目录全数落地；桌宠 sprite 也引用 codex-pet-naiwa |
| `assets/repos/NaiLong-Universe/` | 已拉取站点、预览、图像与部分视频；`docs/data/assets.json` 可定位 | README 不做商业用途；完整原图库另见 wallpaper |

目录中的「经典奶蛙捧腹大笑」`naiwa_0137.jpg` 与「抱胸自信站立」`naiwa_0138.jpg` 固定提交直链
本次 HEAD200（169507 / 271031 字节）；尚未看图，不因标题就锁定身份。精确链接见研究JSON。

用 `python3 scripts/library.py search --help` / `inspect --help` 定位当前实际文件。
媒体能看见不等于能发布，使用前核对 `licensing.md`。

## 主要扩充入口：wallpaper

[Nailong-Studio/wallpaper](https://github.com/Nailong-Studio/wallpaper) 有
[机器可读清单](https://github.com/Nailong-Studio/wallpaper/blob/main/assets.json)。
本次读取版本 2.7.0，263 件，含 emotes67、pet14、audio2。这是上游索引数量，不是本机下载数。

- `emotes/` 有现成立绘、姿态、表情和 GIF；部分档案只追溯到搜索引擎/CDN，权利仍待核对。
- `laugh-gallery/` 有亮黄站姿与捧腹笑，也有粉/白/橙异色版，默认身份不混用。
- `pet/` 有待机、捧腹笑、倾听、躺平四态和 PNG，多为重新制作的桌宠角色。
- `videos/奶蛙-大笑.mp4` 清单称15.4秒连续大笑裸片、含原声；本次未逐帧看该原片。
- 查真实的同名附录（如 `奶蛙-大笑.mp4.txt`，保留媒体扩展名）与 [SOURCES.md](https://github.com/Nailong-Studio/wallpaper/blob/main/SOURCES.md)。
  代码/清单/脚本的 MIT 与逐媒体许可分开；索引尺寸可能是预览尺寸，以实际文件读数为准。

### 已直接读到原作者媒体声明的候选

| 来源与声明 | 已核实范围 | 身份注意 |
|---|---|---|
| [liaosongjie/Codex-Voice-Input](https://github.com/liaosongjie/Codex-Voice-Input/blob/main/assets/pet/ASSET-NOTICE.md) | 作者称源视频、动画与笑声自制，派生 PNG 与 laugh.wav MIT | 桌宠再创作，先看图确认是否匹配网传版本 |
| [Maple498/nai-wa-codex-pet](https://github.com/Maple498/nai-wa-codex-pet/blob/main/ASSET-LICENSE.md) | 自制像素动画/预览 CC BY4，明确不担保原型第三方权利 | 像素用途须署名，不替代原版3D |
| [sandytruant/codex-pet-naiwa](https://github.com/sandytruant/codex-pet-naiwa) | README 明确代码与宠物素材 MIT | 像素再绘，单独风格组 |
| [TarelX/Milk-Frog](https://github.com/TarelX/Milk-Frog/blob/main/NOTICE.md) | 自身设计、图标、帧、道具、文档 MIT | 同名不等于同一造型，先看实际图 |

这些是对维护者自己创作部分的声明，不替第三方角色原型或音乐授权。
WencueCryforme/NaiWa-Universe 的 COPYRIGHT 声称奶蛙无人拥有版权，只记为作者立场，
不据此推定公有领域。

## 三视图：候选已找到，尚无默认合格基准

[Neta 百科](https://neta.art/app/milk-frog-wiki) 与
[头像/壁纸页](https://neta.art/explore/work/en/milk-frog-avatar-wallpaper) 给出三视图链接。
本地候选在 `assets/private/references/neta-mature-*.webp`。

两份实际图都把侧视标为 FRONT、正视标为 SIDE，眼色与嘴形也与用户标准略有差异。
Neta 页面说明该世界由其工具生成；站内“官方”不是权利人背书。默认不采用，也不自行
生成“修正版”凑齐参考。只有实际核验同一造型的正/侧/背，才记多角度已就绪。

## 3D：线索尚未取得

[嘉立创给定模型页](https://model.jlc-3dp.cn/modelDetail/037262f117974eacb739974e67344c53.html)
本次原站请求200，但只有通用页面壳和登录入口；没有奶蛙标题、`.obj` 列表或下载直链，
页面有联系客服获取许可的提示。原文列出的奶蛙/奶趴/奶蛋等 `.obj` 文件，本次未独立确认。
没有下载模型、材质或取得许可。

后续取得模型时核对真实几何、材质和参考渲染用途，不拿白模凭文字新造五官；参考渲染
等进入制作阶段才执行。Sketchfab 的 `milk frog` 多命中真实牛奶蛙，本次没有核实到
可直接采用、同形象且明确许可的 3D 模型。

## LoRA：官方 API 已核实，权重未下载

| 资源 | 版本/底模/触发词 | 文件 |
|---|---|---|
| [Civitai #2802348](https://civitai.com/models/2802348) | Ay1in，V2，version3249650，Krea2，`NAIWA` | Krea2_NAIWA_V2_000002250.safetensors，223230.203125 KiB，约218 MiB |
| [Civitai #3006514](https://civitai.com/models/3006514) | egdarin，v1.0，version3411275，MOSS Image，`naiwa`等 | Nai-Animals-768-r16_e12.safetensors，72630.6796875 KiB，约71 MiB |

已直接读 [2802348 API](https://civitai.com/api/v1/models/2802348) 与
[3006514 API](https://civitai.com/api/v1/models/3006514)，下载端点、预期 SHA-256 与访问状态
记录在 `research/identity-resources.json`。未下载、未加载、未实测；底模条件、运行环境、
访问/下载权限与下游许可在实际使用时核验。

MOSS 作者明确报告比例/局部变化、多黄色角色串特征、多人位置交换等问题。LoRA 不是身份保证，
也未覆盖水豚噜噜、美团袋鼠、奶蛋、唐牛等所有生态成员。不支持兼容 LoRA 的视频服务
不会因为 prompt 写 `NAIWA` 就自动加载模型。

Hugging Face 官方 API 本次搜 `naiwa` 的模型和数据集结果均为空，不是全平台不存在的证明。
`XiC1/nailong-dataset` 是奶龙数据集，不是奶蛙身份库；名称含 Nailong 的翻译/分类/机器人
模型也不是角色生成权重。

## 视频工具适配

先读所用工具的真实能力。支持角色参考就传实际附件并绑定身份；支持独立动作参考才将舞步
放到 motion 输入。若仅支持纯文字，或无法传关键参考，报告能力缺项并继续现成素材策划。
制作交接用 `library.py handoff`，逐镜头验收按 `identity-lock.md`，声音按 `audio.md`。

## 已落地的 Seed3D 本地重建候选

本项目另有经用户授权、从现成参考重建的 Seed3D 资产流程，见
[seed3d-foundation.md](seed3d-foundation.md)。用 `library/seed3d-registry.json`
查角色版本及实际完整状态，`library/seed3d-assets.json` 查模型、相机参考与哈希。
这些是可重复使用的本地衍生候选，不是已经下载到网传角色的官方原始模型；
旧的嘉立创/网络三视图线索状态不因重建成功而自动通过。

同一网格可以本地反复渲染多个视角，避免一镜头重造一个角色。选择时保留原图作身份锚，
把重建渲染用于几何/视角补充；奶蛙嘴形漂移、社区版角色、低分辨率原图和推测背面须明确记录。
多角度参考与相机转台不等于骨骼绑定、角色动作或公开分发许可。
