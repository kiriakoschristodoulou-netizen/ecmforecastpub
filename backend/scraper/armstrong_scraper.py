"""
armstrong_scraper.py

Fetches the public Armstrong Economics RSS feed and parses each item
into a raw forecast dict. This is the LOW-LEVEL scraper layer - it
returns minimally-processed dicts. The build_public_feed.py
orchestrator handles importance scoring, ID generation, and writing
the final events.json.

This module is intentionally dumb: fetch, parse, return. No Claude,
no rules, no scheduled-event attachment.

Design notes:
  - Armstrong's RSS feed appears to be at the standard WordPress
    /feed/ URL. If it moves, RSS_URL below is the single change point.
  - Not every Armstrong blog post is a "forecast" in our app's sense.
    Many are commentary or news. We filter (best-effort) for posts
    that mention dates in their title or summary - these are the ones
    most likely to be forecasts pointing at a future event.
  - We DO NOT try to extract the forecast date from the post text
    here. Date extraction is fragile and belongs in a dedicated
    parser. For 8a, raw items are returned with the publication date;
    8b or 8c will add forecast-date extraction via Claude.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import feedparser  # type: ignore
import requests
from dateutil import parser as date_parser

RSS_URL = "https://www.armstrongeconomics.com/feed/"

# Polite UA so we identify ourselves rather than looking like a bot.
USER_AGENT = (
    "ecmforecastpub/1.0 (+https://github.com/"
    "kiriakoschristodoulou-netizen/ecmforecastpub)"
)

FETCH_TIMEOUT_SECS = 15


@dataclass(frozen=True)
class ArmstrongPost:
    """One raw Armstrong RSS item, minimally parsed."""

    guid: str  # stable identifier from RSS
    title: str  # post title
    summary: str  # post description (may be HTML)
    url: str  # link to full post
    published_at: str  # ISO 8601 string; the RSS pubDate

    def to_dict(self) -> dict:
        return {
            "guid": self.guid,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "published_at": self.published_at,
        }


class ArmstrongFetchError(Exception):
    """Raised when the RSS feed can't be fetched or parsed."""


def fetch_armstrong_rss(
    rss_url: str = RSS_URL,
    *,
    timeout_secs: int = FETCH_TIMEOUT_SECS,
) -> list[ArmstrongPost]:
    """
    Fetch the Armstrong public RSS feed and return parsed items.

    Returns posts in feed order (typically newest first). The caller
    is responsible for any further filtering or transformation.

    Raises ArmstrongFetchError on network or parse failure. Empty
    feeds return an empty list (not an error).
    """
    try:
        response = requests.get(
            rss_url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml"},
            timeout=timeout_secs,
        )
    except requests.RequestException as e:
        raise ArmstrongFetchError(f"Network error fetching {rss_url}: {e}") from e

    if response.status_code != 200:
        raise ArmstrongFetchError(
            f"Armstrong RSS returned HTTP {response.status_code}"
        )

    # feedparser is tolerant - it will parse most reasonable RSS/Atom.
    response.encoding = 'utf-8'
    feed = feedparser.parse(response.text.encode('utf-8'))

    if feed.bozo and not feed.entries:
        # Bozo means feedparser flagged something malformed. We only
        # treat it as fatal when no entries came through.
        raise ArmstrongFetchError(
            f"Feedparser rejected the feed: {feed.bozo_exception}"
        )

    posts: list[ArmstrongPost] = []
    for entry in feed.entries:
        guid = _safe_str(entry.get("id") or entry.get("guid") or entry.get("link"))
        title = _safe_str(entry.get("title")).strip()
        summary = _safe_str(entry.get("summary") or entry.get("description"))
        url = _safe_str(entry.get("link"))

        # pubDate parsing - feedparser exposes a parsed struct_time,
        # but dateutil handles RFC822/ISO/varies in the wild.
        raw_date = entry.get("published") or entry.get("updated") or ""
        published_iso = _iso_or_empty(raw_date)

        if not guid or not title or not url:
            # Skip entries that lack the basic identifying fields.
            continue

        posts.append(
            ArmstrongPost(
                guid=guid,
                title=title,
                summary=summary,
                url=url,
                published_at=published_iso,
            )
        )

    return posts


def filter_forecast_candidates(
    posts: Iterable[ArmstrongPost],
) -> list[ArmstrongPost]:
    """
    Best-effort filter for posts that look like forecasts (i.e. point
    at a future event) rather than commentary/news.

    Heuristic: title or summary mentions an explicit time reference
    (month name, year, or quarter). This is INTENTIONALLY loose; the
    Claude synthesis layer in 8b will do real forecast/non-forecast
    classification with much higher accuracy. Here we just trim the
    noise so the synthesis layer has less to chew through.

    Returns posts in original order.
    """
    # Lowercase title+summary, scan for date-ish substrings.
    keywords = (
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        " 2026", " 2027", " 2028", " 2029", " 2030",
        "q1", "q2", "q3", "q4",
        "next week", "next month", "next year",
    )

    out: list[ArmstrongPost] = []
    for post in posts:
        haystack = f"{post.title} {post.summary}".lower()
        if any(k in haystack for k in keywords):
            out.append(post)
    return out


# --- helpers -----------------------------------------------------------------

def _safe_str(v) -> str:
    if v is None:
        return ""
    return str(v)


def _iso_or_empty(raw: str) -> str:
    if not raw:
        return ""
    try:
        dt = date_parser.parse(raw)
        # Normalize to ISO 8601 with timezone info preserved.
        return dt.isoformat()
    except (ValueError, TypeError):
        return ""
