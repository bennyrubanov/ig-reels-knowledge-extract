# Agent instructions — ig-yt-x-knowledge-extract

Read this file first. Extraction steps: [docs/agent-workflow.md](docs/agent-workflow.md). Filing: [docs/obsidian-filing.md](docs/obsidian-filing.md). After a large queue: [docs/batch-briefing.md](docs/batch-briefing.md).

**If `AGENTS.local.md` exists, read it next.** That file is gitignored machine notes (inbox IDs, parked work, collection order). Cloud clones will not have it.

Obsidian is **knowledge-only** — summaries, analysis, wikilinks. All tooling stays in this repo.

## Triggers

- User pastes `instagram.com/reel/` or `instagram.com/p/` (carousel) or YouTube or `x.com` / `twitter.com` status URL
- “Transcribe this reel/video/post”
- Legitimacy / fact-check / chart review
- Investment case / thesis research
- Inbox paste: URL + the comment they wrote when they saved it — that comment is the analysis prompt (`user_question`). **First TL;DR bullet must be `Your question:` + the answer.**

Do not extract a paste-inbox pile until they say so on a machine that has cookies and the vault.

Scripts warn if `ollama ps` shows a loaded model. Whisper also uses RAM; confirm before a long run if something else is already using the GPU/RAM.

## Quick start

```bash
~/.config/ig-yt-x-knowledge-extract/transcribe-reel.sh "<REEL_URL>"
~/.config/ig-yt-x-knowledge-extract/transcribe-carousel.sh "<POST_URL>"
~/.config/ig-yt-x-knowledge-extract/transcribe-youtube.sh "<YOUTUBE_URL>"
~/.config/ig-yt-x-knowledge-extract/transcribe-twitter.sh "<TWEET_URL>"
~/.config/ig-yt-x-knowledge-extract/transcribe-batch.sh URL URL
~/.config/ig-yt-x-knowledge-extract/extract-status.sh --jsonl /tmp/extract.jsonl
```

Scoreboard is disk + vault. Do not count jsonl `fail` rows.

Optional Notion paste-inbox (IDs in `local.env`):

```bash
python3 scripts/notion-extract-inbox.py list
python3 scripts/notion-extract-inbox.py urls
```

Then `transcribe-batch` those URLs and `mark --status noted` (or `skip` / `fail`). Skip comment-keyword CTAs (Comment “Sued”, KITCHEN, …) — mark `skip`, do not extract.

## Paths

| Item | Path |
|------|------|
| Repo | your clone |
| Config symlink | `~/.config/ig-yt-x-knowledge-extract` → repo (legacy `ig-reels-knowledge-extract` and `ig-reel` still resolve) |
| Cookies | `~/.config/ig-cookies.txt` (IG) · `~/.config/x-cookies.txt` (X, optional) |
| Vault | `OBSIDIAN_VAULT` or `local.env` (gitignored) |
| Raw downloads | `downloads/` under the config symlink |
| Saved ZIP | keep local; parse with `scripts/ig-saved-inventory.py` — do not commit the ZIP |

Copy `local.env.example` → `local.env`. Token for the Notion CLI: `NOTION_TOKEN` or `notion.env` (gitignored).

## After extraction → Obsidian

Write the **receipt** under `instagram/extractions/` (or `youtube/` / `twitter/`). Write the **human page** in a knowledge-center folder. Filing: [docs/obsidian-filing.md](docs/obsidian-filing.md).

Document as you go. A learning that is only in chat is not captured. Pipeline lessons go in [docs/agent-workflow.md](docs/agent-workflow.md). Personal parked work goes in `BACKLOG.local.md` if that file exists.

**YouTube captions:** creator-uploaded `en` beats automatic captions (`en-en`, `en-orig`). Whisper is a comparison pass only (`--force-whisper`).

**IG Saved collections:** no OAuth. Official Accounts Center export (Saved only) → parse URLs. Do not crawl collections with the cookie jar. Do not commit the ZIP. `noted` = id appears in a vault filename. Folder is a weak signal — file the keep on screen. Export captions often attach to the wrong post; trust downloaded media, Whisper, `{id}.ocr.txt`.

**Music / remix folders:** title + artist from frames or speech; else a lyrics hook + `track_id: unknown`. Add `vibe:` tags. There is no Shazam in this pipeline.

Videos **>120s** skip frames by default; `reextract-frames.sh` or `ffmpeg -ss` if needed.

## Instagram comments (fact-check)

When asked for a comment to post on a reel:

- Use the **reel’s words**. Do not upgrade into lab voice.
- Deliver as **plain numbered text**. Instagram strips markdown lists.
- **No hyphens** except one they put in the opener. No em dashes.
- Each item is **what is true + what to do**.
- Do **not** comment the CTA keyword.
- First person, short sentences.

## Missed frames?

```bash
~/.config/ig-yt-x-knowledge-extract/reextract-frames.sh {id} --frame-interval 1
```

## After a batch

Do **not** paste every title into chat. Patterns first, then hubs. Runbook: [docs/batch-briefing.md](docs/batch-briefing.md). In Cursor chat, link `https://www.instagram.com/reel/{id}/` — not `obsidian://`.
