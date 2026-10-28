# 素材来源、证据与许可证

核验日期：2026-10-29。本项目提交索引、工具与知识库；第三方二进制媒体由脚本落到被忽略的
`assets/repos/` 或 `assets/private/`，不随本项目重新打包分发。

## 权利与下载记录分开看

- `library/downloads.json`：实际精选下载的固定 URL、内容哈希、来源与使用限制。
- `library/catalog.json`：`library.py index` 根据本机文件重建，区分本地与远程目录。
- `research/identity-resources.json`、`audio-resources.json`、`ecosystem-resources.json`：
  查询到的来源和核验状态；其中的候选不自动代表已经下载或可发布。
- `production/asset-manifest.json` 是初次接入时的快照；当前文件状态以重建索引与下载报告为准。

固定提交与哈希用于复现和核对内容，不证明发布者有权授权全部底层角色、图片或录音。
无参数拉取不会把上游仓库更新到最新版本；已有仓库保留本地状态。

## 仓库型上游

| 上游 | 实际用途 | 已读到的许可边界 |
|---|---|---|
| [lin-alg/NaiLoong](https://github.com/lin-alg/NaiLoong) | 奶蛙／奶蛋语音、远程表情目录、桌宠 | 代码 MIT；README 区分社区引用图与自带图。音频缺少逐录音权利链；桌宠又引用 codex-pet-naiwa。共享目录是语音／笑声混合集，不是全套笑声。 |
| [timerring/codex-pet-naiwa](https://github.com/timerring/codex-pet-naiwa) | 现成 sprite 与动作／注视预览 | README 的 MIT **只覆盖原创内容**，Credits 第三方素材明确排除。不能把重新打包当作原素材许可。 |
| [LynnShaw/naiwa-pet](https://github.com/LynnShaw/naiwa-pet) | 原片、分帧与提取音频 | 未见 LICENSE；仅本地使用，勿再分发。 |
| [Nitrogen216/awesome_pets](https://github.com/Nitrogen216/awesome_pets) | 奶蛙桌宠 sprite | README 明确尚未加许可证、保留权利；仅本地使用，勿再分发。 |
| [Nailong-Studio/NaiLong-Universe](https://github.com/Nailong-Studio/NaiLong-Universe) | 站点、预览、素材索引 | 仓库有 MIT，README 另称不做商业用途；完整原图库另引 wallpaper。不能由网站许可覆盖全部媒体。 |
| [Nailong-Studio/wallpaper](https://github.com/Nailong-Studio/wallpaper) | 梗图、动作、视频、音频原图库及索引 | 查 `SOURCES.md` 和真实同名附录，例如 `视频.mp4.txt`、`图像.png.txt`；逐件来源不一，部分仅追溯到网络图床。 |
| [ZreXoc/nailong-classification](https://github.com/ZreXoc/nailong-classification) | 奶龙识别模型、示例图和数据集线索 | README 限娱乐学习；完整 Hugging Face 数据集是外链。它是奶龙数据，不是奶蛙身份权重。 |

## 精选媒体与补充来源

具体选中的文件和版本以 `library/downloads.json` 为准。以下是来源边界，不是统一放行清单。

| 来源 | 已核实的声明或限制 |
|---|---|
| [yugh6/Naiwa](https://github.com/yugh6/Naiwa) | `原版笑声.wav` 是现成候选，README 称从原视频提取；`LICENCE` 为 PolyForm Noncommercial。文件名不是试听或第三方权利证明，不运行 exe。 |
| [Diyeego/naiwa-pet](https://github.com/Diyeego/naiwa-pet) | 现成短语音和笑声的另一版本；未见 LICENSE，README 要求学习交流、勿商用。目录归属不代替角色与录音核对。 |
| [liaosongjie/Codex-Voice-Input](https://github.com/liaosongjie/Codex-Voice-Input/blob/main/assets/pet/ASSET-NOTICE.md) | 作者声明自制动画与 laugh.wav 使用 MIT；这是其社区版本，不能因此认定与目标原声相同或清除角色原型权利。脚本合成的通知音不归入原梗口癖。 |
| [DevourerM/dsh-naiwa-theme](https://github.com/DevourerM/dsh-naiwa-theme/blob/main/ASSETS_NOTICE.md) | 原创代码 MIT；声音剪自网络视频，未转授原录音权利。 |
| [jxwb125646/dsh-niu-lai](https://github.com/jxwb125646/dsh-niu-lai/blob/main/NOTICE.md) | 牛来电影录音明确排除于代码 MIT；只声明个人非商业粉丝用途，不能视作电影权利人授权。 |
| [isheng-eqi/dsh-niulai-sound](https://github.com/isheng-eqi/dsh-niulai-sound) | 妈妈／牛来的 WAV 版本线索；代码开源不等于电影音轨许可。 |
| [czy666chen/lulu](https://github.com/czy666chen/lulu) | 社区噜噜动作与多方向图集，仓库 MIT；底层商业角色权利另核。 |
| [lushengyin/Codex-Pets](https://github.com/lushengyin/Codex-Pets) | 用户参考图转制噜噜；当前快照未见根 LICENSE，且社区描述与官方水豚定义有出入。 |
| [peibingchen/You-are-really-bold](https://github.com/peibingchen/You-are-really-bold/blob/main/NOTICE) | 代码 Apache-2.0；NOTICE 明确不授第三方角色、商标和外部视觉材料权利。肥嘟嘟媒体先作本地候选。 |
| [busgm666-cloud/naidan-slingshot](https://github.com/busgm666-cloud/naidan-slingshot) | 奶蛋现成社区变体；部分是程序重着色或另行生成，原梗身份与底层媒体限制仍需核对。 |
| [Maple498/nai-wa-codex-pet](https://github.com/Maple498/nai-wa-codex-pet/blob/main/ASSET-LICENSE.md) | 作者自制像素动画 CC BY 4.0，须署名；明确不保证角色原型第三方权利，不能替代网传 3D 版。 |
| [TarelX/Milk-Frog](https://github.com/TarelX/Milk-Frog/blob/main/NOTICE.md) | 自身设计、帧和工具有 MIT 声明；同名不证明造型与用户目标相同。 |

## 官方身份与网络线索

| 对象 | 可追溯主来源 | 本次结论 |
|---|---|---|
| 水豚噜噜 | [CLE 授权展目录](https://www.chinalicensingexpo.com/cn/product/1849) | 列出铁罐（北京）文化传媒有限公司。旧库“元气造物、2026 开发”说法移除。 |
| 奶龙 | [第七印象 IP 页](https://www.nailoong.com/business/ipIncubation/) | 官方奶龙与奶蛙分别归档，不借奶龙数据集填奶蛙参考。 |
| 美团袋鼠 | [品牌标识相关规范](https://awp.meituan.com/reco/reco-fe-static-html/h5-bussiness-rules/3/4.html) | 品牌版、民间胖版与奶鼠不自动等同。 |
| 牛来 | [中国电影票房条目](https://zgdypf.zgdypw.cn/movie/detail/00103542025?from=box) | 电影小牛可识别，不自动解释为唐牛。 |
| 豆包 | [官方站](https://www.doubao.com/) | 官方产品可确认，具体联动视频视觉版本仍要选图。 |
| 奶粉／唐牛 | `research/ecosystem-resources.json` | 奶粉存在角色与粉丝双义；唐牛身份未定，不让模型凭名补图。 |

## 三视图、模型与音乐

- [Neta Wiki](https://neta.art/app/milk-frog-wiki) 的现成三视图候选已发现标签错误与形象差异；
  站内 official 不是角色权利人背书。浏览器即时合成笑声也不是网络原声包。
- [嘉立创给定页](https://model.jlc-3dp.cn/modelDetail/037262f117974eacb739974e67344c53.html)
  本次仅确认到通用页面壳与登录入口，未核实所称奶蛙／奶蛋 `.obj` 文件，未下载模型或取得许可。
- Civitai [#2802348](https://civitai.com/models/2802348)、[#3006514](https://civitai.com/models/3006514)
  的官方 API 元数据已记录于 `research/identity-resources.json`；权重未默认下载／实测。
  底模、运行环境、访问和下游许可须按实际版本核对。
- 《MONTAGEM ALQUIMIA》的[发行页](https://music.apple.com/us/album/montagem-alquimia-ep/1867871586)
  与[舞步报道](https://cp.newrank.cn/article/detail/34447)支持曲名关联；具体速度版与配乐范围未定。
  平台可播放不等于可以下载或跨平台配乐。

本项目自己的代码与文档适用根目录 MIT LICENSE，不主张第三方角色或录音权利。
发布前按 `skill/references/licensing.md` 逐项检查；原素材与含其内容的成片都需遵守相应范围。
