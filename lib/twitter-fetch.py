#!/usr/bin/env python3
"""Fetch a public X/Twitter status via FixTweet and save text + photos.

Usage: twitter-fetch.py TWEET_URL_OR_ID OUTPUT_DIR
Writes: tweet.json, thread.txt, photos/photo_NN.ext
Prints: id\\thandle\\tphoto_count\\thas_video
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

API = "https://api.fxtwitter.com/status/{id}"
ID_RE = re.compile(r"(?:status|statuses)/(\d+)")


def status_id(arg: str) -> str:
    m = ID_RE.search(arg)
    if m:
        return m.group(1)
    if arg.isdigit():
        return arg
    raise SystemExit(f"Could not parse tweet id from: {arg}")


def fetch(tid: str) -> dict:
    req = urllib.request.Request(
        API.format(id=tid),
        headers={"User-Agent": "ig-yt-x-knowledge-extract/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 200 or "tweet" not in data:
        raise SystemExit(f"FixTweet error for {tid}: {data}")
    return data["tweet"]


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "ig-yt-x-knowledge-extract/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())


def ext_from_url(url: str) -> str:
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"


def walk_thread(start: dict) -> list[dict]:
    tweets = [start]
    parent = start.get("replying_to_status")
    seen = {start.get("id")}
    while parent and parent not in seen:
        seen.add(parent)
        try:
            t = fetch(parent)
        except Exception:
            break
        tweets.append(t)
        parent = t.get("replying_to_status")
    tweets.reverse()
    return tweets


def media_photos(tweet: dict) -> list[str]:
    media = tweet.get("media") or {}
    urls: list[str] = []
    for p in media.get("photos") or []:
        u = p.get("url") if isinstance(p, dict) else None
        if u:
            urls.append(u)
    for item in media.get("all") or []:
        if isinstance(item, dict) and item.get("type") == "photo" and item.get("url"):
            if item["url"] not in urls:
                urls.append(item["url"])
    return urls


def has_video(tweet: dict) -> bool:
    media = tweet.get("media") or {}
    if media.get("videos"):
        return True
    for item in media.get("all") or []:
        if isinstance(item, dict) and item.get("type") in {"video", "gif"}:
            return True
    return bool(tweet.get("video"))


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: twitter-fetch.py TWEET_URL_OR_ID OUTPUT_DIR", file=sys.stderr)
        sys.exit(1)
    tid = status_id(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    photos_dir = out / "photos"
    photos_dir.mkdir(exist_ok=True)

    tweet = fetch(tid)
    thread = walk_thread(tweet)
    (out / "tweet.json").write_text(json.dumps(tweet, indent=2) + "\n", encoding="utf-8")
    (out / "thread.json").write_text(json.dumps(thread, indent=2) + "\n", encoding="utf-8")

    lines: list[str] = []
    photo_n = 0
    video = False
    for t in thread:
        handle = (t.get("author") or {}).get("screen_name") or "?"
        text = (t.get("text") or "").strip()
        lines.append(f"@{handle} ({t.get('id')}):\n{text}\n")
        if t.get("quote"):
            q = t["quote"]
            qh = (q.get("author") or {}).get("screen_name") or "?"
            lines.append(f"  QT @{qh}: {(q.get('text') or '').strip()}\n")
        video = video or has_video(t)
        for url in media_photos(t):
            photo_n += 1
            dest = photos_dir / f"photo_{photo_n:02d}{ext_from_url(url)}"
            try:
                download(url, dest)
            except Exception as e:
                print(f"WARNING: photo download failed: {e}", file=sys.stderr)

    (out / "thread.txt").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    handle = (tweet.get("author") or {}).get("screen_name") or "unknown"
    print(f"{tid}\t{handle}\t{photo_n}\t{int(video)}")


if __name__ == "__main__":
    main()
