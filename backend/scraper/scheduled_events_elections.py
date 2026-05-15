"""
scheduled_events_elections.py

Pulls upcoming national and international elections from Wikipedia's
maintained electoral calendar pages via the MediaWiki API. Filters to
major nations (G7 + G20 + EU heavyweights + geopolitically charged
nations) so the related_events attachment doesn't bury cards in noise.

Sources (no auth, no rate limits for reasonable use):
  - YYYY_national_electoral_calendar (current year + 1 ahead)
  - YYYY_international_electoral_calendar (current year + 1 ahead)

Wikipedia uses three entry patterns in these calendar pages:

  A. Top-level dated bullet:
     * 12 February: [[Elections in Bangladesh|Bangladesh]], [[parliament]]

  B. Sub-bullet inheriting date from parent:
     * 12 April:
     ** [[Elections in Hungary|Hungary]], [[parliament]]
     ** [[Elections in Peru|Peru]], [[president]]

  C. Date-range top-level bullet:
     * 22-23 March: [[Elections in Italy|Italy]], [[referendum]]

Citation blocks (<ref>...</ref>) are commonly opened on one line and
closed several lines later. Single-line regex stripping can't catch
multi-line refs, so this parser truncates each line at the FIRST `<ref`
occurrence — refs always come last in calendar entries on Wikipedia.

Output: scheduled_events_elections.json, cumulative-append, deduped
by (date, title).

Usage:
    python scheduled_events_elections.py            # fetch and merge
    python scheduled_events_elections.py --dry-run  # show what would change
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import ftfy
import requests
from dateutil import parser as date_parser

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "scheduled_events_elections.json"

_CURRENT_YEAR = datetime.now().year
WIKI_PAGES = [
    f"{_CURRENT_YEAR}_national_electoral_calendar",
    f"{_CURRENT_YEAR + 1}_national_electoral_calendar",
    f"{_CURRENT_YEAR}_international_electoral_calendar",
    f"{_CURRENT_YEAR + 1}_international_electoral_calendar",
]

MEDIAWIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = (
    "ecmforecastpub/1.0 (+https://github.com/"
    "kiriakoschristodoulou-netizen/ecmforecastpub)"
)
FETCH_TIMEOUT_SECS = 20

# Major nations whose elections meaningfully affect global markets,
# geopolitics, or ECM-relevant cycles. Case-insensitive substring match.
MAJOR_NATIONS: tuple[str, ...] = (
    # G7
    "United States", "USA", "U.S.",
    "United Kingdom", "Britain", "UK",
    "France", "Germany", "Italy", "Japan", "Canada",
    # G20 additions
    "China", "Russia", "India", "Brazil", "Mexico",
    "South Korea", "Indonesia", "Australia",
    "Saudi Arabia", "South Africa", "Argentina", "Turkey",
    # EU heavyweights
    "Spain", "Netherlands", "Poland",
    # Geopolitically charged
    "Israel", "Iran", "Ukraine", "Taiwan", "Hungary",
    # Also relevant for KC's lens
    "Greece", "Peru", "Colombia", "Bangladesh",
)

_DAY_FIRST_RE = re.compile(
    r"^(\d{1,2})(?:\s*[-\u2013\u2014]\s*\d{1,2})?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"(?:\s+(\d{4}))?\s*[:\u2013\u2014]\s*(.+?)$"
)
_DAY_FIRST_BARE_RE = re.compile(
    r"^(\d{1,2})(?:\s*[-\u2013\u2014]\s*\d{1,2})?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"(?:\s+(\d{4}))?\s*[:\u2013\u2014]?\s*$"
)
_MONTH_FIRST_RE = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2})(?:\s*[-\u2013\u2014]\s*\d{1,2})?(?:,?\s+(\d{4}))?"
    r"\s*[:\u2013\u2014]\s*(.+?)$"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    all_new: list[dict] = []
    for page_title in WIKI_PAGES:
        events = _fetch_and_parse_page(page_title)
        all_new.extend(events)

    print(f"[elections] Total parsed across all pages: {len(all_new)} matching major nations.")

    if not all_new:
        print("[elections] WARN: parser found zero matching events.",
              file=sys.stderr)
        return 2

    existing = _load_existing()
    merged, added = _merge_dedupe(existing, all_new)
    print(f"[elections] Existing: {len(existing)} | new: {len(all_new)} | "
          f"after merge: {len(merged)} | added: {added}")

    if args.dry_run:
        print("[elections] --dry-run: no write.")
        for ev in merged[:25]:
            print(f"    {ev['date']} | {ev['title']}")
        if len(merged) > 25:
            print(f"    ... and {len(merged) - 25} more")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "source": "wikipedia_electoral",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(merged),
        "events": merged,
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[elections] Wrote {len(merged)} events to {OUTPUT_PATH.name}.")
    return 0


def _fetch_and_parse_page(page_title: str) -> list[dict]:
    print(f"[elections] Fetching {page_title}...")
    try:
        response = requests.get(
            MEDIAWIKI_API,
            params={
                "action": "parse",
                "page": page_title,
                "format": "json",
                "prop": "wikitext",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=FETCH_TIMEOUT_SECS,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"[elections] WARN: fetch failed for {page_title}: {e}",
              file=sys.stderr)
        return []

    if "error" in data:
        print(f"[elections] WARN: page {page_title} not found ({data['error'].get('info')}). "
              f"Skipping (may not exist yet for future year).",
              file=sys.stderr)
        return []

    wikitext = (data.get("parse") or {}).get("wikitext", {}).get("*", "")
    if not wikitext:
        print(f"[elections] WARN: empty wikitext for {page_title}.",
              file=sys.stderr)
        return []

    year_match = re.match(r"^(\d{4})_", page_title)
    if not year_match:
        return []
    year = int(year_match.group(1))

    return _parse_wikitext_events(wikitext, year, page_title)


def _parse_wikitext_events(
    wikitext: str, year: int, page_title: str,
) -> list[dict]:
    """Extract date-prefixed election entries from wikitext lines.

    Tracks the 'current parent date' so sub-bullets (**) inherit date
    from the preceding * line. Truncates each line at the FIRST <ref
    occurrence to avoid multi-line citation block leakage.
    """
    events: list[dict] = []
    seen: set[tuple[str, str]] = set()
    page_url = f"https://en.wikipedia.org/wiki/{page_title}"

    current_parent_date: str | None = None

    for raw_line in wikitext.splitlines():
        # Truncate at first <ref to drop entire citation blocks (which
        # often span multiple lines, defeating single-line regex stripping).
        ref_idx = raw_line.find("<ref")
        if ref_idx != -1:
            raw_line = raw_line[:ref_idx]

        stripped_raw = raw_line.strip()
        is_subbullet = stripped_raw.startswith("**")
        is_topbullet = stripped_raw.startswith("*") and not is_subbullet
        if not (is_subbullet or is_topbullet):
            continue

        line = _strip_wikitext(stripped_raw).strip()
        if not line:
            continue

        iso_date, body = _try_parse_dated_line(line, year)
        if iso_date is not None and body is not None and body.strip():
            if is_topbullet:
                current_parent_date = iso_date
            _maybe_add(events, seen, iso_date, body, page_url)
            continue

        if is_topbullet:
            m_bare = _DAY_FIRST_BARE_RE.match(line)
            if m_bare:
                day = m_bare.group(1)
                month = m_bare.group(2)
                year_str = m_bare.group(3)
                eff_year = int(year_str) if year_str else year
                iso = _to_iso(eff_year, month, day)
                if iso:
                    current_parent_date = iso
                    continue
            current_parent_date = None
            continue

        if is_subbullet and current_parent_date is not None:
            sub_iso, sub_body = _try_parse_dated_line(line, year)
            if sub_iso and sub_body:
                _maybe_add(events, seen, sub_iso, sub_body, page_url)
            else:
                _maybe_add(events, seen, current_parent_date, line, page_url)
            continue

    return events


def _maybe_add(
    events: list[dict],
    seen: set[tuple[str, str]],
    iso_date: str,
    body: str,
    page_url: str,
) -> None:
    if not _matches_major_nation(body):
        return
    title = _format_title(body)
    if not title:
        return
    key = (iso_date, title)
    if key in seen:
        return
    seen.add(key)
    events.append({
        "date": iso_date,
        "title": ftfy.fix_text(title),
        "category": "election",
        "url": page_url,
        "source": "wikipedia_electoral",
    })


def _try_parse_dated_line(
    line: str, fallback_year: int,
) -> tuple[str | None, str | None]:
    m = _DAY_FIRST_RE.match(line)
    if m:
        day, month, year_str, body = m.group(1), m.group(2), m.group(3), m.group(4)
        year = int(year_str) if year_str else fallback_year
        return _to_iso(year, month, day), body

    m = _MONTH_FIRST_RE.match(line)
    if m:
        month, day, year_str, body = m.group(1), m.group(2), m.group(3), m.group(4)
        year = int(year_str) if year_str else fallback_year
        return _to_iso(year, month, day), body

    return None, None


def _to_iso(year: int, month_name: str, day: str) -> str | None:
    try:
        return date_parser.parse(f"{day} {month_name} {year}").date().isoformat()
    except (ValueError, TypeError):
        return None


def _matches_major_nation(body: str) -> bool:
    body_lower = body.lower()
    for nation in MAJOR_NATIONS:
        if nation.lower() in body_lower:
            return True
    return False


def _format_title(body: str) -> str:
    """Trim citation/footnote remnants and length-cap."""
    body = re.sub(r"\[\d+\]", "", body)
    body = re.sub(r"\s+", " ", body).strip()
    body = body.rstrip(".")
    if len(body) > 140:
        body = body[:137].rstrip() + "..."
    return body


_WIKI_LINK_PIPED_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")
_WIKI_BOLDITALIC_RE = re.compile(r"'{2,5}")
_WIKI_TEMPLATE_RE = re.compile(r"\{\{[^}]*\}\}")
_LIST_PREFIX_RE = re.compile(r"^[\*#:]+\s*")


def _strip_wikitext(s: str) -> str:
    s = _LIST_PREFIX_RE.sub("", s)
    s = _WIKI_TEMPLATE_RE.sub("", s)
    s = _WIKI_LINK_PIPED_RE.sub(r"\1", s)
    s = _WIKI_BOLDITALIC_RE.sub("", s)
    return s


def _load_existing() -> list[dict]:
    if not OUTPUT_PATH.exists():
        return []
    try:
        with OUTPUT_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("events", [])
    except (OSError, json.JSONDecodeError):
        return []


def _merge_dedupe(
    existing: list[dict],
    new_events: list[dict],
) -> tuple[list[dict], int]:
    key_set = {(e["date"], e["title"]) for e in existing}
    added = 0
    merged = list(existing)
    for ev in new_events:
        key = (ev["date"], ev["title"])
        if key in key_set:
            continue
        key_set.add(key)
        merged.append(ev)
        added += 1
    merged.sort(key=lambda e: e["date"])
    return merged, added


if __name__ == "__main__":
    sys.exit(main())
