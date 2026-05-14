"""
rss_to_archive.py

Orchestrator: pulls latest posts from Armstrong's public RSS feed,
fetches each one's full body via the WP REST API, applies ftfy to clean
mojibake, and appends new posts to armstrong_raw_archive.json.

Designed for non-interactive automated runs (GitHub Actions). Loud
failures: any unrecoverable error exits non-zero so the workflow
notifies the maintainer.

Strategy:
  1. Fetch RSS feed (latest ~10 posts, newest first).
  2. Load existing archive; build a set of known wp_ids.
  3. For each RSS post not yet in archive:
     - Extract wp_id from URL slug or feed.
     - GET https://www.armstrongeconomics.com/wp-json/wp/v2/posts/{id}
     - Parse title/content/date/link.
     - Apply ftfy + html.unescape to title + content_html.
     - Append to in-memory archive.
  4. If anything was appended, write the archive back to disk.

Polite to Armstrong's server: 1-second delay between WP REST fetches.

Usage:
    python rss_to_archive.py            # normal run
    python rss_to_archive.py --dry-run  # show what would be added
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ftfy
import requests
from dateutil import parser as date_parser

from armstrong_scraper import fetch_armstrong_rss, ArmstrongFetchError

SCRIPT_DIR = Path(__file__).resolve().parent
ARCHIVE_PATH = SCRIPT_DIR.parent / "output" / "armstrong_raw_archive.json"

WP_BASE = "https://www.armstrongeconomics.com/wp-json/wp/v2/posts"
USER_AGENT = (
    "ecmforecastpub/1.0 (+https://github.com/"
    "kiriakoschristodoulou-netizen/ecmforecastpub)"
)
FETCH_TIMEOUT_SECS = 20
INTER_FETCH_DELAY_SECS = 1.0

_WP_ID_FROM_URL_RE = re.compile(r"[?&]p=(\d+)")
_GUID_ID_RE = re.compile(r"\?p=(\d+)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be added; don't write.")
    args = parser.parse_args()

    # Load existing archive (or initialize if missing).
    if ARCHIVE_PATH.exists():
        with ARCHIVE_PATH.open("r", encoding="utf-8") as f:
            archive = json.load(f)
    else:
        archive = {
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "post_count": 0,
            "posts": [],
        }

    posts = archive.get("posts", [])
    known_ids = {int(p["wp_id"]) for p in posts if p.get("wp_id")}
    print(f"[rss_to_archive] Archive has {len(posts)} known posts.")

    # Fetch RSS.
    print("[rss_to_archive] Fetching RSS feed...")
    try:
        rss_posts = fetch_armstrong_rss()
    except ArmstrongFetchError as e:
        print(f"[rss_to_archive] ERROR: RSS fetch failed: {e}", file=sys.stderr)
        return 1

    print(f"[rss_to_archive] RSS returned {len(rss_posts)} items.")

    # Identify which RSS posts are new (by wp_id derived from URL).
    candidates: list[tuple[int, str]] = []  # (wp_id, url)
    skipped_no_id = 0
    skipped_known = 0
    for rp in rss_posts:
        wp_id = _extract_wp_id(rp.url, rp.guid)
        if wp_id is None:
            skipped_no_id += 1
            continue
        if wp_id in known_ids:
            skipped_known += 1
            continue
        candidates.append((wp_id, rp.url))

    print(
        f"[rss_to_archive] New candidates: {len(candidates)} "
        f"(skipped {skipped_known} known, {skipped_no_id} no wp_id)."
    )

    if not candidates:
        print("[rss_to_archive] Nothing new. Exiting cleanly.")
        return 0

    # Fetch full body for each new post via WP REST.
    new_posts: list[dict] = []
    for i, (wp_id, url) in enumerate(candidates, start=1):
        print(f"[rss_to_archive] Fetching wp_id={wp_id} ({i}/{len(candidates)})...")
        try:
            post = _fetch_wp_post(wp_id)
        except Exception as e:
            print(
                f"[rss_to_archive] WARN: failed to fetch wp_id={wp_id}: {e}. "
                f"Skipping; will retry on next run.",
                file=sys.stderr,
            )
            continue

        new_posts.append(post)

        if i < len(candidates):
            time.sleep(INTER_FETCH_DELAY_SECS)

    if not new_posts:
        print("[rss_to_archive] No new posts successfully fetched. Exiting cleanly.")
        return 0

    print(f"[rss_to_archive] Successfully fetched {len(new_posts)} new posts.")

    if args.dry_run:
        print("[rss_to_archive] --dry-run: would append these:")
        for p in new_posts:
            print(f"    wp_id={p['wp_id']}: {p['title'][:80]}")
        return 0

    # Append new posts to archive. Existing posts win (per cumulative-archive
    # policy in PROJECT_NOTES). We only got here because candidates were
    # NOT in known_ids, so no conflicts expected, but be defensive.
    final_posts = posts + new_posts
    archive["posts"] = final_posts
    archive["post_count"] = len(final_posts)
    archive["last_rss_run_at"] = datetime.now(timezone.utc).isoformat()

    ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ARCHIVE_PATH.open("w", encoding="utf-8") as f:
        json.dump(archive, f, indent=2, ensure_ascii=False)

    print(f"[rss_to_archive] Wrote {len(final_posts)} total posts to archive.")
    print(f"[rss_to_archive] Added {len(new_posts)} new posts.")
    return 0


def _extract_wp_id(url: str, guid: str) -> int | None:
    """
    Pull the numeric WP post id from either the post URL or the RSS guid.
    WordPress permalinks look like:
        https://www.armstrongeconomics.com/?p=386802
        https://www.armstrongeconomics.com/category/post-slug/?p=386802
    RSS guids often look like:
        https://www.armstrongeconomics.com/?p=386802
    """
    for source in (url, guid):
        if not source:
            continue
        m = _WP_ID_FROM_URL_RE.search(source) or _GUID_ID_RE.search(source)
        if m:
            try:
                return int(m.group(1))
            except (TypeError, ValueError):
                pass

    # Fallback: ask WP REST to resolve by URL (slug). Not implemented here
    # because all permalinks we've seen have ?p=NNNNN. If RSS changes
    # format, this is where to add the fallback.
    return None


def _fetch_wp_post(wp_id: int) -> dict:
    """Fetch one full post from the WP REST API, clean it, and return."""
    response = requests.get(
        f"{WP_BASE}/{wp_id}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=FETCH_TIMEOUT_SECS,
    )
    response.raise_for_status()
    data = response.json()

    raw_title = (data.get("title") or {}).get("rendered", "")
    raw_content = (data.get("content") or {}).get("rendered", "")
    raw_date = data.get("date") or ""
    link = data.get("link") or ""

    cleaned_title = _clean(raw_title)
    cleaned_content = _clean(raw_content)
    iso_date = _iso_or_empty(raw_date)

    return {
        "wp_id": wp_id,
        "title": cleaned_title,
        "content_html": cleaned_content,
        "date_published": iso_date,
        "link": link,
    }


def _clean(s: str) -> str:
    """Strip HTML entities + apply ftfy mojibake repair."""
    if not s:
        return ""
    s = html.unescape(s)
    s = ftfy.fix_text(s)
    return s


def _iso_or_empty(raw: str) -> str:
    if not raw:
        return ""
    try:
        return date_parser.parse(raw).isoformat()
    except (ValueError, TypeError):
        return ""


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[rss_to_archive] Interrupted.", file=sys.stderr)
        sys.exit(130)
