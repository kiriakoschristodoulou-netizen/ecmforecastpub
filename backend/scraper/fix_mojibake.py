"""
fix_mojibake.py

ONE-SHOT script. Reads armstrong_raw_archive.json, applies ftfy to clean
mojibake from titles and content_html, writes the cleaned file back.

Mojibake examples ftfy fixes:
  â€™  -> '   (right single quotation mark / apostrophe)
  â€"  -> -   (en/em dash)
  â€œ  -> "   (left double quotation mark)
  â€   -> "   (right double quotation mark)
  â€¦  -> ... (horizontal ellipsis)
  Â£   -> £   (pound sterling)
  Ã©   -> é   (e acute)

Plus it strips known RSS truncation markers like [â€¦] and [...] before
ftfy runs, so they don't reappear post-decode.

Also fixes HTML entities like &#8217; (curly apostrophe), &#038; (ampersand),
&#8211; (en-dash), etc.

Detection strategy: compare the cleaned string to the original. If different,
something changed. We don't rely on heuristic indicator lists (the v1 of this
script did and undercounted real mojibake).

Usage:
    python fix_mojibake.py            # apply in place (writes backup first)
    python fix_mojibake.py --dry-run  # show what would change, no write
    python fix_mojibake.py --check    # exit 1 if any changes needed, 0 otherwise

Reads/writes:
    backend/output/armstrong_raw_archive.json
Writes backup:
    backend/output/armstrong_raw_archive.before_ftfy.json
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import ftfy

SCRIPT_DIR = Path(__file__).resolve().parent
ARCHIVE_PATH = SCRIPT_DIR.parent / "output" / "armstrong_raw_archive.json"
BACKUP_PATH = SCRIPT_DIR.parent / "output" / "armstrong_raw_archive.before_ftfy.json"

# Regex for RSS truncation markers, applied BEFORE ftfy so the markers
# don't survive into the cleaned text.
_TRUNCATION_RE = re.compile(r"\[\s*(?:â€¦|…|\.\.\.)\s*\]")


def clean_string(s: str) -> str:
    """Apply the full cleaning pipeline to one string."""
    if not s:
        return s
    # 1. Strip [...] truncation markers (any form)
    s = _TRUNCATION_RE.sub("", s)
    # 2. Decode HTML entities (&#8217; -> ', &#038; -> &, etc.)
    s = html.unescape(s)
    # 3. Apply ftfy to fix encoding mojibake
    s = ftfy.fix_text(s)
    return s


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show summary, don't write changes.")
    parser.add_argument("--check", action="store_true",
                        help="Exit 1 if any changes needed, 0 otherwise.")
    args = parser.parse_args()

    if not ARCHIVE_PATH.exists():
        print(f"[fix_mojibake] ERROR: {ARCHIVE_PATH} not found.",
              file=sys.stderr)
        return 1

    with ARCHIVE_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    posts = payload.get("posts", [])
    print(f"[fix_mojibake] Loaded {len(posts)} posts from archive.")

    posts_changed = 0
    titles_changed = 0
    bodies_changed = 0
    examples: list[tuple[str, str]] = []

    for post in posts:
        post_dirty = False

        for field in ("title", "content_html"):
            original = post.get(field, "")
            if not original:
                continue
            cleaned = clean_string(original)
            if cleaned != original:
                post_dirty = True
                if field == "title":
                    titles_changed += 1
                else:
                    bodies_changed += 1
                if len(examples) < 3 and field == "content_html":
                    # Find a substring where they differ for the example.
                    idx = next(
                        (i for i in range(min(len(original), len(cleaned)))
                         if original[i] != cleaned[i]),
                        0
                    )
                    start = max(0, idx - 40)
                    end_o = min(len(original), idx + 80)
                    end_c = min(len(cleaned), idx + 80)
                    examples.append((original[start:end_o], cleaned[start:end_c]))
                if not args.dry_run and not args.check:
                    post[field] = cleaned

        if post_dirty:
            posts_changed += 1

    print(f"[fix_mojibake] Titles changed: {titles_changed}/{len(posts)}")
    print(f"[fix_mojibake] Bodies changed: {bodies_changed}/{len(posts)}")
    print(f"[fix_mojibake] Posts changed (any field): {posts_changed}/{len(posts)}")

    if examples:
        print("\n[fix_mojibake] Examples (excerpt around first difference):")
        for i, (orig, clean) in enumerate(examples, start=1):
            print(f"  Example {i}:")
            print(f"    BEFORE: {orig!r}")
            print(f"    AFTER:  {clean!r}")
            print()

    if args.check:
        return 1 if posts_changed > 0 else 0

    if args.dry_run:
        print("[fix_mojibake] --dry-run: no changes written.")
        return 0

    if posts_changed == 0:
        print("[fix_mojibake] Nothing to change; not writing.")
        return 0

    # Real write: backup first.
    shutil.copy2(ARCHIVE_PATH, BACKUP_PATH)
    print(f"[fix_mojibake] Backup written to {BACKUP_PATH.name}.")

    payload["mojibake_fixed_at"] = datetime.now().astimezone().isoformat()

    with ARCHIVE_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[fix_mojibake] Cleaned archive written to {ARCHIVE_PATH.name}.")
    print(f"[fix_mojibake] Done.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
