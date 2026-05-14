"""
build_public_feed.py

Merges two source feeds into the unified events_public.json that the
Flutter app reads:

  1. manual_events.json     - 39 chart-derived ECM cycle dates,
                              hand-curated from Armstrong's published
                              cycle charts.
  2. synthesis_results.json - 9 blog-derived forecasts that passed
                              Pass 1 -> Pass 1.5 -> Pass 2 synthesis,
                              then manual cleanup.

The output is a single Forecast-shaped list sorted by event_date
ascending, with schema_version=1.0 (additive new fields: category, tag).

The synthesis-derived entries get normalized:
  - wp_id -> id (prefix 'blog-')
  - predicted_date -> event_date
  - category_suggestion -> category
  - tag_suggestion -> tag
  - importance is assigned per the (b3) rule: medium default, high only
    for entries that explicitly amend a prior ECM date
  - source is filled from the link field
  - related_events defaults to []

The chart-derived entries are mostly already in shape - just need:
  - date -> event_date
  - source object preserved
  - confidence field stripped (not part of unified schema)

Schema version stays at 1.0; new fields (category, tag, origin) are
additive and old APKs ignore them per project guide.

Usage:
    python build_public_feed.py            # merge and write
    python build_public_feed.py --dry-run  # show summary, no write

Reads:
    backend/output/manual_events.json
    backend/output/synthesis_results.json
Writes:
    backend/output/events_public.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
MANUAL_PATH = SCRIPT_DIR.parent / "output" / "manual_events.json"
SYNTH_PATH = SCRIPT_DIR.parent / "output" / "synthesis_results.json"
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "events_public.json"

# Titles that get "high" importance because they explicitly amend a prior
# ECM-attributed date. Per the (b3) rule for blog forecasts.
HIGH_IMPORTANCE_TITLES = {
    "Next ECM is July 1/2 not June 1",
}

BLOG_DEFAULT_IMPORTANCE = "medium"


def normalize_manual_entry(entry: dict) -> dict:
    """
    manual_events.json entries are already mostly in Forecast shape.
    Rename date -> event_date, drop confidence, add origin.
    """
    return {
        "id": entry["id"],
        "event_date": entry["date"],
        "title": entry.get("title", ""),
        "subtitle": entry.get("subtitle", ""),
        "category": entry.get("category", "ecm_panic"),
        "tag": entry.get("tag", ""),
        "importance": entry.get("importance", "medium"),
        "is_convergence": entry.get("is_convergence", False),
        "importance_justification": entry.get("importance_justification", ""),
        "synthesis": entry.get("synthesis", ""),
        "source": entry.get("source", {"name": "", "url": None}),
        "related_events": entry.get("related_events", []),
        "origin": "chart",
    }


def normalize_synth_entry(entry: dict) -> dict:
    """synthesis_results.json entry -> unified Forecast shape."""
    wp_id = entry.get("wp_id", "")
    title = entry.get("title", "")
    predicted_date = entry.get("predicted_date", "")
    link = entry.get("link", "")
    synthesis = entry.get("synthesis", "")
    category = entry.get("category_suggestion", "ecm_panic")
    tag = entry.get("tag_suggestion", "")

    importance = (
        "high" if title in HIGH_IMPORTANCE_TITLES
        else BLOG_DEFAULT_IMPORTANCE
    )
    justification = (
        "Auto-derived from blog post synthesis. Explicit ECM date amendment."
        if importance == "high"
        else "Auto-derived from blog post synthesis. Standard blog-derived forecast."
    )

    return {
        "id": f"blog-{wp_id}",
        "event_date": predicted_date,
        "title": title,
        "subtitle": "",
        "category": category,
        "tag": tag,
        "importance": importance,
        "is_convergence": False,
        "importance_justification": justification,
        "synthesis": synthesis,
        "source": {
            "name": "Armstrong Economics blog (public RSS)",
            "url": link,
        },
        "related_events": [],
        "origin": "blog",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show summary, don't write output.")
    args = parser.parse_args()

    if not MANUAL_PATH.exists():
        print(f"[build_public_feed] ERROR: {MANUAL_PATH} not found.",
              file=sys.stderr)
        return 1
    if not SYNTH_PATH.exists():
        print(f"[build_public_feed] ERROR: {SYNTH_PATH} not found.",
              file=sys.stderr)
        return 1

    with MANUAL_PATH.open("r", encoding="utf-8") as f:
        manual_payload = json.load(f)
    with SYNTH_PATH.open("r", encoding="utf-8") as f:
        synth_payload = json.load(f)

    manual_entries = manual_payload.get("forecasts", [])
    synth_entries = synth_payload.get("results", [])

    print(f"[build_public_feed] Manual events: {len(manual_entries)}")
    print(f"[build_public_feed] Synthesis results: {len(synth_entries)}")

    normalized_manual = [normalize_manual_entry(e) for e in manual_entries]
    normalized_synth = [normalize_synth_entry(e) for e in synth_entries]

    all_forecasts = normalized_manual + normalized_synth

    # Sort by event_date ascending (oldest-future-first per (d1)).
    all_forecasts.sort(key=lambda f: f.get("event_date", "9999-01-01"))

    cat_counts = Counter(f.get("category", "") for f in all_forecasts)
    imp_counts = Counter(f.get("importance", "") for f in all_forecasts)
    origin_counts = Counter(f.get("origin", "") for f in all_forecasts)

    print(f"\n[build_public_feed] Total merged: {len(all_forecasts)}")
    print(f"[build_public_feed] By origin: {dict(origin_counts)}")
    print(f"[build_public_feed] By importance: {dict(imp_counts)}")
    print(f"[build_public_feed] By category:")
    for cat, count in cat_counts.most_common():
        print(f"    {cat}: {count}")

    dates = [f.get("event_date", "") for f in all_forecasts if f.get("event_date")]
    if dates:
        print(f"[build_public_feed] Date range: {min(dates)} to {max(dates)}")

    print(f"\n[build_public_feed] First 5 (earliest dates):")
    for f in all_forecasts[:5]:
        print(
            f"    {f['event_date']} | {f['importance']:6s} | "
            f"{f['origin']:5s} | {f['category']:20s} | {f['title']}"
        )

    print(f"\n[build_public_feed] Last 5 (latest dates):")
    for f in all_forecasts[-5:]:
        print(
            f"    {f['event_date']} | {f['importance']:6s} | "
            f"{f['origin']:5s} | {f['category']:20s} | {f['title']}"
        )

    # Validation: every entry must have event_date and title.
    missing_fields: list[tuple[str, str]] = []
    for f in all_forecasts:
        if not f.get("event_date"):
            missing_fields.append((f.get("id", "???"), "event_date"))
        if not f.get("title"):
            missing_fields.append((f.get("id", "???"), "title"))
    if missing_fields:
        print(
            f"\n[build_public_feed] ERROR: {len(missing_fields)} entries "
            f"missing required fields. Aborting.",
            file=sys.stderr,
        )
        for fid, field in missing_fields[:10]:
            print(f"  MISSING {field}: id={fid}", file=sys.stderr)
        return 1

    # Check for duplicate IDs.
    id_counts = Counter(f.get("id", "") for f in all_forecasts)
    dupes = [fid for fid, c in id_counts.items() if c > 1]
    if dupes:
        print(
            f"\n[build_public_feed] ERROR: {len(dupes)} duplicate IDs. Aborting.",
            file=sys.stderr,
        )
        for fid in dupes[:10]:
            print(f"  DUPLICATE: {fid}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("\n[build_public_feed] --dry-run: no changes written.")
        return 0

    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feed_type": "public",
        "source_summary": (
            f"{len(normalized_manual)} chart-derived ECM cycle dates + "
            f"{len(normalized_synth)} blog-derived forecasts "
            f"(Pass 1 -> 1.5 -> 2 synthesis, manually curated). "
            f"Merged and sorted ascending by event_date."
        ),
        "forecast_count": len(all_forecasts),
        "forecasts": all_forecasts,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(
        f"\n[build_public_feed] Wrote {len(all_forecasts)} forecasts to "
        f"{OUTPUT_PATH.name}."
    )
    print("[build_public_feed] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
