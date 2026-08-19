#!/usr/bin/env python3
"""Poll or mark the Notion Instagram Extractions inbox.

Does not download, Whisper, or write the vault. After you have a pile:

  python3 scripts/notion-extract-inbox.py urls
  python scripts/igx.py batch $(python3 scripts/notion-extract-inbox.py urls)
  # file notes, then:
  python3 scripts/notion-extract-inbox.py mark --media-id SHORTCODE --status noted \\
      --vault-path instagram/extractions/SHORTCODE-slug.md

The analysis prompt is usually the Name text before `on Instagram:`, not the
Question column. See docs/paste-inbox.md.

Comment-keyword CTAs (Comment “Sued”) are listed as skip-cta and omitted from
`urls` unless you pass --include-skip-cta. Mark those skip — do not extract.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT / "lib"))

from notion_extract_inbox import (  # noqa: E402
    DEFAULT_DATA_SOURCE_ID,
    DEFAULT_DATABASE_ID,
    INBOX_STATUSES,
    NotionInbox,
    extract_urls,
    format_list,
    load_notion_token,
    media_id_from_url,
    queue_json_payload,
)


def _inbox(args: argparse.Namespace) -> NotionInbox:
    if not args.database:
        raise SystemExit(
            "Set NOTION_DATABASE_ID in local.env or pass --database. "
            "See local.env.example."
        )
    return NotionInbox(
        token=load_notion_token(),
        data_source_id=args.data_source,
        database_id=args.database,
    )


def cmd_list(args: argparse.Namespace) -> int:
    rows = _inbox(args).query_queued()
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(format_list(rows))
    return 0


def cmd_urls(args: argparse.Namespace) -> int:
    rows = _inbox(args).query_queued()
    for url in extract_urls(rows, include_skip_cta=args.include_skip_cta):
        print(url)
    return 0


def cmd_queue_json(args: argparse.Namespace) -> int:
    rows = _inbox(args).query_queued()
    payload = queue_json_payload(rows, include_skip_cta=args.include_skip_cta)
    if args.out:
        args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(args.out)
    else:
        print(json.dumps(payload, indent=2))
    return 0


def cmd_mark(args: argparse.Namespace) -> int:
    inbox = _inbox(args)
    page_id = args.page
    media_id = args.media_id
    if not page_id:
        if not media_id:
            raise SystemExit("mark needs --page or --media-id")
        page_id = inbox.find_by_media_id(media_id)["page_id"]
    if not media_id and args.url:
        media_id = media_id_from_url(args.url)
    inbox.mark(
        page_id,
        status=args.status,
        media_id=media_id,
        vault_path=args.vault_path,
        question=args.question,
        topics=args.topic,
    )
    print(f"marked {page_id} status={args.status or '-'} media_id={media_id or '-'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-source", default=DEFAULT_DATA_SOURCE_ID)
    p.add_argument("--database", default=DEFAULT_DATABASE_ID)
    sub = p.add_subparsers(dest="cmd", required=True)

    list_p = sub.add_parser("list", help="Print queued rows (empty Status + URL counts)")
    list_p.add_argument("--json", action="store_true")
    list_p.set_defaults(func=cmd_list)

    urls_p = sub.add_parser("urls", help="One extract URL per line (skips comment-keyword CTAs)")
    urls_p.add_argument(
        "--include-skip-cta",
        action="store_true",
        help="Include Comment “Sued” / keyword packs (default: omit)",
    )
    urls_p.set_defaults(func=cmd_urls)

    qj = sub.add_parser("queue-json", help="Write extract-queue.py --queue JSON")
    qj.add_argument("--include-skip-cta", action="store_true")
    qj.add_argument("--out", type=Path)
    qj.set_defaults(func=cmd_queue_json)

    mark_p = sub.add_parser("mark", help="PATCH Status / Media ID / Vault path")
    mark_p.add_argument("--page", help="Notion page id")
    mark_p.add_argument("--media-id", help="Instagram/YouTube/X id (finds the queued row)")
    mark_p.add_argument("--url", help="Fill Media ID from this URL")
    mark_p.add_argument("--status", choices=sorted(INBOX_STATUSES))
    mark_p.add_argument("--vault-path", help="e.g. instagram/extractions/{id}-{slug}.md")
    mark_p.add_argument("--question")
    mark_p.add_argument("--topic", action="append", help="Topics multi-select (repeatable)")
    mark_p.set_defaults(func=cmd_mark)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
