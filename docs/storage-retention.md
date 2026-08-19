# Storage & retention policy

Canonical policy for raw downloads vs Obsidian knowledge. **Tooling docs live in this repo**, not the vault.

Cross-ref: [agent-workflow.md](agent-workflow.md) (extraction), [obsidian-filing.md](obsidian-filing.md) (note format & provenance).

---

## Storage math

Approximate footprint for **100 reels** (~90s each, before cleanup):

| Scope | Size |
|-------|------|
| Full cache @ 1s frames + mp4 + m4a | ~2.6 GB |
| Full cache @ 2s / auto frames + mp4 + m4a | ~2.0 GB |
| Transcripts + captions + OCR + logs (after cleanup) | ~15–20 MB |

Per-reel breakdown (~90s reel, measured Da3iJOOIEkw):

| Component | ~Size |
|-----------|-------|
| mp4 | ~12 MB |
| m4a | ~1.5 MB |
| frames @ 1s (~90 JPGs) | ~13 MB |
| frames @ 2s (~45 JPGs) | ~6.5 MB |
| transcript + description + whisper.log + ocr.txt | ~10–40 KB |

YouTube long-form audio dominates when Whisper runs (e.g. 51 min talk ≈ 70 MB m4a); captions-first paths skip most media.

---

## Recommended 3-step policy

1. **Extract densely** — default **1s** frames; use `auto` or `--frame-interval 2` only for clearly static reels. When unsure, bias more frames — prune raw media later.
2. **Write Obsidian note** — claims, frame/chart descriptions, analysis. This is the **durable artifact**; raw media is disposable once the note exists.
3. **Prune raw media monthly** — preview first, then run cleanup with `--keep-noted`.

Agents should complete steps 1–2 before cleanup. Never prune media for a reel you haven't noted yet if you might need frames for chart review.

---

## Cleanup commands

Config root: `~/.config/ig-yt-x-knowledge-extract` (optional symlink; Windows uses the clone). Legacy `ig-reels-knowledge-extract` / `ig-reel` still resolve.

**Preview** (always run first):

```bash
python scripts/igx.py cleanup --dry-run --days 30 --keep-noted
```

**Apply**:

```bash
python scripts/igx.py cleanup --days 30 --keep-noted
```

**Aggressive** (no Obsidian guard — deletes all eligible media):

```bash
python scripts/igx.py cleanup --days 30
```

Override paths if needed:

```bash
IG_REELS_ROOT=~/.config/ig-yt-x-knowledge-extract \
OBSIDIAN_VAULT="$HOME/Documents/Obsidian" \
  cleanup-downloads.sh --dry-run --days 30 --keep-noted
```

---

## What cleanup keeps vs deletes

| Action | Files |
|--------|-------|
| **Keep** (always) | `{id}.txt`, `{id}.description.txt`, `{id}.ocr.txt`, `{id}.whisper.log` |
| **Delete** (if older than `--days`) | `{id}.mp4`, `{id}.m4a`, thumbnails, `{id}/frames/`, `{id}/slides/`, YouTube intermediates |

Instagram reels: `downloads/{id}.*` and `downloads/{id}/frames/`.  
Instagram carousels: `downloads/{id}/slides/slide_NN.*` + `{id}.description.txt`.  
YouTube: `downloads/youtube/{id}.*`.

Re-extract frames anytime while `{id}.mp4` still exists:

```bash
python scripts/igx.py reextract {id} --frame-interval 1
```

---

## What `--keep-noted` does

When `--keep-noted` is set, the script **skips any reel/video ID** that has a matching `.md` **anywhere in the vault** (filename contains the ID). Covers `instagram/extractions/`, `youtube/`, `wealth/`, and knowledge-center folders (`health/`, `building-an-app/`, …).

Match is by filename containing the ID (e.g. `Da3iJOOIEkw-nickelninjatrades-gex-strategy.md` protects `Da3iJOOIEkw` downloads).

Use this so noted reels keep raw media available for re-analysis or denser frame re-extraction until you explicitly delete or run cleanup without `--keep-noted`.

---

## Source link retention (permanent)

**Source URLs outlive raw media.** When you consolidate or reorganize the knowledge base, provenance must survive.

### Per-source notes (`instagram/`, `youtube/`)

- **Always** include `source:` in YAML frontmatter with the original Instagram reel or YouTube URL.
- Never remove `source:` when editing or merging body content.
- Filename should include the platform ID (`{id}-{slug}.md`) so `--keep-noted` and human search both work.

### Synthesis notes (`wealth/`, cross-cutting)

- Wikilink back to each source note: `[[instagram/extractions/Da3iJOOIEkw-nickelninjatrades-gex-strategy]]`.
- Also list source URLs explicitly (inline or under a **Sources** heading) — wikilinks alone can break if notes are renamed.
- When merging multiple source notes into one synthesis note, **keep the source notes** (or archive with redirects); copy URLs into the synthesis note before deleting anything.

### Consolidation passes

Periodic KB cleanup should:

- Merge duplicate *knowledge* (claims, analysis, tables).
- **Preserve provenance** — every fact traceable to a `source:` URL or a wikilink + URL in a synthesis note.
- Never delete a source note without archiving its URL elsewhere.
- Prefer updating source notes in place over deleting them.

Raw mp4/frames may be pruned; **source links and text dumps are permanent** (`{id}.txt`, `{id}.description.txt`, `{id}.ocr.txt`).

Backfill OCR for already-downloaded frames/slides:

```bash
~/.config/ig-yt-x-knowledge-extract/ocr-backfill.sh          # skip ids that already have .ocr.txt
~/.config/ig-yt-x-knowledge-extract/ocr-backfill.sh --force  # redo
```

---

## Monthly checklist

1. Ensure recent extractions have Obsidian notes (claims + frame descriptions).
2. `cleanup-downloads.sh --dry-run --days 30 --keep-noted` — review output.
3. Run without `--dry-run` if preview looks correct.
4. Optional: spot-check that synthesis notes in `wealth/` still link to source notes and URLs.
