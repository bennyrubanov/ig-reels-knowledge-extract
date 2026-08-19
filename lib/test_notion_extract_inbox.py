#!/usr/bin/env python3
"""Unit tests for the Notion extract inbox helpers (no network)."""
from __future__ import annotations

import unittest

from notion_extract_inbox import (
    extract_urls,
    is_actionable_queued,
    looks_like_comment_keyword_cta,
    mark_properties,
    parse_env_file,
    queue_json_payload,
    queued_query_filter,
    row_from_page,
    url_property_name,
)


class ParseTests(unittest.TestCase):
    def test_env_file_skips_comments(self) -> None:
        parsed = parse_env_file("# hi\nNOTION_TOKEN=secret\nOTHER=1\n")
        self.assertEqual(parsed["NOTION_TOKEN"], "secret")
        self.assertEqual(parsed["OTHER"], "1")

    def test_url_property_prefers_type_url(self) -> None:
        self.assertEqual(
            url_property_name({"URL": {"type": "url"}, "Name": {"type": "title"}}),
            "URL",
        )


class CtaTests(unittest.TestCase):
    def test_sued_pack(self) -> None:
        title = (
            '@murphmaxxing on Instagram: "Comment “Sued” to get sent over my '
            "full guide on how to fix this issues with your app"
        )
        self.assertTrue(looks_like_comment_keyword_cta(title))

    def test_plain_reel_title_is_not_cta(self) -> None:
        self.assertFalse(looks_like_comment_keyword_cta("Paywall last — 75% install"))
        self.assertFalse(looks_like_comment_keyword_cta(""))


class QueuedTests(unittest.TestCase):
    def test_empty_status_with_url_is_queued(self) -> None:
        self.assertTrue(is_actionable_queued("", "https://www.instagram.com/reel/Abc/"))
        self.assertTrue(is_actionable_queued("queued", "https://www.instagram.com/reel/Abc/"))
        self.assertFalse(is_actionable_queued("noted", "https://www.instagram.com/reel/Abc/"))
        self.assertFalse(is_actionable_queued("queued", ""))

    def test_filter_shape(self) -> None:
        filt = queued_query_filter("URL")
        self.assertEqual(filt["or"][0]["property"], "Status")


class RowTests(unittest.TestCase):
    def test_row_from_page(self) -> None:
        page = {
            "id": "3c03c77f93de81c0bc1fc127906616ee",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": 'Comment “Sued” to get the guide'}],
                },
                "URL": {
                    "type": "url",
                    "url": "https://www.instagram.com/reel/Db9Br3XBTPj/",
                },
                "Status": {"type": "select", "select": {"name": "queued"}},
                "Question": {"type": "rich_text", "rich_text": []},
                "Media ID": {
                    "type": "rich_text",
                    "rich_text": [{"plain_text": "Db9Br3XBTPj"}],
                },
                "Topics": {"type": "multi_select", "multi_select": []},
            },
        }
        row = row_from_page(page)
        self.assertEqual(row["media_id"], "Db9Br3XBTPj")
        self.assertEqual(row["page_id"], "3c03c77f-93de-81c0-bc1f-c127906616ee")
        self.assertTrue(row["skip_cta"])
        self.assertFalse(row["actionable"])

    def test_urls_omit_cta_by_default(self) -> None:
        rows = [
            {
                "url": "https://www.instagram.com/reel/KeepMe/",
                "status": "queued",
                "skip_cta": False,
                "question": "why this?",
                "page_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "media_id": "KeepMe",
                "kind": "reel",
            },
            {
                "url": "https://www.instagram.com/reel/Db9Br3XBTPj/",
                "status": "queued",
                "skip_cta": True,
                "question": "",
                "page_id": "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee",
                "media_id": "Db9Br3XBTPj",
                "kind": "reel",
            },
        ]
        self.assertEqual(
            extract_urls(rows, include_skip_cta=False),
            ["https://www.instagram.com/reel/KeepMe/"],
        )
        payload = queue_json_payload(rows, include_skip_cta=False)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["user_question"], "why this?")
        self.assertEqual(payload["items"][0]["capture_context"], "Notion")


class MarkTests(unittest.TestCase):
    def test_mark_properties(self) -> None:
        props = mark_properties(
            status="noted",
            media_id="Db9Br3XBTPj",
            vault_path="instagram/extractions/Db9Br3XBTPj-sued.md",
            topics=["building-an-app"],
        )
        self.assertEqual(props["Status"]["select"]["name"], "noted")
        self.assertEqual(props["Topics"]["multi_select"][0]["name"], "building-an-app")

    def test_bad_status(self) -> None:
        with self.assertRaises(ValueError):
            mark_properties(status="done")


if __name__ == "__main__":
    unittest.main()
