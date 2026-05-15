"""
scheduled_events_treasury.py

Generates upcoming US Treasury 20-Year and 30-Year bond auction dates
from Treasury's documented pattern. Per TreasuryDirect (When Auctions
Happen):

  - 20-year bond: auctioned the next-to-last Wednesday of months in
    Feb/May/Aug/Nov (originals) and Jan/Mar/Apr/Jun/Jul/Sep/Oct/Dec
    (reopenings).
  - 30-year bond: auctioned during the second week of the same months.

We deviated from API scraping because:
  1. The "upcoming_auctions" fiscaldata API endpoint only returns ~1
     week of forward data (confirmed: 100 total rows, 3 long-dated).
  2. The "treasury_securities_auctions_data" endpoint goes back to
     1979 with no clean future-only filter.
  3. The "Tentative Auction Schedule" lives in a PDF, fragile to parse.

Rule-based generation is honest: Treasury follows its documented
pattern very reliably. Specials/holidays can shift by a day; we don't
attempt to model holiday adjustments. The +/-7 day window in
build_public_feed.py absorbs small drift.

Source for the pattern:
  https://www.treasurydirect.gov/auctions/when-auctions-happen/
Last verified: 2026-05-15

Output: scheduled_events_treasury.json with category=sovereign_debt,
picked up by build_public_feed.py with +/-7 day window.

Usage:
    python scheduled_events_treasury.py            # write file
    python scheduled_events_treasury.py --dry-run  # show what would change
"""

from __future__ import annotations

import argparse
import json
import sys
from calendar import Calendar, WEDNESDAY
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "scheduled_events_treasury.json"

_SOURCE_URL = "https://www.treasurydirect.gov/auctions/when-auctions-happen/"

# Year range to generate. Cover current year and next year.
_YEAR_START = 2026
_YEAR_END = 2027

# Months when 20Y bonds are auctioned with their auction type.
# "original" = first issuance; "reopening" = additional supply of an
# existing issue.
_20Y_MONTHS: dict[int, str] = {
    1: "reopening",
    2: "original",
    3: "reopening",
    4: "reopening",
    5: "original",
    6: "reopening",
    7: "reopening",
    8: "original",
    9: "reopening",
    10: "reopening",
    11: "original",
    12: "reopening",
}
# 30Y same months/types as 20Y.
_30Y_MONTHS = _20Y_MONTHS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    events: list[dict] = []
    for year in range(_YEAR_START, _YEAR_END + 1):
        for month in range(1, 13):
            # 30Y: 2nd Wednesday of the month
            d30 = _nth_weekday(year, month, WEDNESDAY, 2)
            if d30:
                kind = _30Y_MONTHS.get(month, "reopening")
                suffix = " (reopening)" if kind == "reopening" else ""
                events.append({
                    "date": d30.isoformat(),
                    "title": f"30-Year Bond auction{suffix}",
                    "category": "sovereign_debt",
                    "url": _SOURCE_URL,
                    "source": "treasury_pattern",
                })
            # 20Y: next-to-last Wednesday of the month
            d20 = _nth_to_last_weekday(year, month, WEDNESDAY, 2)
            if d20:
                kind = _20Y_MONTHS.get(month, "reopening")
                suffix = " (reopening)" if kind == "reopening" else ""
                events.append({
                    "date": d20.isoformat(),
                    "title": f"20-Year Bond auction{suffix}",
                    "category": "sovereign_debt",
                    "url": _SOURCE_URL,
                    "source": "treasury_pattern",
                })

    events.sort(key=lambda e: e["date"])

    print(f"[treasury] Generated {len(events)} long-dated bond auctions.")
    print(f"[treasury] Date range: {events[0]['date']} to {events[-1]['date']}")

    if args.dry_run:
        print("[treasury] --dry-run: no write.")
        for e in events[:24]:
            print(f"    {e['date']} | {e['title']}")
        if len(events) > 24:
            print(f"    ... and {len(events) - 24} more")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "source": "treasury_pattern",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(events),
        "events": events,
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[treasury] Wrote {len(events)} events to {OUTPUT_PATH.name}.")
    return 0


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date | None:
    """Return the nth occurrence (1-indexed) of `weekday` in the given
    month. Returns None if month doesn't have that many."""
    cal = Calendar()
    matching = [
        d for d in cal.itermonthdates(year, month)
        if d.month == month and d.weekday() == weekday
    ]
    if n <= 0 or n > len(matching):
        return None
    return matching[n - 1]


def _nth_to_last_weekday(
    year: int, month: int, weekday: int, n: int,
) -> date | None:
    """Return the nth-to-last occurrence (1-indexed; 1=last, 2=next-to-last)
    of `weekday` in the given month."""
    cal = Calendar()
    matching = [
        d for d in cal.itermonthdates(year, month)
        if d.month == month and d.weekday() == weekday
    ]
    if n <= 0 or n > len(matching):
        return None
    return matching[-n]


if __name__ == "__main__":
    sys.exit(main())
