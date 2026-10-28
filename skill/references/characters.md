# 角色档案与名称消歧

最后核验：2026-10-29。机器可读来源、固定提交与候选素材见
`research/ecosystem-resources.json`；多人同框方法见 `ecosystem.md`。

本文件用于识别现成角色，**不是从文字重造形象的说明书**。角色名、LoRA 触发词和
外貌描述都不能替代上传参考图。没有实际参考时先补来源，不按“黄色吉祥物”
“卡皮巴拉”“袋鼠”等通用概念自由设计。

## 名称路由

| ID | 名称 / 别名 | 当前识别状态 | 禁止自动替换成 |
|---|---|---|---|
| `naiwa` | 奶蛙、奶娃、大笑奶龙、变异奶龙 | 本项目主角，须锁定网络流传版参考 | 官方奶龙、普通青蛙、新造黄色吉祥物 |
| `naidan` | 奶蛋 | 有独立图像目录和专属语音表 | 奶蛙任意变圆、官方蛋猫、普通鸡蛋 |
| `naifen_character` | 奶粉（角色） | 创作者视频标题支持角色用法，具体造型版本待锁定 | 奶蛙粉丝、奶包、凭名称想象的粉色奶蛙 |
| `naifen_fandom` | 奶粉（粉丝） | “奶粉们”等文字用法 | 默认新增一个角色 |
| `capylulu` | 水豚噜噜、噜噜、Capylulu | 官方授权展目录与社区桌宠可追溯 | 任意水豚、卡皮巴拉歌曲里的任意动物 |
| `meituan_meme` | 美团袋鼠、美团老鼠、肥嘟嘟 | 官方品牌版与民间胖版分开记录 | 真老鼠、奶鼠、普通袋鼠 |
| `doubao` | 豆包 | 官方 AI 产品可确认，视频中的视觉版本待选 | 通用圆形机器人、把“豆奶”当官方角色名 |
| `niulai` | 牛来 | 电影《牛来》的小牛角色可确认 | 唐牛、任意黄牛、奶牛 |
| `tangniu_unresolved` | 唐牛 | 尚未确定所指动画版本 | 牛来、《食神》真人唐牛、同名账号 |
| `nailoong` | 奶龙、Nailoong | 第七印象官方 IP，与奶蛙分开 | 奶蛙 |
| `naibao` | 奶包 | MOSS 模型卡已核实，视觉参考待锁定 | 奶粉、奶蛋、普通包子 |
| `nai_whale` | 奶鲸、Nai_DS_whale | 本地有“沉思的奶鲸”原图目录条目 | 任意蓝鲸、把奶蛙涂蓝 |
| `zhiren` | 纸人 | MOSS 模型卡已核实，视觉参考待锁定 | 任意纸扎人、任意国风人物 |

ID 是本库检索键，不宣称官方命名或人物关系。

## 奶蛙 `naiwa`

用户指定的视觉要点：金黄梨形、头身一体无脖子、灰绿圆形大眼与黑瞳、一字横嘴、
乳白大肚皮、橄榄褐四指手、三趾脚。招牌动作是捧腹大笑。
这些要点只用于检查参考和生成结果，不能作为纯文字出角色的依据。

- `assets/repos/naiwa-pet/public/pets/naiwa/frames/`：438 帧原序列，
  manifest 为 720×960、30 fps；无 LICENSE，仅本地使用。
- `assets/repos/codex-pet-naiwa/naifrog/previews/idle.png`、`jumping.png`：
  README 将后者标作捧腹大笑；另有 16 向预览。README 明确排除 Credits 第三方媒体的 MIT 授权。
- `assets/repos/NaiLoong/data/naiwa/`：远程图像索引，不代表对应原图全已下载。

先选本条视频的同一版本，再取该版本的多视角和表情。不同作者的正／侧／背图不能拼称
“官方三视图”。neta.art 候选有正侧标签对调和外观差异，不因文件名带 official 就通过。
旧库关于起源作者、删号和“无版权方”的说法本次未独立核实，不再由此推导自由使用。

## 奶蛋 `naidan`

`NaiLoong/data/manifest.json` 单列奶蛋。当前快照有 **5 条静态、1 条动图**索引。
可追“奶蛋呆呆站立”“奶蛋双手抱胸自信微笑”“生气叉腰的奶蛋”等具体条目。
`data/naidan/voice.json` 明确将“安~迪~”映射到 `assets/audio/andi.mp3`；
**andi 不应无条件归到奶蛙名下。**

