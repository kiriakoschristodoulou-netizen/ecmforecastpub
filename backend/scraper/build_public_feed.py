"""
build_public_feed.py

Merges manual_events.json (chart-derived) + synthesis_results.json
(blog-derived) into the unified events_public.json that the Flutter
app reads. Attaches scheduled_events.json entries (Fed FOMC, Wikipedia
electoral calendars) to forecasts within per-category windows, and
sets is_convergence=true when a forecast has 2+ related_events.

Per-category windows (the (delta) decision in session 8f):
  - central_bank (FOMC): +/-14 days. Meetings dominate the news cycle
    around them; markets pre-position ~2 weeks before/after.
  - election: +/-5 days. Elections are point events. Tight window
    preserves "in the election week" signal.
  - other categories: +/-14 days default.

Convergence threshold: 2+ related events attach. A forecast with both
a nearby FOMC and a nearby election IS genuinely a high-density period.

Reads:
    backend/output/manual_events.json
    backend/output/synthesis_results.json
    backend/output/scheduled_events.json   (optional)

Writes:
    backend/output/events_public.json

Usage:
    python build_public_feed.py
    python build_public_feed.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
MANUAL_PATH = SCRIPT_DIR.parent / "output" / "manual_events.json"
SYNTH_PATH = SCRIPT_DIR.parent / "output" / "synthesis_results.json"
SCHEDULED_PATH = SCRIPT_DIR.parent / "output" / "scheduled_events.json"
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "events_public.json"

# Per-category +/-day windows. Falls back to DEFAULT_WINDOW_DAYS for
# any category not listed. The (delta) decision in session 8f: tighter
# window for elections (point events), wider for central bank meetings
# (news-cycle events).
CATEGORY_WINDOW_DAYS: dict[str, int] = {
    "central_bank": 14,
    "election": 5,
    "summit": 7,
    "treaty": 7,
    "military": 7,
    "economic_data": 7,
    "sovereign_debt": 7,
}
DEFAULT_WINDOW_DAYS = 14

# Per session-3 decision: a forecast with 2+ related events triggers
# is_convergence=true and the CONVERGENCE! badge in the UI.
CONVERGENCE_THRESHOLD = 2

# Cap on related_events attached to a single forecast. Cards render
# fine with 3-5 related but more becomes clutter.
MAX_RELATED_PER_FORECAST = 6

HIGH_IMPORTANCE_TITLES = {
    "Next ECM is July 1/2 not June 1",
}
BLOG_DEFAULT_IMPORTANCE = "medium"

# Sort priority for trimming when over the cap. Lower number = higher
# priority (more likely to survive trim).
_CATEGORY_PRIORITY = {
    "central_bank": 0,
    "election": 1,
    "summit": 2,
    "treaty": 3,
    "military": 4,
    "economic_data": 5,
    "sovereign_debt": 6,
    "other": 99,
}


def normalize_manual_entry(entry: dict) -> dict:
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


def load_scheduled_events() -> list[dict]:
    if not SCHEDULED_PATH.exists():
        print(f"[build_public_feed] No scheduled_events.json found. "
              f"Skipping attachment step.")
        return []
    try:
        with SCHEDULED_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[build_public_feed] WARN: failed to load scheduled_events.json: {e}. "
              f"Skipping attachment step.", file=sys.stderr)
        return []

    events = data.get("events", [])
    print(f"[build_public_feed] Loaded {len(events)} scheduled events.")
    return events


def attach_related_events(
    forecasts: list[dict],
    scheduled: list[dict],
) -> None:
    """For each forecast, attach scheduled events within the per-category
    window. Mutates forecast dicts in place. Sets is_convergence=true
    when 2+ events attach."""
    if not scheduled:
        return

    # Pre-parse scheduled event dates once.
    parsed_sched: list[tuple[date, dict, int]] = []  # (date, event, window_days)
    for ev in scheduled:
        d = _parse_iso_date(ev.get("date", ""))
        if d is None:
            continue
        category = ev.get("category", "other")
        window = CATEGORY_WINDOW_DAYS.get(category, DEFAULT_WINDOW_DAYS)
        parsed_sched.append((d, ev, window))

    convergence_set: int = 0
    attach_count: int = 0

    for f in forecasts:
        f_date = _parse_iso_date(f.get("event_date", ""))
        if f_date is None:
            continue

        # An event attaches if it's within ITS OWN category-specific
        # window of the forecast date.
        nearby: list[tuple[int, dict]] = []  # (abs_days_offset, event)
        for sched_date, sched_ev, window in parsed_sched:
            offset = abs((sched_date - f_date).days)
            if offset <= window:
                nearby.append((offset, sched_ev))

        if not nearby:
            continue

        # Sort: closer dates first, then by category priority.
        nearby.sort(key=lambda t: (
            t[0],
            _CATEGORY_PRIORITY.get(t[1].get("category", "other"), 99),
        ))

        capped = nearby[:MAX_RELATED_PER_FORECAST]
        attached = [
            {
                "date": ev["date"],
                "title": ev["title"],
                "category": ev.get("category", "other"),
                "url": ev.get("url"),
            }
            for _, ev in capped
        ]
        f["related_events"] = attached
        attach_count += len(attached)

        if len(attached) >= CONVERGENCE_THRESHOLD:
            f["is_convergence"] = True
            convergence_set += 1

    n_with_attachments = sum(1 for f in forecasts if f["related_events"])
    print(f"[build_public_feed] Attached {attach_count} related events "
          f"across {n_with_attachments} forecasts.")
    print(f"[build_public_feed] Convergence flagged on {convergence_set} forecasts.")


def _parse_iso_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.split("T")[0]).date()
    except (ValueError, TypeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
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

    scheduled = load_scheduled_events()
    attach_related_events(all_forecasts, scheduled)

    all_forecasts.sort(key=lambda f: f.get("event_date", "9999-01-01"))

    cat_counts = Counter(f.get("category", "") for f in all_forecasts)
    imp_counts = Counter(f.get("importance", "") for f in all_forecasts)
    origin_counts = Counter(f.get("origin", "") for f in all_forecasts)
    conv_count = sum(1 for f in all_forecasts if f.get("is_convergence"))

    print(f"\n[build_public_feed] Total merged: {len(all_forecasts)}")
    print(f"[build_public_feed] By origin: {dict(origin_counts)}")
    print(f"[build_public_feed] By importance: {dict(imp_counts)}")
    print(f"[build_public_feed] Convergence: {conv_count}")
    print(f"[build_public_feed] By category:")
    for cat, count in cat_counts.most_common():
        print(f"    {cat}: {count}")

    dates = [f.get("event_date", "") for f in all_forecasts if f.get("event_date")]
    if dates:
        print(f"[build_public_feed] Date range: {min(dates)} to {max(dates)}")

    print(f"\n[build_public_feed] First 5 (earliest dates):")
    for f in all_forecasts[:5]:
        conv = " [CONV]" if f.get("is_convergence") else ""
        related_n = len(f.get("related_events", []))
        related_tag = f" (+{related_n} related)" if related_n else ""
        print(
            f"    {f['event_date']} | {f['importance']:6s} | "
            f"{f['origin']:5s} | {f['category']:20s} | {f['title']}{related_tag}{conv}"
        )

    print(f"\n[build_public_feed] Last 5 (latest dates):")
    for f in all_forecasts[-5:]:
        conv = " [CONV]" if f.get("is_convergence") else ""
        related_n = len(f.get("related_events", []))
        related_tag = f" (+{related_n} related)" if related_n else ""
        print(
            f"    {f['event_date']} | {f['importance']:6s} | "
            f"{f['origin']:5s} | {f['category']:20s} | {f['title']}{related_tag}{conv}"
        )

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
            f"(Pass 1 -> 1.5 -> 2 synthesis, auto-cleaned). "
            f"{len(scheduled)} scheduled events attached within per-category windows "
            f"(FOMC +/-14d, elections +/-5d). "
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
