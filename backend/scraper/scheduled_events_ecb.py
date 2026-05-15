"""
scheduled_events_ecb.py

Hardcoded ECB Governing Council monetary policy meeting dates. The ECB
website (https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html)
is buried in nav HTML and only lists ~7-8 dates per year, so the cost
of scraping outweighs the value of automation. Hardcode is simpler
and more reliable.

Update procedure: once a year (typically Q3-Q4 when ECB publishes the
following year's calendar), come back to this file and add the next
year's dates. Set _LAST_VERIFIED to the date you confirmed.

Source: https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html
Last verified: 2026-05-15

Per source 'ecb.europa.eu' (official 2026 calendar) and 'skilling.com'
(2026 trading guide), the 2026 monetary policy meetings are confirmed
as listed below. The ECB also holds non-monetary policy meetings twice
a month, but those rarely move markets — we only track the rate-setting
ones.

Output: scheduled_events_ecb.json with category=central_bank, picked
up by build_public_feed.py with +/-14 day window (same as FOMC).

Usage:
    python scheduled_events_ecb.py            # write file
    python scheduled_events_ecb.py --dry-run  # show what would change
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "scheduled_events_ecb.json"

_LAST_VERIFIED = "2026-05-15"

# ECB Governing Council monetary policy meetings. Add new years as the
# ECB publishes them.
_ECB_MEETINGS: tuple[tuple[str, str], ...] = (
    # 2025 (historical reference, harmless to keep)
    ("2025-01-30", "ECB Governing Council monetary policy meeting"),
    ("2025-03-06", "ECB Governing Council monetary policy meeting"),
    ("2025-04-17", "ECB Governing Council monetary policy meeting"),
    ("2025-06-05", "ECB Governing Council monetary policy meeting"),
    ("2025-07-24", "ECB Governing Council monetary policy meeting"),
    ("2025-09-11", "ECB Governing Council monetary policy meeting"),
    ("2025-10-30", "ECB Governing Council monetary policy meeting"),
    ("2025-12-18", "ECB Governing Council monetary policy meeting"),
    # 2026 (confirmed by ECB, per ecb.europa.eu/press/calendars/mgcgc)
    ("2026-03-19", "ECB Governing Council monetary policy meeting"),
    ("2026-04-30", "ECB Governing Council monetary policy meeting"),
    ("2026-06-11", "ECB Governing Council monetary policy meeting"),
    ("2026-07-23", "ECB Governing Council monetary policy meeting"),
    ("2026-09-10", "ECB Governing Council monetary policy meeting"),
    ("2026-10-29", "ECB Governing Council monetary policy meeting"),
    ("2026-12-17", "ECB Governing Council monetary policy meeting"),
    # 2027: NOT YET PUBLISHED by ECB (as of May 2026). Add when available,
    # typically Q3 2026.
)

_SOURCE_URL = "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    events = [
        {
            "date": date_str,
            "title": title,
            "category": "central_bank",
            "url": _SOURCE_URL,
            "source": "ecb",
        }
        for date_str, title in _ECB_MEETINGS
    ]
    events.sort(key=lambda e: e["date"])

    print(f"[ecb] Loaded {len(events)} ECB Governing Council meetings.")
    print(f"[ecb] Last verified: {_LAST_VERIFIED}")
    print(f"[ecb] Date range: {events[0]['date']} to {events[-1]['date']}")

    if args.dry_run:
        print("[ecb] --dry-run: no write.")
        for e in events:
            print(f"    {e['date']} | {e['title']}")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "source": "ecb",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "last_verified": _LAST_VERIFIED,
        "event_count": len(events),
        "events": events,
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[ecb] Wrote {len(events)} events to {OUTPUT_PATH.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
