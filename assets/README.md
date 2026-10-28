# assets/

素材落地目录。**仓库不含任何第三方二进制素材**，请先运行：

```bash
./scripts/fetch-assets.sh
```

拉取后结构：

```
assets/
├── repos/                 # 由 fetch-assets.sh 生成（已在 .gitignore 中）
│   ├── NaiLoong/          # 笑声 mp3 ×6、表情包目录 JSON
│   ├── codex-pet-naiwa/   # 逐帧 sprite + previews
│   ├── naiwa-pet/         # ⚠️ 438 帧动画 + audio.m4a（上游无 LICENSE）
│   └── awesome_pets/      # ⚠️ naifrog 桌宠素材（上游无 LICENSE）
└── private/               # 私有素材（视觉基准图等，不入库）
```

## 视觉基准图

奶蛙的标准长相请自行保存一份到 `assets/private/`（该目录已 gitignore）：

**黄梨形身体、奶油色大肚皮、灰绿色圆形大眼、一字横嘴、3D 卡通质感。**

在搜索引擎搜「奶蛙 表情包」或访问 neta.art 奶蛙宇宙即可获得参考图。
