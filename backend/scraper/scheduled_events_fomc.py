"""
scheduled_events_fomc.py

Scrapes the Federal Reserve's FOMC meeting calendar at
https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

The Fed publishes the FOMC meeting schedule as a single HTML page,
server-rendered, no anti-bot measures, public. Updated quarterly when
new meetings are added.

Output: list of dicts with date, title, category, url. Written to
scheduled_events_fomc.json (cumulative append, deduped by date+title).

This is one of three feeders for scheduled_events.json. The merge step
in scheduled_events_build.py combines all feeders into one list that
build_public_feed.py attaches to forecasts within +/-5 days.

Usage:
    python scheduled_events_fomc.py            # fetch and merge
    python scheduled_events_fomc.py --dry-run  # show what would change
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dateutil import parser as date_parser

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "scheduled_events_fomc.json"
FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
USER_AGENT = (
    "ecmforecastpub/1.0 (+https://github.com/"
    "kiriakoschristodoulou-netizen/ecmforecastpub)"
)
FETCH_TIMEOUT_SECS = 20


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"[fomc] Fetching {FOMC_URL}...")
    try:
        response = requests.get(
            FOMC_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=FETCH_TIMEOUT_SECS,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[fomc] ERROR: fetch failed: {e}", file=sys.stderr)
        return 1

    html = response.text
    print(f"[fomc] Got {len(html)} bytes.")

    new_events = _parse_fomc_html(html)
    print(f"[fomc] Parsed {len(new_events)} meetings.")

    if not new_events:
        print(
            "[fomc] WARN: parser found zero meetings. Page layout may have changed.",
            file=sys.stderr,
        )
        return 2  # not fatal but flag for investigation

    # Cumulative merge.
    existing = _load_existing()
    merged, added = _merge_dedupe(existing, new_events)
    print(f"[fomc] Existing: {len(existing)} | new: {len(new_events)} | "
          f"after merge: {len(merged)} | added: {added}")

    if args.dry_run:
        print("[fomc] --dry-run: no write.")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "source": "fomc",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(merged),
        "events": merged,
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[fomc] Wrote {len(merged)} events to {OUTPUT_PATH.name}.")
    return 0


# FOMC meeting date patterns the Fed uses on their calendar page:
#   "January 27-28"           (typical 2-day meeting in a year context)
#   "March 17-18*"            (asterisk denotes press conference)
#   "April 28-29"
# The year is embedded in surrounding heading (e.g., "2026 FOMC Meetings").
_YEAR_HEADING_RE = re.compile(r"(\d{4})\s+FOMC\s+Meetings", re.IGNORECASE)
_MEETING_RANGE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2})\s*[-\u2013\u2014]\s*(\d{1,2})\b"
)
# Some single-day meetings appear as "August 19" (rare).
_MEETING_SINGLE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2})(?!\s*[-\u2013\u2014\d])"
)


def _parse_fomc_html(html: str) -> list[dict]:
    """Extract FOMC meeting dates from the Fed's calendar HTML."""
    events: list[dict] = []
    seen: set[tuple[str, str]] = set()  # (iso_date, title) dedupe

    # Find year headings; for each, find meeting date patterns in the
    # surrounding ~3000 chars (one year's panel).
    year_positions = [
        (m.group(1), m.start()) for m in _YEAR_HEADING_RE.finditer(html)
    ]
    if not year_positions:
        return events

    # Append a sentinel end position.
    year_positions.append(("", len(html)))

    for i in range(len(year_positions) - 1):
        year, start = year_positions[i]
        _, end = year_positions[i + 1]
        section = html[start:end]

        # Two-day meetings: use the SECOND day as the canonical date
        # (the rate decision day; first day is the policy discussion).
        for m in _MEETING_RANGE_RE.finditer(section):
            month_name, day1, day2 = m.group(1), m.group(2), m.group(3)
            iso_date = _to_iso(year, month_name, day2)
            if iso_date is None:
                continue
            title = "FOMC meeting (rate decision)"
            key = (iso_date, title)
            if key in seen:
                continue
            seen.add(key)
            events.append({
                "date": iso_date,
                "title": title,
                "category": "central_bank",
                "url": FOMC_URL,
                "source": "fomc",
            })

        # Single-day meetings (rare).
        for m in _MEETING_SINGLE_RE.finditer(section):
            month_name, day = m.group(1), m.group(2)
            iso_date = _to_iso(year, month_name, day)
            if iso_date is None:
                continue
            title = "FOMC meeting"
            key = (iso_date, title)
            if key in seen:
                continue
            seen.add(key)
            events.append({
                "date": iso_date,
                "title": title,
                "category": "central_bank",
                "url": FOMC_URL,
                "source": "fomc",
            })

    return events


def _to_iso(year: str, month_name: str, day: str) -> str | None:
    try:
        return date_parser.parse(f"{day} {month_name} {year}").date().isoformat()
    except (ValueError, TypeError):
        return None


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
    """Merge new events into existing, deduped by (date, title). Returns
    (merged, count_added). Existing entries win on conflict."""
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
