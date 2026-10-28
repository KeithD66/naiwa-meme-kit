# 音频体系：按现成原声选 cue，不让模型重配

核对日期：2026-10-29。机器可读来源、候选文件、固定版本与缺口见项目根目录
`research/audio-resources.json`。清单记录来源，不表示每项都已下载或已获发布许可。

## 必须执行

1. **奶蛙的声音是一套网络素材，不是一个 TTS 音色。** 脚本引用下方 cue ID，
   从具体文件取片段；不要输入「生成奶蛙魔性笑声」让视频模型重新配一段。
2. 图生视频优先只生成画面；已有原声锁到剪辑时间轴。模型自动生成的对白、笑声或 BGM，
   最终用选定现成文件替换。不要用语音克隆把新台词冒充经典原声。
3. 拼音名、空耳字和角色名不能证明版本正确。必须试听，记录文件、源地址、SHA-256、
   使用区间及是否含 BGM；未经试听一律写「候选」。本次研究没有试听，不预填匹配结论。
4. 文件存在、匹配目标、允许下载、允许改编/分发/商用分别核对。
   代码 MIT、公开流传和非商用均不能代替录音许可。
5. 第三方音频保留在 `assets/repos/` 或 `assets/private/`，不加入本项目 Git。
   无许可录音及仅供个人娱乐的电影片段不打成可再分发音效包。
6. 找不到匹配原声时保留静音/字幕或换已核验 cue，不能用合成声音填缺口。

## 1. 奶蛙核心口癖与笑声

「建议落点」是本库的剪辑建议，不是宣称梗有固定剧情。不同空耳字只作检索别名，
不当日文原台词或官方译文。路径以项目根目录为准。

| cue ID | 检索别名 | 本地候选（`assets/repos/NaiLoong/assets/audio/` 内） | 建议落点 / 核对状态 |
|---|---|---|---|
| `naiwa.laugh` | 齁齁齁、哟齁齁齁、捧腹大笑 | `nailong_laugh.mp3`，15.65 秒 | 语音表写「咳哈哈哈哈~」。反转破功/结尾回扣；未试听，不能直接称目标原版。 |
| `naiwa.hola_ganbadie` | Hola、嘎巴跌、ganbadie | `hola_ganbadie.mp3`，1.81 秒 | 语音表有对应标签；出场/招呼/突然接话。 |
| `naiwa.gajiaosai` | 嘎脚塞、卡脚塞、gajiaosai / gajiaosei | `gajiaosai.mp3`，1.11 秒 | 短促动作/切镜；不同库的音色版本先比对。 |
| `naiwa.gagadilashui` | 嘎嘎滴啦水、嘎嘎滴辣虾、gagadilaxia | `gagadilashui.mp3`，1.30 秒 | 口癖连击/反应；不同目录的拼音不代表同一录音。 |
| `naiwa.dupu` | 嘟噗、dupu | `dupu.mp3`，1.19 秒 | 动作句号/尴尬停顿后的短点。 |

