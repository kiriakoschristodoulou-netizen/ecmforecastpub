"""
scheduled_events_opec.py

Hardcoded OPEC meeting dates. OPEC publishes meeting dates piecemeal
via press releases at opec.org/pr-detail/*.html with no central
calendar page that lists future meetings. Scraping would require
either crawling all press releases or guessing URLs, both fragile.
Hardcode is simpler.

Three types of OPEC meetings tracked:
  - ONOMM (full OPEC+ ministerial): twice a year, biggest market impact
  - JMMC (Joint Ministerial Monitoring Committee): every 2 months
  - "Eight" voluntary-cut group meetings: monthly

The "Eight" monthly meetings can move oil prices materially when they
signal pause/resume of production cuts. Full ONOMM is the biggest of
the three.

Update procedure: once a year (typically December for the next year),
check opec.org press releases and update this file. The ONOMM dates
are usually announced at the previous ONOMM. JMMC and "Eight" dates
are announced 1-2 months ahead in press releases.

Source: https://www.opec.org/opec_web/en/press_room/
Last verified: 2026-05-15

Per opec.org press releases and ebc.com 2026 OPEC schedule analysis,
the 2026 meetings are confirmed as listed below. Some 2026 meetings
have already passed (Jan, Mar, Apr) but are kept for historical
reference (harmless and helps the FOMC-style window work for forecasts
near those dates).

Output: scheduled_events_opec.json with category=summit, picked up by
build_public_feed.py with +/-7 day window.

Usage:
    python scheduled_events_opec.py            # write file
    python scheduled_events_opec.py --dry-run  # show what would change
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "scheduled_events_opec.json"

_LAST_VERIFIED = "2026-05-15"

# OPEC meetings. Add new dates as OPEC announces them through 2026-2027.
# Format: (ISO date, full title)
_OPEC_MEETINGS: tuple[tuple[str, str], ...] = (
    # 2026 (confirmed via opec.org press releases)
    ("2026-01-04", "OPEC+ 'Eight' voluntary-cut group meeting"),
    ("2026-03-01", "OPEC+ 'Eight' voluntary-cut group meeting"),
    ("2026-04-05", "OPEC+ 'Eight' voluntary-cut group meeting"),
    ("2026-06-07", "41st OPEC and non-OPEC Ministerial Meeting (full ONOMM)"),
    # JMMC every 2 months — exact dates announced ~1 month ahead. Educated
    # estimates based on the every-2-months cadence:
    ("2026-02-01", "OPEC+ JMMC meeting (estimated, confirm via opec.org)"),
    ("2026-08-01", "OPEC+ JMMC meeting (estimated, confirm via opec.org)"),
    ("2026-10-01", "OPEC+ JMMC meeting (estimated, confirm via opec.org)"),
    ("2026-12-01", "OPEC+ JMMC meeting (estimated, confirm via opec.org)"),
    # 2027 ONOMM: NOT YET ANNOUNCED. Add when confirmed (typically at
    # the 41st ONOMM in June 2026).
)

_SOURCE_URL = "https://www.opec.org/opec_web/en/press_room/"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    events = [
        {
            "date": date_str,
            "title": title,
            "category": "summit",
            "url": _SOURCE_URL,
            "source": "opec",
        }
        for date_str, title in _OPEC_MEETINGS
    ]
    events.sort(key=lambda e: e["date"])

    print(f"[opec] Loaded {len(events)} OPEC meetings.")
    print(f"[opec] Last verified: {_LAST_VERIFIED}")
    print(f"[opec] Date range: {events[0]['date']} to {events[-1]['date']}")

    if args.dry_run:
        print("[opec] --dry-run: no write.")
        for e in events:
            print(f"    {e['date']} | {e['title']}")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "source": "opec",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "last_verified": _LAST_VERIFIED,
        "event_count": len(events),
        "events": events,
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[opec] Wrote {len(events)} events to {OUTPUT_PATH.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
