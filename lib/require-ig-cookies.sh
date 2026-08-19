# Shared by transcribe-reel.sh and transcribe-carousel.sh.
# Never echo cookie values.

ig_cookies_help() {
  echo "No Instagram OAuth / Graph API / Connect Instagram." >&2
  echo "Scripts need a Netscape jar at ${HOME}/.config/ig-cookies.txt (HttpOnly sessionid)." >&2
  echo "Recipe: docs/auth.md  —  python3 scripts/check-setup.py" >&2
  echo "Do not commit, log, echo, or paste the file." >&2
}

require_ig_cookies() {
  COOKIES="${HOME}/.config/ig-cookies.txt"
  if [[ ! -f "$COOKIES" ]]; then
    echo "Cookie file missing: $COOKIES" >&2
    ig_cookies_help
    exit 1
  fi
}
