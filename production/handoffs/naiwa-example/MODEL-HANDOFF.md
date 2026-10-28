# 给视频模型的素材交接草案

状态：draft_only；不得直接启动生成或发布。

模式：existing-edit
项目根目录：`/Users/denglx/Desktop/video/naiwa-meme-kit`

## 角色A：奶蛙 (naiwa)

位置：待指定
- 视觉: naiwa-frame-0000 → `assets/repos/naiwa-pet/public/pets/naiwa/frames/frame_0000.webp`；SHA-256: 0186113e8cdf7e5b8109b7679eaa17fc3523e664f62010ed8db0894f858e0332
- 视觉: naiwa-frame-0200 → `assets/repos/naiwa-pet/public/pets/naiwa/frames/frame_0200.webp`；SHA-256: 36118d59ec8ae570fa31e017012a0628503e1cf38bc06cb00642438be6695b28
- 声音: nai-hub-nailong_laugh → `assets/repos/NaiLoong/assets/audio/nailong_laugh.mp3`；SHA-256: 716c2d58d02c6543057a7adf6637b8224886f6f0d7c06ffa34bfdf18dde72c33

## 当前阻塞
- 声音尚未试听匹配: nai-hub-nailong_laugh

## 给模型的指令
- 读取并实际查看每个characters条目自己的reference_assets，不用文字另造形象。
- 每个角色只使用其绑定的身份、动作与录音；不串脸、串色，不把奶蛋andi交给奶蛙。
- screen_position未指定时先确定位置；工具须逐角色接收真实附件，不凭多个名字融合形象。
- 仅使用audio_assets中的既有录音，不合成原作语音，不自动生成缺失BGM。
- 所有文件路径相对project_root，传给视频工具时必须上传真实文件。
- 本文件是交接草案，不代表素材有公开分发许可；不执行生成、剪辑或发布。
