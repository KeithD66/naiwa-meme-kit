#!/usr/bin/env bash
# 拉取奶蛙梗的上游开源素材到 assets/repos/
#
# 用法:
#   ./scripts/fetch-assets.sh              # 拉取全部
#   ./scripts/fetch-assets.sh naiwa-pet    # 只拉指定仓库（可多个）
#
# 注意: 网络不稳时单个仓库可能失败，脚本会跳过并继续，重跑即可续拉。

set -uo pipefail

DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/assets/repos"

# 名称 -> 仓库（按重要性排序）
declare -a ALL=(
  "NaiLoong|https://github.com/lin-alg/NaiLoong.git"
  "codex-pet-naiwa|https://github.com/timerring/codex-pet-naiwa.git"
  "naiwa-pet|https://github.com/LynnShaw/naiwa-pet.git"
  "awesome_pets|https://github.com/Nitrogen216/awesome_pets.git"
  "NaiLong-Universe|https://github.com/Nailong-Studio/NaiLong-Universe.git"
  "nailong-classification|https://github.com/ZreXoc/nailong-classification.git"
)

mkdir -p "$DEST"

targets=("$@")
include() {
  [[ ${#targets[@]} -eq 0 ]] && return 0
  local t
  for t in "${targets[@]}"; do [[ "$t" == "$1" ]] && return 0; done
  return 1
}

ok=0; fail=0
for entry in "${ALL[@]}"; do
  name="${entry%%|*}"
  url="${entry#*|}"
  include "$name" || continue

  if [[ -d "$DEST/$name/.git" ]]; then
    echo "== $name 已存在，跳过（如需更新请删目录后重跑）"
    ok=$((ok+1))
    continue
  fi

  echo "== 拉取 $name ..."
  if git clone --depth 1 "$url" "$DEST/$name" 2>/dev/null; then
    echo "   ✓ $name"
    ok=$((ok+1))
  else
    echo "   ✗ $name 失败（网络中断？重跑本脚本可续拉）"
    rm -rf "$DEST/$name"
    fail=$((fail+1))
  fi
done

echo
echo "完成: 成功 $ok，失败 $fail"
echo "素材位置: $DEST"
echo
echo "⚠️  LICENSE 提醒:"
echo "  - naiwa-pet / awesome_pets 上游无 LICENSE，仅本地使用，勿再分发"
echo "  - NaiLoong 代码 MIT，但图片为社区共有，商用需原作者同意"
echo "  详见 ../SOURCES.md"
