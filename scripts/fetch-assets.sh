#!/usr/bin/env bash
# 下载第三方素材到被 Git 忽略的 assets/，不执行上游程序。
# 无参数：七个上游仓库 + library/downloads.json 中的小型现成素材。
# ./scripts/fetch-assets.sh --list
# ./scripts/fetch-assets.sh wallpaper curated
# RETRY=3 GITHUB_PROXY=https://ghfast.top ./scripts/fetch-assets.sh wallpaper
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${ROOT}/assets/repos"
RETRY="${RETRY:-4}"
export GIT_HTTP_LOW_SPEED_LIMIT="${GIT_HTTP_LOW_SPEED_LIMIT:-1000}"
export GIT_HTTP_LOW_SPEED_TIME="${GIT_HTTP_LOW_SPEED_TIME:-120}"
ALL=(
  "NaiLoong|https://github.com/lin-alg/NaiLoong.git"
  "codex-pet-naiwa|https://github.com/timerring/codex-pet-naiwa.git"
  "naiwa-pet|https://github.com/LynnShaw/naiwa-pet.git"
  "awesome_pets|https://github.com/Nitrogen216/awesome_pets.git"
  "NaiLong-Universe|https://github.com/Nailong-Studio/NaiLong-Universe.git"
  "nailong-classification|https://github.com/ZreXoc/nailong-classification.git"
  "wallpaper|https://github.com/Nailong-Studio/wallpaper.git"
)
if [[ "${1:-}" == "--list" ]]; then
  for entry in "${ALL[@]}"; do printf '%s\n' "${entry%%|*}"; done
  printf '%s\n' curated
  exit 0
fi
if ! [[ "${RETRY}" =~ ^[1-9][0-9]*$ ]] || (( RETRY > 20 )); then
  echo "RETRY 必须是 1–20 的整数" >&2; exit 2
fi
targets=("$@")
for target in "$@"; do
  known=0
  [[ "${target}" == "curated" ]] && known=1
  for entry in "${ALL[@]}"; do [[ "${target}" == "${entry%%|*}" ]] && known=1; done
  if [[ "${known}" == 0 ]]; then echo "未知素材目标: ${target}（用 --list 查看）" >&2; exit 2; fi
done
include() {
  [[ ${#targets[@]} -eq 0 ]] && return 0
  local target
  for target in "${targets[@]}"; do [[ "${target}" == "$1" ]] && return 0; done
  return 1
}
git_source() {
  if [[ -n "${GITHUB_PROXY:-}" ]]; then
    git -c "url.${GITHUB_PROXY%/}/https://github.com/.insteadOf=https://github.com/" "$@"
  else
    git "$@"
  fi
}
stage=""
cleanup() { if [[ -n "${stage}" && -d "${stage}" ]]; then rm -rf -- "${stage}"; fi; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -p "${DEST}"
ok=0; fail=0
for entry in "${ALL[@]}"; do
  name="${entry%%|*}"
  url="${entry#*|}"
  include "${name}" || continue
  if [[ -e "${DEST}/${name}" ]]; then
    if [[ -d "${DEST}/${name}/.git" ]] && git -C "${DEST}/${name}" rev-parse --verify HEAD >/dev/null 2>&1; then
      actual="$(git -C "${DEST}/${name}" config --get remote.origin.url || true)"
      if [[ "${actual%.git}" == "${url%.git}" ]]; then
        echo "== ${name} 已存在，保留本地版本（不覆盖修改）"
        ok=$((ok+1)); continue
      fi
    fi
    echo "== ${name} 路径已存在但不是预期的完整仓库；保留文件，请检查后重试" >&2
    fail=$((fail+1)); continue
  fi
  echo "== 拉取 ${name}（最多 ${RETRY} 次）..."
  success=0
  for ((i=1; i<=RETRY; i++)); do
    stage="$(mktemp -d "${DEST}/.${name}.partial.XXXXXX")"
    printf '   尝试 %d/%d ... ' "${i}" "${RETRY}"
    if git_source clone --depth 1 "${url}" "${stage}/repo" >"${stage}/clone.log" 2>&1 \
      && git -C "${stage}/repo" rev-parse --verify HEAD >/dev/null 2>&1; then
      if [[ -e "${DEST}/${name}" ]]; then
        echo "目标被其它进程创建，保留现有目录并停止" >&2
        break
      fi
      mv "${stage}/repo" "${DEST}/${name}"
      echo "成功"; success=1
      cleanup; stage=""; break
    fi
    echo "失败"
    tail -n 3 "${stage}/clone.log" >&2
    cleanup; stage=""
    (( i < RETRY )) && sleep 2
  done
  if [[ "${success}" == 1 ]]; then ok=$((ok+1)); else fail=$((fail+1)); fi
done
if include curated; then
  echo "== 拉取固定版本的精选素材（不含程序或权重）..."
  if python3 "${ROOT}/scripts/fetch-curated.py" --retries "${RETRY}"; then
    ok=$((ok+1))
  else
    fail=$((fail+1))
  fi
fi
printf '\n完成: 成功 %d，失败 %d\n素材位置: %s\n' "${ok}" "${fail}" "${DEST}"
echo "媒体许可逐项看 SOURCES.md 与 library/downloads.json；无许可及其衍生素材仅本地参考。"
(( fail == 0 ))
