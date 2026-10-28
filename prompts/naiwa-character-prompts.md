# 形象 Prompt 速查卡

> 以下英文特征描述摘自开源 LoRA（Civitai #3006514 `Nai-Animals MOSS 多角色`）的 trigger 描述，
> 可直接脱离 LoRA 喂给任意图像模型复现形象。出处见 `SOURCES.md`。

## 奶蛙 naiwa（主角）

```
naiwa, a golden-yellow pear-shaped 3D mascot with a seamless neckless head,
pale grey-green circular eyes, black pupils, a thin horizontal mouth,
a large cream-colored belly patch, olive-brown four-fingered hands,
and broad three-toed feet
```

**中文要点**：金黄梨形 3D 吉祥物、头身一体无脖子、灰绿色圆眼黑瞳、一字横嘴、乳白色大肚皮、橄榄褐四指手、三趾大脚。

**动作提示**：`laughing hysterically`（捧腹大笑）、`blank stare`（看透一切的呆滞）、`holding belly`。

## 奶龙 nailoong

```
nailoong, a plump yellow 3D cartoon mascot with a large rounded head,
glossy green eyes, a small mouth, a cream-colored belly, short chubby limbs,
three small brown claws on each hand and foot, and pink palm pads
```

## 奶包 naibao

```
naibao, a yellow 3D mascot with a human-like face, short side-parted
dark brown bob hair, large dark brown eyes, eyelashes and arched eyebrows,
a plump yellow body, a cream belly patch,
and dark grey-brown hoof-like hands and feet
```

## 奶鲸 Nai_DS_whale

```
Nai_DS_whale, a plump blue anthropomorphic whale mascot with a large white
chest and belly, curved white facial markings with small white dots,
a wide mouth, dark grey four-fingered hands, a dorsal fin,
and an upright whale tail
```

## 纸人 zhiren

```
zhiren, a faceted papercraft humanoid with a peach-colored paper face,
pupil-less white eyes, thick black eyebrows, red lips, black paper hair
and a gold headband, wearing a royal blue traditional Chinese paper jacket
and trousers with circular gold medallions, gold frog-button closures,
and black shoes with white soles
```

## 通用质量后缀

```
3D render, soft studio lighting, smooth plastic surface, clean background,
high detail, character turnaround / single subject
```

## 生成参数建议

- LoRA 用 Civitai #2802348 时触发词 `NAIWA`；与其他 LoRA 叠加建议拉高强度。
- 需要多角度一致：**先用三视图或 `.obj` 渲参考帧**，再做图生视频，避免"转身就崩"。

---

## ⚠️ 未建档

**唐牛**：形象尚未确认，暂无 prompt。确认形象后补在此处。
