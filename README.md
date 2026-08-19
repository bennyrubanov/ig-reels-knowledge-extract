# ig-yt-x-knowledge-extract

Download Instagram, YouTube, or X media, pull captions and frames, transcribe with Whisper, and file notes in Obsidian. Built for agent-assisted review (charts, on-screen text, spoken claims).

No paid APIs. Cookies stay on your machine. Scripts warn if `ollama ps` shows a loaded model (Whisper also needs RAM).

## Setup

```bash
git clone git@github.com:bennyrubanov/ig-yt-x-knowledge-extract.git
cd ig-yt-x-knowledge-extract
ln -sfn "$(pwd)" ~/.config/ig-yt-x-knowledge-extract
# Older names still work if those symlinks exist:
#   ~/.config/ig-reels-knowledge-extract  ~/.config/ig-reel
python3 -m venv whisper-venv
./whisper-venv/bin/pip install openai-whisper faster-whisper
cp local.env.example local.env   # set OBSIDIAN_VAULT
```

Dependencies: `yt-dlp`, `ffmpeg`, `ffprobe`, optional `tesseract` for on-screen OCR.

**Instagram cookies:** there is no Instagram OAuth or app login. `transcribe-reel.sh` reads a Netscape cookie jar at `~/.config/ig-cookies.txt` (`chmod 600`). Export it from a browser that is already logged into instagram.com, and include the HttpOnly `sessionid`. yt-dlp can also pull cookies from Chrome in an attended run (`--cookies-from-browser`); the scripts do not do that by default. Never commit, log, or paste the file. X login wall: `~/.config/x-cookies.txt`.

## Usage

```bash
~/.config/ig-yt-x-knowledge-extract/transcribe-reel.sh 'https://www.instagram.com/reel/…'
~/.config/ig-yt-x-knowledge-extract/transcribe-carousel.sh 'https://www.instagram.com/p/…'
~/.config/ig-yt-x-knowledge-extract/transcribe-youtube.sh 'https://www.youtube.com/watch?v=…'
~/.config/ig-yt-x-knowledge-extract/transcribe-twitter.sh 'https://x.com/user/status/…'
~/.config/ig-yt-x-knowledge-extract/transcribe-batch.sh URL1 URL2   # MAX_JOBS=2; --jsonl FILE
~/.config/ig-yt-x-knowledge-extract/extract-status.sh --jsonl FILE
```

`extract-status.sh` is the scoreboard (disk + vault). Do not count jsonl `fail` rows.

`transcribe-*.sh` already runs `ollama ps` and warns if a model is loaded. Harmless when Ollama is absent or idle.

## What you get per item

Under `downloads/` (gitignored): video, audio, Whisper `{id}.txt`, caption `{id}.description.txt`, OCR `{id}.ocr.txt`, frames or carousel slides. Videos longer than 120s skip frames; re-run `reextract-frames.sh {id}` if you need them.

Then write a receipt in your vault (`instagram/extractions/{id}-{slug}.md`) and a human page in a knowledge-center folder. See [docs/obsidian-filing.md](docs/obsidian-filing.md).

## Saved collections and inboxes

Instagram Saved: official Accounts Center export (Saved only, JSON ZIP). Keep the ZIP local. Parse it with:

```bash
python3 scripts/ig-saved-inventory.py \
  --zip ~/path/to/instagram-saved.zip \
  --out exports/YYYY-MM-DD-ig-saved
```

`exports/` is gitignored. Optional `wanted-collections.txt` limits which folders get queue files.

Optional Notion paste-inbox: set `NOTION_DATABASE_ID` / `NOTION_DATA_SOURCE_ID` in `local.env` and `NOTION_TOKEN` (or `notion.env`). `scripts/notion-extract-inbox.py` lists and marks rows. It does not download or transcribe.

## Docs

| File | For |
|------|-----|
| [AGENTS.md](AGENTS.md) | Agent entry point |
| [docs/agent-workflow.md](docs/agent-workflow.md) | Extraction steps, failures, cookies |
| [docs/obsidian-filing.md](docs/obsidian-filing.md) | Where notes go |
| [docs/batch-briefing.md](docs/batch-briefing.md) | After a large queue |
| [docs/storage-retention.md](docs/storage-retention.md) | Prune downloads |
| [docs/BACKLOG.md](docs/BACKLOG.md) | How to park work (local list is `BACKLOG.local.md`) |

Machine-only overrides: `AGENTS.local.md`, `local.env`, `wanted-collections.txt` — all gitignored.

## License

Use and adapt. You are responsible for Instagram/YouTube/X terms and for anything in your cookie jar or vault.