依据：[NaiLoong 奶蛙语音表](https://github.com/lin-alg/NaiLoong/blob/main/data/naiwa/voice.json)。
共享音频目录是 **奶蛙表 5 个文件 + 奶蛋表 1 个文件**，不是「六种经典笑声」，也不是六条都属奶蛙。
其中 `andi.mp3` 明确登记在奶蛋语音表，见下节；原始录音权利链未见逐文件说明。

### 同一 cue 的其他现成版本

- [yugh6/Naiwa](https://github.com/yugh6/Naiwa) 的 `原版笑声.wav`：README 称从原视频提取，
  已核对到 622482 字节文件，是核对流传版的优先候选。`LICENCE` 为 PolyForm Noncommercial，
  录音原始第三方权利仍须核对；无需下载或运行 `.exe`。
- `assets/repos/naiwa-pet/public/pets/naiwa/audio.m4a`：与该库 438 帧序列同源，适合核对捧腹动作同步；
  无 LICENSE，仅本地使用，勿再分发。
- [Diyeego/naiwa-pet](https://github.com/Diyeego/naiwa-pet) 的 `naiwa/voice/` 有
  `andi (1).mp3`、`gagadilaxia.mp3`、`gajiaosei.mp3`、`ganbadie.mp3`、`laugh.mp3`，
  另有 `naiwa/laugh.m4a`。这是额外版本集；无 LICENSE，README 要求不商用。
  `andi (1).mp3` 虽在 `naiwa/voice/`，仍只作奶蛋「安迪」的跨版本待试听候选，
  不凭目录名推翻奶蛋语音表归属，也不放进奶蛙默认声音集合。
- [wallpaper](https://github.com/Nailong-Studio/wallpaper) 的 `audio/` 实际两项：
  `奶蛙-桌宠笑声.wav`、`奶蛙-爆笑原声.mp3`。前者源于 Codex-Voice-Input；后者与
  WencueCryforme/NaiWa-Universe 的 `dist/sound/奶蛙爆笑合集/奶蛙爆笑.mp3` Git blob 相同，按镜像去重。
- [Codex-Voice-Input 素材说明](https://github.com/liaosongjie/Codex-Voice-Input/blob/main/assets/pet/ASSET-NOTICE.md)
  明确将作者制作的动画与 `laugh.wav` 以 MIT 发布。这是作者社区版本，未试听匹配前不能替代目标原声。
  另四个 `busy/error/listen/target.wav` 是脚本生成通知音，不列作经典口癖。
- [DevourerM/dsh-naiwa-theme](https://github.com/DevourerM/dsh-naiwa-theme) 的
  `assets/naiwa-complete-laugh.mp3` 与 `assets/naiwa-send-crawl.mp3` 是短笑声/爬行音候选。
  [ASSETS_NOTICE](https://github.com/DevourerM/dsh-naiwa-theme/blob/main/ASSETS_NOTICE.md)说明音效剪自网络视频，
  MIT 只覆盖原创代码，未转授原录音权利。

## 2. 生态联动语音

| cue ID | 角色 / 内容 | 可追溯来源 | 使用要求 |
|---|---|---|---|
| `naidan.andi` | 奶蛋：安~迪~ | [奶蛋语音表](https://github.com/lin-alg/NaiLoong/blob/main/data/naidan/voice.json)，`assets/repos/NaiLoong/assets/audio/andi.mp3`，1.61 秒 | 目录映射已确认，[manifest](https://github.com/lin-alg/NaiLoong/blob/main/data/manifest.json)也有同一口癖。录音版本仍待试听，但不是身份未知，更不是奶蛙默认口癖。 |
| `niulai.mama` | 牛来：妈妈 | [dsh-niu-lai](https://github.com/jxwb125646/dsh-niu-lai)，`assets/妈妈.mp3` | 原仓 NOTICE 明确电影录音不适用代码 MIT，仅个人非商业粉丝用途；不得仿配。 |
| `niulai.name` | 牛来：牛来 | 同仓 `assets/牛来.mp3` | 与上一句可做呼唤→突然打断；分开试听、分别记来源。 |
| `niulai.mama` / `niulai.name` 的 WAV 候选 | 同梗另一剪辑版本 | [dsh-niulai-sound](https://github.com/isheng-eqi/dsh-niulai-sound)，`assets/mama.wav` / `niulai.wav` | README 给出约 6.2 秒 / 1.8 秒并称电影原声；代码 MIT 不能当电影授权，不安装插件也能核对。 |
| `meituan.feidudu` | 袋鼠：胆子肥嘟嘟 | [传播视频候选](https://www.douyin.com/video/7677438628561811855) | 仅来源页线索；尚未认证原始发言者、干净音轨及许可，勿冒称袋鼠官方配音。 |
| `mai.remix` | 不知火舞变调语音体系 | 核心短文件与[传播线索](https://www.douyin.com/shipin/7618380794075105323) | 先核对文件是否为所需既有变调版本；不能仅凭搜索页认定原配音者、出处或变速参数。 |
| `lulu.voice` / `naifen.voice` / `tangniu.voice` | 噜噜、奶粉、唐牛 | 尚无确认整套原声与许可的包 | 角色身份/原片未确认前用字幕；不补造口癖、不将唐牛与牛来合并。奶蛋已有上面的目录映射，不混入缺失身份项。 |

电影录音的边界见 [NOTICE](https://github.com/jxwb125646/dsh-niu-lai/blob/main/NOTICE.md)。
这些文件是本地研究候选，不在本仓库重发。

## 3. BGM 先锁版本，再卡点

| cue ID | 名称 / 版本问题 | 已核实证据与当前状态 |
|---|---|---|
| `bgm.montagem_alquimia` | 《MONTAGEM ALQUIMIA》；原速/Slowed/Super Slowed 要分开 | [发行页](https://music.apple.com/us/album/montagem-alquimia-ep/1867871586)列 h6itam、n7san7os、Mc Menor Do Alvorada；[新榜报道](https://cp.newrank.cn/article/detail/34447)关联唐嘉琦舞步。曲名已核对，目标版本及配乐许可未定，未下载。原库《Monica / jim okimia》不作确认曲名。 |
| `bgm.dagou` | 大狗大狗是衍生曲族，不是唯一录音 | 不同大狗曲有不同原曲与二创作者；[创作者视频示例](https://www.bilibili.com/video/BV1oKNP6pEiS/)明确标其改编来源，须逐曲锁版本与使用范围。 |
| `bgm.tea_shake` | 来杯好茶摇一摇：流传名称不等于已核实正式曲名 | [品牌微博转载入口](https://www.sina.cn/news/detail/5291574986805952.html)帮助回溯联名宣传。原片与可复用音源未锁，不自动下载或仿配。 |
| `bgm.mermaid_tears` | 人鱼的眼泪 | WencueCryforme/NaiWa-Universe 有同名 MP3；仅文件名证据，词曲/录音/版本权利未知，不因仓库 MIT 作默认可用配乐。 |

《MONTAGEM ALQUIMIA》发行页标注 ℗ 2026 Black 17 Media。平台可播放不等于允许下载、改编、
跨平台配乐或商用。先确认平台曲库使用范围再锁时间轴，不为适配脚本编造 BPM、变速比例或切点。

## 4. 用声音制造反差的编排模板

以下是编排方法，不是新增音效，也不要求把每条视频塞满音轨：

- **出场识别**：短前摇 → 一条已核验口癖，先让观众认出音色。
- **雷霆启动**：镜头动作压到现成 BGM 的首个明确重拍；舞步给音乐留完整节奏。
- **突然打断**：长 cue 尚未结束时切到短 cue，配明确动作/表情；例如妈妈→牛来，不改写为新对白。
- **反转破功**：先断乐留白，再放捧腹原笑声；别把大笑埋在多条同时发声的对白下。
- **回扣循环**：同一短 cue 第二次出现时改变画面含义；尾端回首帧，留明确落点。
- **密度控制**：动作、字幕、语音、BGM 同时出现时指定主信息，其余让位。
  刺激来自节奏和反差，不把统一增益、爆音或随机堆叠当雷霆风格。

后续记录 cue 入出点、留白、BGM 压低区间及是否保留原声尾气；具体响度/时码以实际试听为准。
本资料不自行启动制作，制作范围以当前用户授权为准；梗原声必须现成，不得仿配。

## 5. 排除项与明确缺口

- [Neta 八段笑声页](https://neta.art/explore/work/zh/milk-frog-laugh)明确写浏览器即时合成，
  **不是网络经典原录音包**；不要录网页声音来冒充原版。
- [Marshall-Jimmy/naiwa-universe](https://github.com/Marshall-Jimmy/naiwa-universe)有 manifest 与下载器，
  需要人工填写音源，缺省可静默降级；不是已经带全套音效的资源包。
- App Store「奶蛙音乐键盘」可交叉核对音效术语，不能证明允许提取/重发内置资源；
  不通过购买、安装、拆包或绕过服务获取音效。
- 未发现同时涵盖全生态、全部雷霆 BGM 且逐文件明确授权的万能整包。
  本库按 cue → 多来源版本 → 文件 → 试听/许可状态补齐，不掩盖缺项。
- 优先待补：核心口癖目标变调版试听；奶蛋「安迪」的跨来源版本试听；「戏弄壁诺机」精确现成文件；
  肥嘟嘟原片；BGM 目标舞步版本；噜噜/奶粉/唐牛经确认身份对应的原声。
