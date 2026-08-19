#!/usr/bin/env python3
"""Parse an Instagram Accounts Center Saved-only ZIP into a lightweight inventory.

Does not commit the ZIP. Re-run on the next dump; compare `id` to the vault
to see what is already noted (`--keep-noted` style: id anywhere in a filename).

  python3 scripts/ig-saved-inventory.py \\
    --zip ~/path/to/instagram-saved.zip \\
    --out exports/YYYY-MM-DD-ig-saved
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from local_config import default_vault, wanted_collections  # noqa: E402

IG_URL = re.compile(
    r"https?://(?:www\.)?instagram\.com/(reel|p|tv)/([A-Za-z0-9_-]+)/?"
)


def collection_name(item: dict) -> str:
    for lv in item.get("label_values") or []:
        if isinstance(lv, dict) and lv.get("label") == "Name":
            return (lv.get("value") or "?").strip()
    return "?"


def walk(obj, fn) -> None:
    if isinstance(obj, dict):
        fn(obj)
        for v in obj.values():
            walk(v, fn)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, fn)


def ig_hits(obj) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []

    def visit(d: dict) -> None:
        if d.get("label") != "URL":
            return
        u = d.get("href") or d.get("value") or ""
        m = IG_URL.search(u)
        if m:
            kind, sid = m.group(1), m.group(2)
            found.append((kind, sid, f"https://www.instagram.com/{kind}/{sid}/"))

    walk(obj, visit)
    return found


def owner_username(obj) -> str | None:
    found: list[str] = []

    def visit(d: dict) -> None:
        if d.get("label") == "Username" and d.get("value"):
            found.append(d["value"])

    walk(obj, visit)
    return found[0] if found else None


def caption_excerpt(obj, n: int = 180) -> str:
    found: list[str] = []

    def visit(d: dict) -> None:
        if d.get("label") == "Caption" and d.get("value"):
            found.append(d["value"])

    walk(obj, visit)
    if not found:
        return ""
    text = found[0].replace("\n", " ").strip()
    return text[:n]


def vault_noted_ids(vault: Path) -> set[str]:
    """Any `{id}` that appears in a vault markdown filename."""
    noted: set[str] = set()
    if not vault.exists():
        return noted
    for p in vault.rglob("*.md"):
        if "Notion" in p.parts:
            continue
        noted.add(p.name)
    return noted


def is_noted(sid: str, name_blobs: set[str]) -> bool:
    return any(sid in name for name in name_blobs)


def parse_zip(zpath: Path) -> tuple[list[dict], dict[str, list[dict]]]:
    with zipfile.ZipFile(zpath) as z:
        cols = json.loads(z.read("your_instagram_activity/saved/saved_collections.json"))
        posts = json.loads(z.read("your_instagram_activity/saved/saved_posts.json"))

    by_id: dict[str, dict] = {}
    id_to_collections: dict[str, set[str]] = defaultdict(set)

    for c in cols:
        name = collection_name(c)
        for kind, sid, url in ig_hits(c):
            id_to_collections[sid].add(name)
            by_id.setdefault(
                sid,
                {
                    "id": sid,
                    "kind": kind,
                    "url": url,
                    "owner": None,
                    "caption": "",
                },
            )
            row = by_id[sid]
            if not row.get("owner"):
                row["owner"] = owner_username(c)
            if not row.get("caption"):
                row["caption"] = caption_excerpt(c)

    # Flat all-posts list fills gaps (saves not in a named collection)
    for p in posts:
        for kind, sid, url in ig_hits(p):
            row = by_id.setdefault(
                sid,
                {
                    "id": sid,
                    "kind": kind,
                    "url": url,
                    "owner": owner_username(p),
                    "caption": caption_excerpt(p),
                },
            )
            if not row.get("owner"):
                row["owner"] = owner_username(p)
            if not row.get("caption"):
                row["caption"] = caption_excerpt(p)

    for sid, names in id_to_collections.items():
        by_id[sid]["collections"] = sorted(names)

    for row in by_id.values():
        row.setdefault("collections", [])

    collection_index: dict[str, list[dict]] = defaultdict(list)
    for sid, names in id_to_collections.items():
        for name in names:
            collection_index[name].append(by_id[sid])

    return list(by_id.values()), dict(collection_index)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--vault", type=Path, default=default_vault())
    args = ap.parse_args()

    rows, by_col = parse_zip(args.zip)
    name_blobs = vault_noted_ids(args.vault)
    for row in rows:
        row["noted"] = is_noted(row["id"], name_blobs)

    args.out.mkdir(parents=True, exist_ok=True)
    inv = args.out / "inventory.jsonl"
    with inv.open("w", encoding="utf-8") as f:
        for row in sorted(rows, key=lambda r: r["id"]):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    wanted = wanted_collections() or sorted(by_col.keys())
    audit = []
    for name in wanted:
        items = by_col.get(name, [])
        noted_n = sum(1 for r in items if r["noted"])
        audit.append(
            {
                "collection": name,
                "unique_ig": len(items),
                "noted": noted_n,
                "pending": len(items) - noted_n,
            }
        )

    (args.out / "audit.json").write_text(
        json.dumps(
            {
                "source_zip": str(args.zip),
                "vault": str(args.vault),
                "unique_ig_in_dump": len(rows),
                "wanted": audit,
                "all_collections": sorted(
                    {n: len(v) for n, v in by_col.items()}.items()
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # Per-collection URL lists for extract queues
    qdir = args.out / "queues"
    qdir.mkdir(exist_ok=True)
    for name in wanted:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        pending = [r for r in by_col.get(name, []) if not r["noted"]]
        already = [r for r in by_col.get(name, []) if r["noted"]]
        (qdir / f"{slug}.pending.txt").write_text(
            "\n".join(r["url"] for r in pending) + ("\n" if pending else ""),
            encoding="utf-8",
        )
        (qdir / f"{slug}.already-noted.txt").write_text(
            "\n".join(f"{r['id']}\t{r['url']}" for r in already) + ("\n" if already else ""),
            encoding="utf-8",
        )

    print(f"wrote {inv} ({len(rows)} unique IG ids)")
    print(f"wrote {args.out / 'audit.json'}")
    for a in audit:
        print(
            f"  {a['collection']}: {a['unique_ig']} unique, "
            f"{a['noted']} noted, {a['pending']} pending"
        )


if __name__ == "__main__":
    main()
