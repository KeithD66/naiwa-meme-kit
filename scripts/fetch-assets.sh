#!/usr/bin/env bash
# 拉取奶蛙梗的上游开源素材到 assets/repos/
#
# 用法:
#   ./scripts/fetch-assets.sh              # 拉取全部
#   ./scripts/fetch-assets.sh naiwa-pet    # 只拉指定仓库（可多个）
#
# 稳定性: 网络不稳/大仓库（NaiLong-Universe、nailong-classification 各 ~90MB）
#         极易中途断线。本脚本对失败仓库自动重试 RETRY 次，单仓库失败不影响其余。
#
# 注意: bash 在 set -u 下会把 `$name` 后紧跟的全角标点误并入变量名，故本文件所有
#       变量一律写成 `${name}` 形式，避免 UTF-8 变量边界歧义。

set -uo pipefail

DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/assets/repos"
RETRY="${RETRY:-4}"

# git 传输超过 120 秒无进展即判定卡死，提前失败进入重试
export GIT_HTTP_LOW_SPEED_LIMIT=1000
export GIT_HTTP_LOW_SPEED_TIME=120

# 名称 -> 仓库
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

  if [[ -d "$DEST/$name/.git" ]] && [[ "$(git -C "$DEST/$name" rev-parse --is-inside-work-tree 2>/dev/null)" == "true" ]]; then
    echo "== ${name} 已存在，跳过（如需更新请删目录后重跑）"
    ok=$((ok+1))
    continue
  fi

  echo "== 拉取 ${name}（最多重试 ${RETRY} 次）..."
  success=0
  for ((i=1; i<=RETRY; i++)); do
    rm -rf "$DEST/$name"
    printf "   尝试 %d/%d ... " "$i" "$RETRY"
    if git clone --depth 1 "$url" "$DEST/$name" >/dev/null 2>&1; then
      printf "成功\n"
      success=1
      break
    else
      printf "失败\n"
      sleep 2
    fi
  done

  if [[ $success -eq 1 ]]; then
    echo "   ✓ ${name} 完成"
    ok=$((ok+1))
  else
    echo "   ✗ ${name} ${RETRY} 次均失败（网络问题，重跑本脚本可续拉）"
    rm -rf "$DEST/$name"
    fail=$((fail+1))
  fi
done

echo
echo "完成: 成功 ${ok}，失败 ${fail}"
echo "素材位置: ${DEST}"
echo
echo "LICENSE 提醒:"
echo "  - naiwa-pet / awesome_pets 上游无 LICENSE，仅本地使用，勿再分发"
echo "  - NaiLoong 代码 MIT，但图片为社区共有，商用需原作者同意"
echo "  详见 ../SOURCES.md"
