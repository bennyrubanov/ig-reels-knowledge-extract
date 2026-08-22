#!/usr/bin/env python3
"""Notion Instagram Extractions inbox — poll and mark, never extract.

A hosted poller may email when queued first hits a threshold. This module only
talks to Notion. Download, Whisper, and vault writes stay on the cookie machine.
See docs/paste-inbox.md.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from extract_status import classify_url, media_id_from_url
from local_config import config_root, load_local_env, notion_data_source_id, notion_database_id

DEFAULT_DATABASE_ID = notion_database_id()
DEFAULT_DATA_SOURCE_ID = notion_data_source_id()
NOTION_VERSION = "2025-09-03"
INBOX_STATUSES = frozenset({"queued", "extracting", "noted", "skip", "fail"})
TOKEN_PATHS = (
    config_root() / "notion.env",
    Path(__file__).resolve().parents[1] / "notion.env",
)

# Instagram share titles look like `{creator} on Instagram: "{caption}"`.
# The operator types the analysis prompt immediately before that.
_ON_INSTAGRAM = re.compile(
    r"^(?P<prefix>.*?)\s+on Instagram:\s*",
    re.IGNORECASE | re.DOTALL,
)
_PROMPT_START = re.compile(
    r"^(true|valid|necessary|should|why|how|what|is\b|any|anything|copy|"
    r"implement|new|worth|check|thoughts|legit|does|can|would|could|"
    r"please|look|review)\b",
    re.IGNORECASE,
)
_TRAILING_HANDLE = re.compile(r"\s+@[\w.]+$")
# `{Brand | subtitle}` at the end — not everything before the first `|`.
_TRAILING_PIPE_BRAND = re.compile(
    r"\s+[A-Z][^\s|]*(?:\s+[A-Z][^\s|]*){0,3}(?:\s*\|\s*[^|]+)+$"
)
_TRAILING_CREATOR_NAME = re.compile(
    r"""
    (?:
        \s+[A-Z][^\s|]*(?:\s+[A-Z][^\s|]*){0,2}
        |
        \s+[A-Z][a-zA-Z]*[A-Z][a-zA-Z]+
        |
        (?<=\?)\s+[a-z][\w.]{2,}(?:\s+[a-z][\w.]{2,})?
    )
    $
    """,
    re.VERBOSE,
)

# Comment “Sued” / Comment KITCHEN — flag only. Never omit from extract.
# 2026-08-21: “comment this word for the link” hid ScrapeGraph-AI and recipes.
_COMMENT_KEYWORD = re.compile(
    r"""
    comment\s+[“"'][^”"']+[”"']
    |comment\s+\w+\s+to\s+(?:get|receive|unlock|send|dm)
    |drop\s+(?:a\s+)?keyword
    |type\s+[A-Z]{3,}
    """,
    re.IGNORECASE | re.VERBOSE,
)
_NAMED_KEEP = re.compile(
    r"github\.com/|on github|dropped \S+ on github",
    re.IGNORECASE,
)


def looks_like_comment_keyword_cta(text: str) -> bool:
    if not text or not _COMMENT_KEYWORD.search(text):
        return False
    if _NAMED_KEEP.search(text):
        return False
    return True


def looks_like_creator_only(prefix: str) -> bool:
    """True when the Name prefix is only the Instagram creator, not a prompt."""
    s = (prefix or "").strip()
    if not s:
        return True
    if "?" in s:
        return False
    if _PROMPT_START.match(s):
        return False
    if s.startswith("@") and len(s.split()) <= 2:
        return True
    if "|" in s:
        return True
    return len(s.split()) <= 4


def strip_trailing_creator(prefix: str) -> str:
    """Drop `{creator}` from `{prompt} {creator}` so the prompt remains."""
    s = (prefix or "").strip()
    s = _TRAILING_HANDLE.sub("", s).strip()
    s = _TRAILING_PIPE_BRAND.sub("", s).strip()
    s = _TRAILING_CREATOR_NAME.sub("", s).strip()
    return s


def user_question_from_name(title: str, question_prop: str = "") -> str:
    """Question column wins; otherwise the text typed before the IG share title."""
    q = (question_prop or "").strip()
    if q:
        return q
    text = (title or "").strip()
    if not text:
        return ""
    match = _ON_INSTAGRAM.match(text)
    if match:
        prefix = (match.group("prefix") or "").strip()
    else:
        prefix = re.sub(r"\s+Instagram\s*$", "", text, flags=re.I).strip()
        if prefix.lower() in {"", "instagram"}:
            return ""
    if looks_like_creator_only(prefix):
        return ""
    return strip_trailing_creator(prefix)


def is_actionable_queued(status: str, url: str) -> bool:
    if not (url or "").strip():
        return False
    s = (status or "").strip().lower()
    return s in {"", "queued"}


def normalize_notion_id(value: str) -> str:
    hex32 = re.sub(r"[^0-9a-fA-F]", "", value)
    if len(hex32) != 32:
        return value
    h = hex32.lower()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def parse_env_file(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key:
            out[key] = val
    return out


def load_notion_token(env: dict[str, str] | None = None) -> str:
    env = env if env is not None else os.environ
    token = (env.get("NOTION_TOKEN") or "").strip()
    if token:
        return token
    for path in TOKEN_PATHS:
        if not path.is_file():
            continue
        parsed = parse_env_file(path.read_text(encoding="utf-8"))
        token = (parsed.get("NOTION_TOKEN") or "").strip()
        if token:
            return token
    raise SystemExit(
        "Set NOTION_TOKEN or write notion.env next to the repo "
        "(gitignored). Cursor agents can query the inbox via Notion MCP instead. "
        "Do not copy Railway .env into git."
    )


def url_property_name(schema: dict[str, Any]) -> str:
    for name, prop in schema.items():
        if isinstance(prop, dict) and prop.get("type") == "url":
            return name
    return "URL"


def plain_rich_text(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(str(part.get("plain_text") or "") for part in items if isinstance(part, dict))


def prop_plain(prop: Any) -> str:
    if not isinstance(prop, dict):
        return ""
    kind = prop.get("type")
    if kind == "url":
        return str(prop.get("url") or "")
    if kind == "select":
        sel = prop.get("select") or {}
        return str(sel.get("name") or "") if isinstance(sel, dict) else ""
    if kind in {"rich_text", "text"}:
        return plain_rich_text(prop.get("rich_text") or prop.get("text") or [])
    if kind == "title":
        return plain_rich_text(prop.get("title") or [])
    if kind == "multi_select":
        opts = prop.get("multi_select") or []
        names = [str(o.get("name") or "") for o in opts if isinstance(o, dict)]
        return ", ".join(n for n in names if n)
    return ""


def row_from_page(page: dict[str, Any], url_prop: str = "URL") -> dict[str, Any]:
    props = page.get("properties") or {}
    if not isinstance(props, dict):
        props = {}
    url = prop_plain(props.get(url_prop) or props.get("URL") or props.get("userDefined:URL"))
    title = ""
    for prop in props.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            title = prop_plain(prop)
            break
    status = prop_plain(props.get("Status"))
    question_prop = prop_plain(props.get("Question"))
    question = user_question_from_name(title, question_prop)
    media_id = prop_plain(props.get("Media ID")) or media_id_from_url(url)
    vault_path = prop_plain(props.get("Vault path"))
    topics_prop = props.get("Topics") or {}
    topics: list[str] = []
    if isinstance(topics_prop, dict):
        for opt in topics_prop.get("multi_select") or []:
            if isinstance(opt, dict) and opt.get("name"):
                topics.append(str(opt["name"]))
    skip_cta = looks_like_comment_keyword_cta(f"{title}\n{question}")
    return {
        "page_id": normalize_notion_id(str(page.get("id") or "")),
        "url": url,
        "title": title,
        "status": status,
        "question": question,
        "media_id": media_id,
        "vault_path": vault_path,
        "topics": topics,
        "skip_cta": skip_cta,
        "kind": classify_url(url) if url else "unknown",
        "actionable": is_actionable_queued(status, url),
    }


def mark_properties(
    *,
    status: str | None = None,
    media_id: str | None = None,
    vault_path: str | None = None,
    question: str | None = None,
    topics: list[str] | None = None,
) -> dict[str, Any]:
    props: dict[str, Any] = {}
    if status is not None:
        s = status.strip().lower()
        if s not in INBOX_STATUSES:
            raise ValueError(f"status must be one of {sorted(INBOX_STATUSES)}")
        props["Status"] = {"select": {"name": s}}
    if media_id is not None:
        props["Media ID"] = {"rich_text": [{"text": {"content": media_id[:2000]}}]}
    if vault_path is not None:
        props["Vault path"] = {"rich_text": [{"text": {"content": vault_path[:2000]}}]}
    if question is not None:
        props["Question"] = {"rich_text": [{"text": {"content": question[:2000]}}]}
    if topics is not None:
        props["Topics"] = {"multi_select": [{"name": t} for t in topics if t]}
    return props


def queued_query_filter(url_prop: str = "URL") -> dict[str, Any]:
    return {
        "or": [
            {"property": "Status", "select": {"equals": "queued"}},
            {
                "and": [
                    {"property": "Status", "select": {"is_empty": True}},
                    {"property": url_prop, "url": {"is_not_empty": True}},
                ]
            },
        ]
    }


class NotionInbox:
    def __init__(
        self,
        token: str,
        data_source_id: str = DEFAULT_DATA_SOURCE_ID,
        database_id: str = DEFAULT_DATABASE_ID,
    ) -> None:
        self.token = token
        self.data_source_id = normalize_notion_id(data_source_id)
        self.database_id = normalize_notion_id(database_id)
        self._url_prop: str | None = None

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        req = urllib.request.Request(
            f"https://api.notion.com/v1{path}",
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            raise SystemExit(f"Notion {exc.code} {method} {path}: {detail}") from exc

    def schema(self) -> dict[str, Any]:
        body = self._request("GET", f"/data_sources/{self.data_source_id}")
        props = body.get("properties") or {}
        return props if isinstance(props, dict) else {}

    def url_prop(self) -> str:
        if self._url_prop is None:
            self._url_prop = url_property_name(self.schema())
        return self._url_prop

    def query_queued(self) -> list[dict[str, Any]]:
        url_prop = self.url_prop()
        rows: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            payload: dict[str, Any] = {
                "filter": queued_query_filter(url_prop),
                "page_size": 100,
            }
            if cursor:
                payload["start_cursor"] = cursor
            body = self._request(
                "POST", f"/data_sources/{self.data_source_id}/query", payload
            )
            for page in body.get("results") or []:
                if isinstance(page, dict):
                    rows.append(row_from_page(page, url_prop))
            if not body.get("has_more"):
                break
            cursor = body.get("next_cursor")
            if not cursor:
                break
        return rows

    def mark(
        self,
        page_id: str,
        *,
        status: str | None = None,
        media_id: str | None = None,
        vault_path: str | None = None,
        question: str | None = None,
        topics: list[str] | None = None,
    ) -> dict[str, Any]:
        props = mark_properties(
            status=status,
            media_id=media_id,
            vault_path=vault_path,
            question=question,
            topics=topics,
        )
        if not props:
            raise SystemExit("mark needs --status, --media-id, --vault-path, --question, or --topic")
        return self._request(
            "PATCH",
            f"/pages/{normalize_notion_id(page_id)}",
            {"properties": props},
        )

    def find_by_media_id(self, media_id: str, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        want = media_id.strip()
        for row in rows if rows is not None else self.query_queued():
            if row.get("media_id") == want:
                return row
        raise SystemExit(f"no queued row with Media ID {want}")


def format_list(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "0 queued"
    inbox = load_local_env().get("NOTION_INBOX_URL", "").strip()
    header = f"{len(rows)} queued" + (f"  ({inbox})" if inbox else "")
    lines = [header]
    for row in rows:
        flag = "skip-cta" if row.get("skip_cta") else (row.get("status") or "queued")
        lines.append(
            f"{flag:10} {row.get('media_id') or '-':12} {row.get('url') or ''}  "
            f"page={row.get('page_id')}"
        )
        if row.get("question"):
            lines.append(f"           question: {row['question']}")
        if row.get("title") and row.get("skip_cta"):
            lines.append(f"           {row['title'][:120]}")
    return "\n".join(lines)


def extract_urls(rows: list[dict[str, Any]], *, include_skip_cta: bool) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        url = (row.get("url") or "").strip()
        if not url or url in seen:
            continue
        if not is_actionable_queued(str(row.get("status") or ""), url):
            continue
        seen.add(url)
        out.append(url)
    return out


def queue_json_payload(rows: list[dict[str, Any]], *, include_skip_cta: bool) -> dict[str, Any]:
    items = []
    for row in rows:
        url = (row.get("url") or "").strip()
        if not url:
            continue
        if not is_actionable_queued(str(row.get("status") or ""), url):
            continue
        items.append(
            {
                "action": "extract",
                "user_question": row.get("question") or None,
                "capture_context": "Notion",
                "notion_page_id": row.get("page_id"),
                "media": [
                    {
                        "kind": row.get("kind") or classify_url(url),
                        "media_id": row.get("media_id") or media_id_from_url(url),
                        "url": url,
                    }
                ],
            }
        )
    return {"source": "notion-extract-inbox", "items": items}
