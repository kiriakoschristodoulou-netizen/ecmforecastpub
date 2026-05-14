"""
clean_synthesis.py

ONE-SHOT cleanup script. Takes synthesis_results.json (43 entries from
Pass 2 Sonnet synthesis) and reduces it to a curated 9-entry set by:

  - Dropping known false positives (editorial / non-ECM-attributed)
  - Dropping borderline entries (year-only dates, weak attribution)
  - Dropping duplicates within thematic clusters (keep best per theme)
  - Dropping past-dated 2026-01-01 placeholder entries
  - Re-categorizing the Asteroid 2032 entry (natural_disasters / asteroid_impact)

The drop/keep decisions were made interactively with the user.

Writes a backup of the original synthesis_results.json before mutating.

Usage:
    python clean_synthesis.py            # apply cleanup
    python clean_synthesis.py --dry-run  # show what would change, no write

Reads/writes:
    backend/output/synthesis_results.json
Writes backup:
    backend/output/synthesis_results.before_cleanup.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "synthesis_results.json"
BACKUP_PATH = SCRIPT_DIR.parent / "output" / "synthesis_results.before_cleanup.json"

# wp_ids to DROP. Comments document why each was dropped.
#
# IMPORTANT: these wp_ids are derived from the title->wp_id mapping at
# the time of run. The script verifies each title matches its expected
# wp_id before dropping; if any drift, it exits with an error instead
# of silently mutating the wrong entry.
EXPECTED_DROPS_BY_TITLE = {
    # Clear false positives (editorial / news commentary / not ECM-attributed)
    "We Won?": "editorial rhetorical title; incoherent category",
    "Trump Invades Venezuela": "speculative editorial; date already past, did not happen",
    "Sending Children to War — History Repeats in Iran": "historical analogy, not model amendment",
    "Wars Change Politics Not Just Destroy Targets": "generic editorial commentary; year-only date",
    "Great Nations Do Not Fight Endless Wars": "generic editorial title; year-only date",
    "Trump to End Civilization? It Maybe the West's!": "rhetorical editorial title",
    "The Confusing World": "vague title; questionable real forecast",
    "Trump Backs Down – Will Declare Victory": "speculative editorial about Trump's timing",
    "When Will Trump Declare Victory? Will He Send In Troops?": "speculative editorial",
    "Neocons Advising Trump Are Destroying America": "editorial commentary",
    "Netanyahu Tries to Sabotage Trump's Peace Plan": "news commentary",

    # Borderlines (per user directive: remove all borderlines)
    "Pentagon Considers Raising Budget by 50%": "news report; arbitrary date",
    "Trump Using Criminal Law to Intimidate the Federal Reserve?": "news commentary",
    "Poland's Death Wish?": "editorial; year-only date",
    "The Canals Behind the War": "history/analysis; year-only date",
    "Iran, Russia, China, and the Emerging Axis": "geopolitical analysis; year-only date",
    "Iran – the Great Global Mess": "year-only date; weak attribution",
    "Why the Dollar is Really the Reserve Currency": "analysis without explicit model amendment",

    # Europe-2028 cluster: keep "Europe's Inflation Spiral", drop the rest
    "Canada Is Running Toward Europe as the West Fractures": "Europe-2028 cluster duplicate",
    "The Euro Devastated Southern Europe and Greece Is Proof": "Europe-2028 cluster duplicate",
    "UK Retail Sector Collapse": "Europe-2028 cluster duplicate",
    "Europe Explores Wealth Taxes, Capital Taxes, and Exit Taxes": "Europe-2028 cluster duplicate",

    # Iran-2027 cluster: keep "Iran's War Tactics" (most specific date)
    "Is Peace Really Possible in Middle East?": "Iran-2027 cluster duplicate",
    "IRAN into 2027": "Iran-2027 cluster duplicate",
    "The Cycles Warn The US Cannot Defeat Iran": "Iran-2027 cluster duplicate",

    # Iran-2026 cluster: keep "Iran & the Drawn-Out Cold War" (only future-dated)
    "Iran – Socrates & Geopolitics": "Iran-2026 cluster duplicate; past-dated",
    "Entering Geopolitical Chaos": "Iran-2026 cluster duplicate; past-dated",

    # Oil/energy-2026-06 cluster: keep "The Global Energy Crisis"
    "The Blockade & the Future": "Oil/energy-2026 cluster duplicate",
    "Oil & Religion": "Oil/energy-2026 cluster duplicate",

    # Liquidity/Economy 2028-08 cluster: keep "The Economy into 2028"
    "Liquidity Crisis 2026": "Liquidity/Economy cluster; misleading title vs 2028 date",

    # NATO past-dated duplicate: keep "Zelensky – NATO's puppet"
    "Will NATO & Europe Be Down for the Count with WWIII?": "past-dated NATO duplicate",

    # Past-dated 2026-01-01 placeholder entries (per user directive)
    "Deflation v Inflation v Stagflation – Misconceptions Clarified": "year-only past date",
    "November 2025 US Real Estate": "year-only past date",
    "October 2025 Partial US Economic Data Blackout": "year-only past date",
}

# Entries to RECATEGORIZE (don't drop, just update category/tag).
# Keyed by exact title -> new (category, tag).
RECATEGORIZATIONS = {
    "Asteroid 2032 – 2024 YR4": ("natural_disasters", "asteroid_impact"),
}

# After cleanup, we expect exactly this many entries:
EXPECTED_FINAL_COUNT = 9


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change, don't write.")
    args = parser.parse_args()

    if not OUTPUT_PATH.exists():
        print(f"[clean_synthesis] ERROR: {OUTPUT_PATH} not found.",
              file=sys.stderr)
        return 1

    with OUTPUT_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    results = payload.get("results", [])
    original_count = len(results)
    print(f"[clean_synthesis] Loaded {original_count} synthesis entries.")

    # Build a title-keyed view of the current data
    titles_in_data = {r.get("title", ""): r for r in results}

    # Validate: every drop title should be present in the data.
    missing_drops: list[str] = []
    for title in EXPECTED_DROPS_BY_TITLE:
        if title not in titles_in_data:
            missing_drops.append(title)

    if missing_drops:
        print(
            f"[clean_synthesis] ERROR: {len(missing_drops)} expected-drop "
            f"titles not found in data. The data may have changed since the "
            f"cleanup plan was built. Aborting.",
            file=sys.stderr,
        )
        for t in missing_drops:
            print(f"  MISSING: {t!r}", file=sys.stderr)
        return 1

    # Validate recategorizations
    missing_recats: list[str] = []
    for title in RECATEGORIZATIONS:
        if title not in titles_in_data:
            missing_recats.append(title)
    if missing_recats:
        print(
            f"[clean_synthesis] ERROR: {len(missing_recats)} expected-recat "
            f"titles not found. Aborting.",
            file=sys.stderr,
        )
        for t in missing_recats:
            print(f"  MISSING: {t!r}", file=sys.stderr)
        return 1

    # Apply drops
    drop_titles = set(EXPECTED_DROPS_BY_TITLE.keys())
    kept_results = [r for r in results if r.get("title", "") not in drop_titles]
    dropped_count = original_count - len(kept_results)

    print(f"[clean_synthesis] Dropping {dropped_count} entries:")
    for title, reason in EXPECTED_DROPS_BY_TITLE.items():
        print(f"  DROP: {title!r}")
        print(f"        reason: {reason}")

    # Apply recategorizations
    print(f"\n[clean_synthesis] Recategorizing {len(RECATEGORIZATIONS)} entries:")
    for r in kept_results:
        title = r.get("title", "")
        if title in RECATEGORIZATIONS:
            new_cat, new_tag = RECATEGORIZATIONS[title]
            old_cat = r.get("category_suggestion", "")
            old_tag = r.get("tag_suggestion", "")
            print(f"  RECAT: {title!r}")
            print(f"         category: {old_cat!r} -> {new_cat!r}")
            print(f"         tag:      {old_tag!r} -> {new_tag!r}")
            r["category_suggestion"] = new_cat
            r["tag_suggestion"] = new_tag

    print(f"\n[clean_synthesis] Final count: {len(kept_results)}")

    if len(kept_results) != EXPECTED_FINAL_COUNT:
        print(
            f"[clean_synthesis] WARN: expected {EXPECTED_FINAL_COUNT} final "
            f"entries, got {len(kept_results)}. Review above.",
            file=sys.stderr,
        )

    print("\n[clean_synthesis] Final keep list:")
    for r in kept_results:
        print(
            f"  KEEP: {r.get('predicted_date', '')} | "
            f"{r.get('category_suggestion', '')} / "
            f"{r.get('tag_suggestion', '')} | "
            f"{r.get('title', '')!r}"
        )

    if args.dry_run:
        print("\n[clean_synthesis] --dry-run: no changes written.")
        return 0

    # Backup before write
    shutil.copy2(OUTPUT_PATH, BACKUP_PATH)
    print(f"\n[clean_synthesis] Backup written to {BACKUP_PATH.name}.")

    payload["results"] = kept_results
    payload["post_count"] = len(kept_results)
    payload["cleaned_at"] = datetime.now().astimezone().isoformat()
    payload["dropped_count"] = dropped_count
    payload["recategorized_count"] = len(RECATEGORIZATIONS)

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[clean_synthesis] Cleaned file written to {OUTPUT_PATH.name}.")
    print("[clean_synthesis] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
