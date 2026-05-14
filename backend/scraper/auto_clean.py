"""
auto_clean.py

Rule-based automated cleanup for synthesis_results.json. Runs in the
GitHub Actions synthesis pipeline. Unlike clean_synthesis.py (which
was a one-shot for manual curation at v1 launch), this script uses
pattern-based rules that work on any incoming new entries.

Rules applied:

  Rule 1: Drop year-only Jan 1 dates.
    Pattern: predicted_date ends in "-01-01"
    Rationale: Pass 2 Sonnet sometimes extracts "in 2028" as "2028-01-01"
    when no specific month was given. Year-only dates produce misleading
    countdowns ("23 days until Jan 1") for vague forecasts ("Europe
    depression into 2028"). Dropping them keeps the countdown card
    contract honest.

  Rule 2: Drop "Trump X" editorial title patterns.
    Pattern: title starts with "Trump " AND contains a known editorial verb
    Rationale: most "Trump X" titles are commentary, not model-attributed
    forecasts. Risk: drops legitimate Trump-related amendments, but
    those are rare.

  Rule 3: (deferred) rhetorical-question filter - too brittle.
  Rule 4: (deferred) editorial-marker filter - too brittle.

  Rule 5: Dedupe within thematic clusters.
    Pattern: multiple entries share the same predicted_date AND the same
    category_suggestion. Keep one; drop the rest.
    Keep priority: tag specificity > title length (shorter wins; "Liquidity
    Crisis 2026" is more specific than "The Economy into 2028" if both
    say the same thing - hmm, actually opposite is true. Better: just
    keep the first one encountered after sort by (wp_id) for determinism.

Auto-cleanup is conservative by design. False negatives (noise gets
through) are acceptable. False positives (legitimate forecasts dropped)
are not. If a class of garbage starts recurring, add a rule.

Usage:
    python auto_clean.py            # apply and write
    python auto_clean.py --dry-run  # show what would change

Reads/writes:
    backend/output/synthesis_results.json (in place)
Writes backup:
    backend/output/synthesis_results.before_autoclean.json (only on
    actual writes when something changed)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "synthesis_results.json"
BACKUP_PATH = SCRIPT_DIR.parent / "output" / "synthesis_results.before_autoclean.json"

# Rule 2 editorial verbs. If title starts with "Trump " AND contains one
# of these, we drop it.
TRUMP_EDITORIAL_VERBS = (
    "Invades",
    "Backs Down",
    "Considers",
    "Using",
    "Tries to",
    "to End",
    "Withdraws",
    "Will Declare",
    "When Will",
    "Backs Off",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change; don't write.")
    args = parser.parse_args()

    if not OUTPUT_PATH.exists():
        print(f"[auto_clean] ERROR: {OUTPUT_PATH} not found.",
              file=sys.stderr)
        return 1

    with OUTPUT_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    results = payload.get("results", [])
    original_count = len(results)
    print(f"[auto_clean] Loaded {original_count} synthesis entries.")

    if original_count == 0:
        print("[auto_clean] Nothing to do.")
        return 0

    # Apply rules in order.
    after_rule1 = _apply_rule1_year_only(results)
    after_rule2 = _apply_rule2_trump_editorial(after_rule1)
    after_rule5 = _apply_rule5_dedupe(after_rule2)

    final_count = len(after_rule5)
    dropped_count = original_count - final_count

    print(f"[auto_clean] Final count: {final_count} (dropped {dropped_count})")

    if args.dry_run:
        print("\n[auto_clean] --dry-run: no changes written.")
        return 0

    if dropped_count == 0:
        print("[auto_clean] Nothing dropped; no write needed.")
        return 0

    # Backup before write
    shutil.copy2(OUTPUT_PATH, BACKUP_PATH)
    print(f"[auto_clean] Backup written to {BACKUP_PATH.name}.")

    payload["results"] = after_rule5
    payload["post_count"] = final_count
    payload["auto_cleaned_at"] = datetime.now().astimezone().isoformat()
    payload["auto_clean_dropped"] = dropped_count

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[auto_clean] Wrote cleaned file with {final_count} entries.")
    return 0


def _apply_rule1_year_only(entries: list[dict]) -> list[dict]:
    """Drop entries with predicted_date ending in '-01-01' (year-only flat)."""
    kept = []
    dropped = []
    for e in entries:
        date_str = e.get("predicted_date") or ""
        if date_str.endswith("-01-01"):
            dropped.append(e)
        else:
            kept.append(e)
    if dropped:
        print(f"[auto_clean] Rule 1 (year-only): dropped {len(dropped)} entries")
        for e in dropped:
            print(f"    DROP: {e.get('predicted_date')} | {e.get('title')!r}")
    else:
        print(f"[auto_clean] Rule 1 (year-only): no drops")
    return kept


def _apply_rule2_trump_editorial(entries: list[dict]) -> list[dict]:
    """Drop entries with 'Trump X' editorial title pattern."""
    kept = []
    dropped = []
    for e in entries:
        title = e.get("title", "")
        if title.startswith("Trump ") and any(v in title for v in TRUMP_EDITORIAL_VERBS):
            dropped.append(e)
        else:
            kept.append(e)
    if dropped:
        print(f"[auto_clean] Rule 2 (Trump editorial): dropped {len(dropped)} entries")
        for e in dropped:
            print(f"    DROP: {e.get('title')!r}")
    else:
        print(f"[auto_clean] Rule 2 (Trump editorial): no drops")
    return kept


def _apply_rule5_dedupe(entries: list[dict]) -> list[dict]:
    """
    For entries with same (predicted_date, category_suggestion), keep one.
    Priority: lowest wp_id wins (deterministic; assumes lower wp_ids are
    earlier posts, which usually means original announcement vs commentary).
    """
    # Group by (date, category).
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for e in entries:
        key = (e.get("predicted_date"), e.get("category_suggestion"))
        groups[key].append(e)

    kept: list[dict] = []
    dropped: list[dict] = []
    for key, group in groups.items():
        if len(group) == 1:
            kept.append(group[0])
            continue
        # Multiple entries on same date+category. Keep the one with
        # lowest wp_id (first written).
        sorted_group = sorted(group, key=lambda e: e.get("wp_id", 0))
        kept.append(sorted_group[0])
        for dup in sorted_group[1:]:
            dropped.append(dup)

    # Restore original order among kept entries.
    kept_ids = {e.get("wp_id") for e in kept}
    ordered_kept = [e for e in entries if e.get("wp_id") in kept_ids]

    if dropped:
        print(f"[auto_clean] Rule 5 (dedup): dropped {len(dropped)} duplicates")
        for e in dropped:
            print(
                f"    DROP: {e.get('predicted_date')} | "
                f"{e.get('category_suggestion')} | {e.get('title')!r}"
            )
    else:
        print(f"[auto_clean] Rule 5 (dedup): no duplicates")
    return ordered_kept


if __name__ == "__main__":
    sys.exit(main())
