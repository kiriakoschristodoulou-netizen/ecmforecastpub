"""
scheduled_events_build.py

Combines all feeder outputs into a single scheduled_events.json that
build_public_feed.py reads and attaches to forecasts within per-category
windows.

Feeders (any that exist are loaded; missing ones soft-skip):
    scheduled_events_fomc.json         (Fed FOMC, scraped)
    scheduled_events_elections.json    (Wikipedia electoral calendars, scraped)
    scheduled_events_ecb.json          (ECB monetary policy, hardcoded)
    scheduled_events_opec.json         (OPEC meetings, hardcoded)
    scheduled_events_treasury.json     (20Y/30Y bond auctions, scraped via API)

NATO summits intentionally dropped in session 8f: no clean source URL,
~1-2 events/year, easier to add manually to manual_events.json when
announced.

Writes:
    backend/output/scheduled_events.json

Usage:
    python scheduled_events_build.py
    python scheduled_events_build.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR.parent / "output"

FEEDER_PATHS = [
    OUTPUT_DIR / "scheduled_events_fomc.json",
    OUTPUT_DIR / "scheduled_events_elections.json",
    OUTPUT_DIR / "scheduled_events_ecb.json",
    OUTPUT_DIR / "scheduled_events_opec.json",
    OUTPUT_DIR / "scheduled_events_treasury.json",
]
OUTPUT_PATH = OUTPUT_DIR / "scheduled_events.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    all_events: list[dict] = []
    sources_loaded: list[str] = []

    for path in FEEDER_PATHS:
        if not path.exists():
            print(f"[scheduled_build] Skipping missing feeder: {path.name}")
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"[scheduled_build] WARN: failed to load {path.name}: {e}",
                  file=sys.stderr)
            continue

        events = data.get("events", [])
        all_events.extend(events)
        sources_loaded.append(data.get("source", path.stem))
        print(f"[scheduled_build] Loaded {len(events)} from {path.name}")

    if not all_events:
        print("[scheduled_build] No feeder data found. Nothing to build.")
        return 0

    seen: set[tuple[str, str]] = set()
    merged: list[dict] = []
    for ev in all_events:
        key = (ev.get("date"), ev.get("title"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(ev)

    merged.sort(key=lambda e: e.get("date") or "")

    source_counts = Counter(e.get("source", "unknown") for e in merged)
    cat_counts = Counter(e.get("category", "unknown") for e in merged)

    print(f"[scheduled_build] Total unique events: {len(merged)}")
    print(f"[scheduled_build] By source: {dict(source_counts)}")
    print(f"[scheduled_build] By category: {dict(cat_counts)}")

    if merged:
        print(f"[scheduled_build] Date range: {merged[0]['date']} to "
              f"{merged[-1]['date']}")

    if args.dry_run:
        print("[scheduled_build] --dry-run: no write.")
        return 0

    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(merged),
        "sources": sources_loaded,
        "events": merged,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[scheduled_build] Wrote {len(merged)} events to {OUTPUT_PATH.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
