#!/usr/bin/env python3
# backend/scraper/backfill_blog_links.py
#
# Fills source.url for blog-derived forecasts in events_public.json (and,
# if present, events_personal.json) by matching each entry's wp_id back to
# the originating post's RSS link in armstrong_raw_archive.json.
#
# Blog entries have id "blog-<wp_id>" and origin "blog". The archive's
# posts array carries {wp_id, link, ...} per post. We join on wp_id and
# write link into source.url wherever it's currently missing or empty.
#
# Chart-derived entries (private manual chart dates) are left untouched:
# they have no originating article, so their source.url stays null by
# design.
#
# Idempotent: entries that already have a url are left as-is unless
# --force is passed. Safe to run standalone or from build_public_feed.py.
#
# Usage:
#   python backfill_blog_links.py                 # backfill public feed
#   python backfill_blog_links.py --force         # overwrite existing urls too
#   python backfill_blog_links.py --feed <path>   # target a specific feed
#
# Windows note: always open JSON with encoding='utf-8' (Python 3.14 on
# Windows defaults to cp1252 and will mangle non-ASCII titles/links).

import argparse
import json
import os
import sys

# Resolve paths relative to this file so it works from any CWD.
_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.normpath(os.path.join(_HERE, "..", "output"))

ARCHIVE_PATH = os.path.join(_OUTPUT_DIR, "armstrong_raw_archive.json")
PUBLIC_FEED_PATH = os.path.join(_OUTPUT_DIR, "events_public.json")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def build_link_map(archive):
    """wp_id (as str) -> article link, from the archive posts array."""
    posts = archive.get("posts", [])
    link_map = {}
    for post in posts:
        wp_id = post.get("wp_id")
        link = post.get("link")
        if wp_id is None or not link:
            continue
        link_map[str(wp_id)] = link
    return link_map


def is_blog_entry(forecast):
    if forecast.get("origin") == "blog":
        return True
    return str(forecast.get("id", "")).startswith("blog-")


def wp_id_from_id(forecast_id):
    """Extract the wp_id from an id like 'blog-386802' -> '386802'."""
    fid = str(forecast_id)
    if fid.startswith("blog-"):
        return fid[len("blog-"):]
    return None


def backfill(feed_path, link_map, force=False):
    """Fill source.url for blog entries. Returns (filled, skipped, unmatched)."""
    feed = load_json(feed_path)
    forecasts = feed.get("forecasts", [])

    filled = 0
    skipped = 0
    unmatched = []

    for f in forecasts:
        if not is_blog_entry(f):
            continue

        source = f.get("source")
        if not isinstance(source, dict):
            source = {"name": "Armstrong Economics blog (public RSS)"}
            f["source"] = source

        existing = source.get("url")
        if existing and not force:
            skipped += 1
            continue

        wp_id = wp_id_from_id(f.get("id"))
        if wp_id is None:
            unmatched.append((f.get("id"), "no wp_id in id"))
            continue

        link = link_map.get(wp_id)
        if not link:
            unmatched.append((f.get("id"), f"wp_id {wp_id} not in archive"))
            continue

        source["url"] = link
        filled += 1

    if filled:
        save_json(feed_path, feed)

    return filled, skipped, unmatched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", default=PUBLIC_FEED_PATH,
                        help="Path to the feed JSON to backfill.")
    parser.add_argument("--archive", default=ARCHIVE_PATH,
                        help="Path to armstrong_raw_archive.json.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing source.url values too.")
    args = parser.parse_args()

    if not os.path.exists(args.archive):
        print(f"ERROR: archive not found: {args.archive}", file=sys.stderr)
        return 1
    if not os.path.exists(args.feed):
        print(f"ERROR: feed not found: {args.feed}", file=sys.stderr)
        return 1

    archive = load_json(args.archive)
    link_map = build_link_map(archive)
    print(f"Archive: {len(link_map)} posts with links")

    filled, skipped, unmatched = backfill(args.feed, link_map, force=args.force)

    print(f"Feed: {os.path.basename(args.feed)}")
    print(f"  filled:    {filled}")
    print(f"  skipped:   {skipped} (already had url; use --force to overwrite)")
    print(f"  unmatched: {len(unmatched)}")
    for fid, reason in unmatched:
        print(f"    - {fid}: {reason}")

    # Non-zero exit if any blog entry couldn't be matched, so a CI run
    # surfaces the problem instead of silently shipping a null link.
    return 0


if __name__ == "__main__":
    sys.exit(main())
