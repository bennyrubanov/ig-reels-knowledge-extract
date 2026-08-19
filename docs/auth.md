# Auth — no Instagram (or X) OAuth

There is **no** Instagram app grant, Graph API, “Connect Instagram,” or official download API in this repo. Same for X. The download scripts reuse a **browser session** you already have.

Agents: if the jar is missing, **stop** and give the human this page. Do not invent OAuth. Do not log into Google or Instagram as the agent. Do not commit, log, echo, or paste cookie files.

Cloud / Codespace / a VM without the operator’s Chrome **cannot** download Instagram. Ask them to run setup on a machine that is logged in.

## What the scripts actually read

| Site | File | Required? |
|------|------|-----------|
| Instagram reels + carousels | `~/.config/ig-cookies.txt` (`%USERPROFILE%\.config\ig-cookies.txt` on Windows) | **Yes.** `python scripts/igx.py reel` / `carousel` exit if it is missing. |
| X / Twitter video | `~/.config/x-cookies.txt` | Optional. Thread text still comes from FixTweet. |

Netscape (Mozilla) format. First line `# Netscape HTTP Cookie File` or `# HTTP Cookie File`. On Unix, `chmod 600`. Instagram needs the HttpOnly **`sessionid`** row. An export that skips HttpOnly will 403 / empty-media while the post is still live.

The scripts pass that path to `yt-dlp --cookies`. They do **not** call `--cookies-from-browser` unless a human does that themselves.

## Write the Instagram jar (pick one)

### A — Instagram-only export (preferred)

1. In Chrome (or Firefox), log into [instagram.com](https://www.instagram.com/) as the account that can see the posts.
2. On an instagram.com tab, export **Netscape cookies**, **including HttpOnly**. A common tool is the “Get cookies.txt LOCALLY” extension. Cookie-Editor and similar work if they actually write HttpOnly `sessionid`.
3. Save the file as `~/.config/ig-cookies.txt` (Windows: `%USERPROFILE%\.config\ig-cookies.txt`):

```bash
mkdir -p ~/.config
# move/copy the export onto:
#   ~/.config/ig-cookies.txt
chmod 600 ~/.config/ig-cookies.txt   # Unix; skip on Windows
```

Then check **without printing values**:

```bash
python3 scripts/check-setup.py
```

### B — Dump from Chrome via yt-dlp (attended)

This writes **every site’s** cookies from that Chrome profile. Prefer A. If you use B, filter to Instagram before keeping the file, and delete the full dump.

On macOS the Keychain prompt must be **Allow**, not Always Allow. A human has to click it. Close extra Chrome instances if yt-dlp says the cookie DB is locked.

```bash
mkdir -p ~/.config /tmp
# Full-profile dump (secret). Do not commit or paste.
yt-dlp --cookies-from-browser chrome:Default \
  --cookies /tmp/all-cookies.txt \
  --skip-download "https://www.instagram.com/"
# Keep Instagram rows only:
awk 'BEGIN{print "# Netscape HTTP Cookie File"}
     $0 ~ /^# Netscape/ || $0 ~ /^# HTTP Cookie/ {next}
     $1 ~ /instagram\.com/ {print}' /tmp/all-cookies.txt > ~/.config/ig-cookies.txt
chmod 600 ~/.config/ig-cookies.txt
rm -f /tmp/all-cookies.txt
python3 scripts/check-setup.py
```

Use `chrome:"Profile 1"` (or another named profile) if Instagram is not in Default.

**One-off download** without writing a jar (human at Keychain):

```bash
yt-dlp --cookies-from-browser chrome:Default "<REEL_URL>"
```

The Python CLI (`scripts/igx.py`) still will not run Instagram downloads until `~/.config/ig-cookies.txt` exists. This one-off is only for debugging yt-dlp.

## X (optional)

Same Netscape recipe → `~/.config/x-cookies.txt`. Only needed when yt-dlp hits a login wall or age-gate on video. Do not use the official X API.

## Agents must not

- Ask the user to “connect Instagram” in Cursor / Claude / Codex
- Put cookies in the repo, chat, jsonl, Notion, or vault
- Crawl Chrome or the cookie jar to list Saved collections (use the official Accounts Center ZIP — see `AGENTS.md`)
- Re-export on a cloud agent and hope the operator’s session appears

Re-export when yt-dlp 403s or media comes back empty. Sessions expire.