另有现成游戏库 [`busgm666-cloud/naidan-slingshot`](https://github.com/busgm666-cloud/naidan-slingshot)，
包含奶蛋立绘与背面图；README 说明部分变体由程序重着色、部分表情另行生成。
它是已有社区变体线索，不能证明哪一版就是用户所指的网络标准。优先核对原始梗图。
嘉立创“奶蛋.obj”也只是模型线索，实际文件和使用条件须另取另验。

## 奶粉：两个分支都保留

抖音创作者“鼠粉动画（名画收藏）奶总”的
[“奶粉看奶鼠出丑了”](https://www.douyin.com/video/7655968905470853738)
及[“选择奶粉还是奶蛋”](https://www.douyin.com/video/7683022618401145829)
的可检索标题支持角色用法。直接页受动态加载限制，本次没有据标题确认造型或原作者。
另一方面，“奶粉们”“十年奶粉”等也可指粉丝，不应触发人物生成。

遇到“奶粉出场”，先从具体创作者原片或已有素材锁定版本，记下 URL、作者和帧时间。
目前尚未找到可证实身份并带完整许可的统一三视图／模型包；不得用奶包、粉色奶蛙或奶粉罐替代。

## 水豚噜噜 `capylulu`

**纠正旧库**：[CLE 中国授权展目录](https://www.chinalicensingexpo.com/cn/product/1849)
列出铁罐（北京）文化传媒有限公司，描述为头顶橘子的小水豚。
旧库“元气造物、2026 年开发”的断言未获支持，已移除。

| 已核对来源 | 可追溯资源 | 还需核对 |
|---|---|---|
| [`czy666chen/lulu`](https://github.com/czy666chen/lulu) | sprite、pet.json、contact sheet、16 向预览；README 写明 9 组动作，仓库 MIT | 社区版与所选原片是否一致；原角色权利未由 MIT 清除 |
| [`lushengyin/Codex-Pets`](https://github.com/lushengyin/Codex-Pets) | `pets/lulu/spritesheet.webp`，README 说明由用户参考图转制 | 当前快照未发现根 LICENSE；不能默认为可再分发 |

帽子、短裤和比例均以选定版本的实际画面为准，不拼接两套社区版；不能把任意卡皮巴拉歌曲
当作噜噜专属原声。固定提交、blob SHA 与下载路径在机器可读清单中。

## 美团袋鼠 / 美团老鼠 / 肥嘟嘟 `meituan_meme`

分别记录品牌袋鼠、网友“美团老鼠”称呼、胖版二创及相应口癖。
**奶鼠**是另一个需独立确认的奶系角色名，不能仅因都叫“鼠”就合并。
品牌身份可从[美团标识相关规范](https://awp.meituan.com/reco/reco-fe-static-html/h5-bussiness-rules/3/4.html)
核对；这不是本项目已取得媒体授权的证明。

公开社区库 [`peibingchen/You-are-really-bold`](https://github.com/peibingchen/You-are-really-bold)
有 `pet/spritesheet.webp`、`pet/pet.json` 和 16 向预览。代码 Apache-2.0，
README 明说视觉资产另看 `NOTICE`。社区的生成提示词与源图行不能当成官方标准。
先锁定具体胖袋鼠版本，再核鼻形、耳形、比例与声音；不使用通用 kangaroo prompt。

## 牛来 `niulai` 与唐牛 `tangniu_unresolved`

[中国电影票房的《牛来》条目](https://zgdypf.zgdypw.cn/movie/detail/00103542025?from=box)
确认影片、导演信雨萌、2026-08-05 上映及小牛角色。海报可作身份核对入口，
不表示允许下载电影、分发海报或重用音轨。“妈妈，牛来”的具体声音版本另见音频表。

**唐牛尚未确认。** 本次检索未找到足以唯一映射为奶蛙生态动画角色的主来源。
可能涉及别名或同音，不是改名成牛来的依据；《食神》真人、同名账号、普通牛均不自动纳入。
保留名称并继续追具体创作者／原片；没有证据时不生成这个角色。该缺口不阻塞其他角色入库。

## 豆包 `doubao`

[官方站](https://www.doubao.com/)可确认产品身份，本次动态页面未确认奶蛙视频中的具体造型。
官方 Logo、App 头像、拟人二创版可能不同，先绑定实际参考，不能用“圆润 AI 助手”自行设计。
“豆奶 CP”先记为组合称呼，不能推导官方关系；奶系视频的“豆奶”也不自动归入官方豆包。

## 奶龙 `nailoong`

[第七印象官方 IP 页](https://www.nailoong.com/business/ipIncubation/)
分别展示基础 3D、Q 版等形象，版权署名第七印象文化传媒（深圳）有限公司。
这是核对与排错入口：官方奶龙和奶蛙必须分 ID；奶龙训练集不能当奶蛙训练集，
`nailoong` 不能作为 `naiwa` 的等价触发词。

## 奶包、奶鲸、纸人：有线索，不造标准

- 奶鲸：`NaiLoong/data/others/static.json` 有“沉思的奶鲸”条目，可追原图；
  未确认前不用“蓝色拟人鲸鱼”造一个替代者。
- 奶包与纸人：Civitai #3006514 的官方 API 已核实 MOSS Image v1.0（version 3411275），
  触发词含 `naibao`、`zhiren` 与奶鲸的 `Nai_DS_whale`。权重未下载、未加载、未实测；
  还没有据此锁定本条视频所需的真实视觉参考。元数据详见 `ip-assets.md` 和
  `research/identity-resources.json`，不能把模型卡已核实当成身份已通过。
- 旧库英文外貌段落不是官方设定。参考未到位时，不因名字已进表就让模型出场。

## 权利与证据

所有角色先按非商用二创策划；非商用不等于已获授权。
“公开流传”“原作者失联”“全民共创”都不能证明公共领域。
逐文件看媒体与录音来源，完整规则见 `licensing.md`。
