"""
wp_backfill.py

ONE-SHOT manual script. Pulls 2 months of Armstrong post history via
their WordPress REST API. Saves raw posts to disk for downstream
processing by the Claude classification + synthesis scripts.

This is NOT automated. Run once, inspect output, then proceed to
claude_classify.py.

Usage:
    python wp_backfill.py

Reads: nothing
Writes: backend/output/armstrong_raw_archive.json

The raw archive is a separate file from events_public.json. Reasons:
  - Doesn't disturb the live feed during backfill
  - Lets us iterate on classification/synthesis without re-fetching
  - Acts as a snapshot we can re-process if prompts change

Politeness:
  - 1-second delay between page requests
  - Explicit User-Agent identifying the project
  - Hard fail on first HTTP error (no retries) - if Armstrong returns
    an error, we want to know immediately rather than hammer their
    server with retries.

Exit codes:
    0 - success
    1 - network/HTTP error
    2 - no posts found in window (unexpected)
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "armstrong_raw_archive.json"

WP_API_BASE = "https://www.armstrongeconomics.com/wp-json/wp/v2/posts"

# Pull this many days of history. 2 months = 60 days.
BACKFILL_DAYS = 60

POSTS_PER_PAGE = 100  # WP REST API max
REQUEST_TIMEOUT_SECS = 30
INTER_REQUEST_DELAY_SECS = 1.0

USER_AGENT = (
    "ecmforecastpub-backfill/1.0 (+https://github.com/"
    "kiriakoschristodoulou-netizen/ecmforecastpub)"
)


def main() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
    print(
        f"[wp_backfill] Fetching Armstrong posts published after "
        f"{cutoff_iso} ({BACKFILL_DAYS} days back)..."
    )

    all_posts: list[dict] = []
    page = 1

    while True:
        params = {
            "per_page": POSTS_PER_PAGE,
            "page": page,
            "after": cutoff_iso,
            "orderby": "date",
            "order": "desc",
        }

        print(f"[wp_backfill] Requesting page {page}...")
        try:
            response = requests.get(
                WP_API_BASE,
                params=params,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
                timeout=REQUEST_TIMEOUT_SECS,
            )
        except requests.RequestException as e:
            print(
                f"[wp_backfill] ERROR: network error on page {page}: {e}",
                file=sys.stderr,
            )
            return 1

        # WP REST returns 400 when page is beyond the last one with
        # results. That's our normal end-of-pagination signal.
        if response.status_code == 400 and page > 1:
            print(
                f"[wp_backfill] Page {page} returned 400 (past last "
                f"page); pagination complete."
            )
            break

        if response.status_code != 200:
            print(
                f"[wp_backfill] ERROR: page {page} returned HTTP "
                f"{response.status_code}. Body: {response.text[:300]}",
                file=sys.stderr,
            )
            return 1

        try:
            page_posts = response.json()
        except ValueError as e:
            print(
                f"[wp_backfill] ERROR: page {page} returned invalid "
                f"JSON: {e}",
                file=sys.stderr,
            )
            return 1

        if not isinstance(page_posts, list):
            print(
                f"[wp_backfill] ERROR: page {page} response is not a "
                f"list (got {type(page_posts).__name__}).",
                file=sys.stderr,
            )
            return 1

        if not page_posts:
            print(f"[wp_backfill] Page {page} empty; pagination complete.")
            break

        # Normalize each post into the minimal shape we'll feed to
        # downstream classification. Keep just what we need; WP returns
        # tons of fields we don't care about (acf, jetpack_*, _links etc).
        for raw in page_posts:
            try:
                normalized = _normalize_post(raw)
            except (KeyError, TypeError) as e:
                print(
                    f"[wp_backfill] WARN: skipping malformed post: {e}",
                    file=sys.stderr,
                )
                continue
            all_posts.append(normalized)

        print(
            f"[wp_backfill] Page {page}: got {len(page_posts)} posts "
            f"(running total: {len(all_posts)})."
        )

        # Check WP's pagination headers. X-WP-TotalPages tells us when
        # to stop without making the final 400-throwing request.
        total_pages_header = response.headers.get("X-WP-TotalPages")
        if total_pages_header:
            try:
                total_pages = int(total_pages_header)
                if page >= total_pages:
                    print(
                        f"[wp_backfill] Reached last page "
                        f"({page}/{total_pages})."
                    )
                    break
            except ValueError:
                pass  # if the header isn't parseable, fall through

        page += 1
        time.sleep(INTER_REQUEST_DELAY_SECS)

    print(f"[wp_backfill] Total posts fetched: {len(all_posts)}")

    if not all_posts:
        print(
            "[wp_backfill] ERROR: no posts in window. Did the API change?",
            file=sys.stderr,
        )
        return 2

    _write_archive(all_posts)
    print(f"[wp_backfill] Wrote {len(all_posts)} posts to {OUTPUT_PATH}")
    return 0


def _normalize_post(raw: dict) -> dict:
    """
    Extract the fields we care about from a WP REST post object.

    WP REST nests text fields under 'rendered' keys. We unwrap those
    here so downstream consumers don't need to know the WP shape.

    Raises KeyError or TypeError on malformed input - the caller skips
    such posts and moves on.
    """
    return {
        "wp_id": int(raw["id"]),
        "slug": str(raw.get("slug", "")),
        "title": _unwrap_rendered(raw.get("title")),
        "content_html": _unwrap_rendered(raw.get("content")),
        "excerpt_html": _unwrap_rendered(raw.get("excerpt")),
        "link": str(raw.get("link", "")),
        "date_published": str(raw.get("date_gmt", raw.get("date", ""))),
        "categories": list(raw.get("categories") or []),
        "tags": list(raw.get("tags") or []),
    }


def _unwrap_rendered(field) -> str:
    """WP REST text fields are {'rendered': '...', 'protected': bool}."""
    if isinstance(field, dict):
        return str(field.get("rendered", ""))
    if isinstance(field, str):
        return field
    return ""


def _write_archive(posts: list[dict]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "backfill_days": BACKFILL_DAYS,
        "source": "armstrong_wp_rest_api",
        "post_count": len(posts),
        "posts": posts,
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
