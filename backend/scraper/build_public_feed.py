"""
build_public_feed.py

Orchestrator for the public-build data pipeline. Wires the Armstrong
RSS scraper to a JSON output file with CUMULATIVE ARCHIVING - new
posts are merged into the existing feed by stable GUID rather than
overwriting, so we never lose a post we've already captured.

Future sub-sessions will add Claude synthesis, importance rules,
convergence detection, and Apify-sourced related events.

Usage:
    python build_public_feed.py

Reads:
    backend/output/events_public.json (if exists, used as archive)

Writes:
    backend/output/events_public.json (replaced with merged result)

Exit codes:
    0 - success
    1 - scraper failure (fetch or parse error)
    2 - no new posts captured AND no archive exists (cold start with
        empty feed; non-zero so the Action notifies on it)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import ftfy

from armstrong_scraper import (
    ArmstrongFetchError,
    ArmstrongPost,
    fetch_armstrong_rss,
    filter_forecast_candidates,
)

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "events_public.json"

SCHEMA_VERSION = "1.0"
FEED_TYPE = "public"

# Post titles starting with these prefixes (case-insensitive) are
# excluded regardless of date keywords. These are recurring commentary
# series, not forecasts pointing at future events.
TITLE_EXCLUDE_PREFIXES = (
    "market talk",
    "ask socrates",
    "video update",
    "private blog",  # private-blog teasers in the public RSS
)


def main() -> int:
    print(f"[build_public_feed] Fetching Armstrong RSS...")
    try:
        raw_posts = fetch_armstrong_rss()
    except ArmstrongFetchError as e:
        print(f"[build_public_feed] ERROR: {e}", file=sys.stderr)
        return 1

    print(f"[build_public_feed] Fetched {len(raw_posts)} raw posts.")

    # First pass: date-keyword filter (loose).
    date_filtered = filter_forecast_candidates(raw_posts)

    # Second pass: exclude recurring commentary series by title prefix.
    candidates = [p for p in date_filtered if not _is_excluded_title(p.title)]

    print(
        f"[build_public_feed] Kept {len(candidates)} candidates after "
        f"date+exclude filters (down from {len(date_filtered)} after "
        f"date filter alone)."
    )

    # Load existing archive (if any) and merge.
    existing_forecasts = _load_existing_archive()
    print(
        f"[build_public_feed] Loaded {len(existing_forecasts)} existing "
        f"forecasts from archive."
    )

    new_forecasts = [_post_to_forecast(p) for p in candidates]
    merged = _merge_by_id(existing_forecasts, new_forecasts)
    added = len(merged) - len(existing_forecasts)
    print(
        f"[build_public_feed] Merged: {added} new, "
        f"{len(merged) - added} preserved, "
        f"{len(merged)} total."
    )

    if not merged:
        print(
            "[build_public_feed] WARNING: no forecasts in archive and no "
            "new candidates. Writing empty feed and exiting with code 2.",
            file=sys.stderr,
        )
        _write_feed([])
        return 2

    # Sort by date descending so newest forecasts come first in the JSON.
    merged.sort(key=lambda f: f.get("date", ""), reverse=True)

    _write_feed(merged)
    print(
        f"[build_public_feed] Wrote {len(merged)} forecasts to "
        f"{OUTPUT_PATH}"
    )
    return 0


def _is_excluded_title(title: str) -> bool:
    t = title.lower().strip()
    return any(t.startswith(prefix) for prefix in TITLE_EXCLUDE_PREFIXES)


def _load_existing_archive() -> list[dict]:
    """
    Read the existing events_public.json if present. Returns the
    forecasts list, or [] if the file is missing/unreadable/invalid.
    """
    if not OUTPUT_PATH.exists():
        return []
    try:
        with OUTPUT_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(
            f"[build_public_feed] WARN: could not read existing archive "
            f"({e}); starting fresh.",
            file=sys.stderr,
        )
        return []

    forecasts = payload.get("forecasts")
    if not isinstance(forecasts, list):
        return []

    return [f for f in forecasts if isinstance(f, dict) and f.get("id")]


def _merge_by_id(
    existing: list[dict], incoming: list[dict]
) -> list[dict]:
    """
    Merge incoming forecasts into existing by id. Existing wins on
    conflict so future Claude enrichment is preserved.
    """
    by_id: dict[str, dict] = {f["id"]: f for f in existing}
    for f in incoming:
        if f["id"] not in by_id:
            by_id[f["id"]] = f
    return list(by_id.values())


def _post_to_forecast(post: ArmstrongPost) -> dict:
    """
    Map a raw Armstrong post to one Forecast object in our schema.

    All text fields run through _fix_text() which strips RSS
    truncation markers and applies ftfy to repair mojibake.
    """
    return {
        "id": _stable_id(post),
        "date": post.published_at or _now_iso(),
        "title": _fix_text(post.title),
        "subtitle": None,
        "category": "armstrong_ecm",
        "importance": "normal",
        "is_convergence": False,
        "importance_justification": None,
        "synthesis": (_fix_text(_strip_html(post.summary))[:600]
                      or "(synthesis pending)"),
        "source": {
            "name": "Armstrong Economics",
            "url": post.url,
        },
        "related_events": [],
    }


def _write_feed(forecasts: list[dict]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "feed_type": FEED_TYPE,
        "forecasts": forecasts,
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# --- helpers -----------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _stable_id(post: ArmstrongPost) -> str:
    # Run title through fix_text so the slug derives from clean text.
    cleaned = _fix_text(post.title or "")
    slug = _SLUG_RE.sub("-", cleaned.lower()).strip("-")
    slug = slug[:80] or "untitled"
    return f"armstrong-{slug}"


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

# RSS truncation markers - "[...]" "[…]" "[&hellip;]" and their mojibake
# variants. WordPress inserts these to indicate the summary is cut off.
# Match either ascii [...], unicode [...], the HTML entity, or the
# common mojibake form "[â€¦]" that survives bad UTF-8 decoding.
_TRUNCATION_RE = re.compile(
    r"\[\s*(?:\.\.\.|\u2026|&hellip;|&#8230;|â€¦)\s*\]",
    re.IGNORECASE,
)


def _fix_text(s: str) -> str:
    """
    Clean text for output. Order matters:
      1. Strip RSS truncation markers (before ftfy, because ftfy
         leaves them mid-broken)
      2. Apply ftfy to repair mojibake, decode HTML entities,
         normalize unicode
      3. Collapse whitespace
    """
    if not s:
        return ""
    no_trunc = _TRUNCATION_RE.sub("", s)
    cleaned = ftfy.fix_text(no_trunc)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def _strip_html(s: str) -> str:
    if not s:
        return ""
    return _HTML_TAG_RE.sub("", s)


if __name__ == "__main__":
    sys.exit(main())
