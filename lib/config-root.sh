# Shared install-root resolver. Source from repo scripts.
# IG_REELS_ROOT wins, then the current name, then legacy symlinks.
if [[ -n "${IG_REELS_ROOT:-}" ]]; then
  CONFIG_ROOT="$IG_REELS_ROOT"
elif [[ -e "${HOME}/.config/ig-yt-x-knowledge-extract" ]]; then
  CONFIG_ROOT="${HOME}/.config/ig-yt-x-knowledge-extract"
elif [[ -e "${HOME}/.config/ig-reels-knowledge-extract" ]]; then
  CONFIG_ROOT="${HOME}/.config/ig-reels-knowledge-extract"
else
  CONFIG_ROOT="${HOME}/.config/ig-reel"
fi
