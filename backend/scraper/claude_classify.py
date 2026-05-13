"""
claude_classify.py

PASS 1 of the synthesis pipeline. Reads the raw archive produced by
wp_backfill.py, sends each post to Claude Haiku in batches, and
classifies each as ECM forecast vs everything else. Extracts a
predicted date for posts classified as ECM forecasts.

Usage:
    python claude_classify.py                # full run (all posts)
    python claude_classify.py --limit 5      # test run on first 5 posts
    python claude_classify.py --limit 10     # calibration batch

Reads:
    backend/output/armstrong_raw_archive.json

Writes:
    backend/output/classification_results.json

Environment:
    ANTHROPIC_API_KEY (required)

The classification prompt is STRICT: only posts referencing Armstrong's
Economic Confidence Model (ECM) or its associated computer/Socrates
model that PREDICT A SPECIFIC FUTURE EVENT ON A SPECIFIC FUTURE DATE
are classified as forecasts. Everything else - general commentary,
historical analysis, news, opinion, Q&A, market roundups, ECM model
references without specific predictions - is classified as commentary.

We send the full post body so Claude can catch forecasts where the
key timing reveal lives in middle or final paragraphs (a common
pattern in Armstrong's writing).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic, APIError, BadRequestError

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_PATH = SCRIPT_DIR.parent / "output" / "armstrong_raw_archive.json"
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "classification_results.json"

MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 5
MAX_TOKENS_PER_CALL = 2000
INTER_CALL_DELAY_SECS = 0.5

# Truncate post body to this many chars before sending. Armstrong
# posts run 2-5k chars. 8000 chars (~2000 tokens) catches the whole
# body for most posts; for very long posts, the most useful timing
# context is usually in the first 8k anyway.
MAX_POST_CHARS = 8000


SYSTEM_PROMPT = """You are classifying blog posts from Armstrong Economics for an ECM forecast tracker app.

CONTEXT:
Martin Armstrong's Economic Confidence Model (ECM) is a 8.6-year cycle model that predicts specific turning points on specific future dates. His proprietary computer system (also called "Socrates" or "the computer") generates dated forecasts for political, economic, geopolitical, and social events. The app exists to track these specific ECM-derived predictions.

Your task: for each post, decide if it is an ECM FORECAST or COMMENTARY.

DEFINITION OF AN ECM FORECAST (STRICT - must meet ALL THREE):
  1. The post references Armstrong's ECM, computer model, Socrates, "the array", "the model", or "panic cycle" (or strongly implies these by discussing Armstrong's dated predictions)
  2. The post predicts a SPECIFIC EVENT OR TURNING POINT (a concrete outcome, not just "trends will continue")
  3. The prediction is tied to a SPECIFIC FUTURE DATE, MONTH, QUARTER, OR YEAR (after today)

EVERYTHING ELSE is COMMENTARY:
  - General analysis of current events
  - Historical commentary or context
  - News reporting
  - Opinion pieces without ECM-dated predictions
  - Daily market roundups (e.g. "Market Talk - May 12")
  - Q&A posts answering reader questions
  - Promotional posts (live events, tickets, video updates)
  - Private blog teasers
  - Posts that mention dates as context ("by 2030 the trend will continue") without predicting a specific event
  - Posts that reference the ECM model in passing without making a specific dated prediction in THIS post

CRITICAL DISTINCTIONS:
  - "Europe will enter depression by 2028" + ECM reference + specific predicted event = FORECAST
  - "Europe will enter depression by 2028" without ECM reference, just opinion = COMMENTARY
  - "The 2026 ECM panic point in May was correct as we now see..." (about a PAST date) = COMMENTARY
  - "The computer is showing a major turning point on October 1, 2027 in geopolitics" = FORECAST
  - "We are seeing the effects of the May 2024 panic cycle now" (past date) = COMMENTARY
  - "The next major ECM date is November 2026 where we expect..." = FORECAST
  - "Armstrong on USA Watchdog" (media appearance post) = COMMENTARY
  - "Watch Martin Armstrong LIVE" (promotional) = COMMENTARY

IMPORTANT:
  - The forecast timing often appears in MIDDLE OR FINAL paragraphs. Read the entire post body.
  - Be STRICT. When in doubt, classify as COMMENTARY. Better to drop a borderline forecast than include commentary in the feed.
  - The presence of an ECM date in the post but referring to a PAST event = COMMENTARY (the date has already happened).

For each post, also extract:
  - predicted_date: ISO 8601 (YYYY-MM-DD). If only month/quarter/year, use first day of that period (e.g. "Q3 2026" -> "2026-07-01", "August 2026" -> "2026-08-01", "2027" -> "2027-01-01"). Null if not a forecast.
  - confidence: "high" if both ECM reference AND specific dated prediction are explicit, "medium" if one is explicit and the other implied, "low" if you are uncertain.

OUTPUT FORMAT:
Respond with ONLY a JSON array, one object per post, in the SAME ORDER as input. No prose before or after. Each object MUST have exactly these keys:
  - wp_id (integer): match the input
  - is_forecast (boolean)
  - confidence ("high" | "medium" | "low")
  - predicted_date (string YYYY-MM-DD or null)
  - reason (string, max 1 sentence, must cite the ECM/computer/Socrates reference AND the specific predicted event AND the future date if is_forecast=true)
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Classify only the first N posts (for testing). 0 = all.",
    )
    parser.add_argument(
        "--start", type=int, default=0,
        help="Skip the first N posts (for sampling different ranges).",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "[claude_classify] ERROR: set ANTHROPIC_API_KEY in environment.",
            file=sys.stderr,
        )
        return 1

    if not INPUT_PATH.exists():
        print(
            f"[claude_classify] ERROR: {INPUT_PATH} not found. "
            f"Run wp_backfill.py first.",
            file=sys.stderr,
        )
        return 1

    with INPUT_PATH.open("r", encoding="utf-8") as f:
        archive = json.load(f)

    all_posts = archive.get("posts", [])
    print(f"[claude_classify] Archive has {len(all_posts)} posts total.")

    posts = all_posts[args.start:]
    if args.limit > 0:
        posts = posts[: args.limit]

    print(f"[claude_classify] Classifying {len(posts)} posts (start={args.start}, limit={args.limit or 'none'}).")

    client = Anthropic(api_key=api_key)

    all_results: list[dict] = []
    total_input_tokens = 0
    total_output_tokens = 0

    batches = list(_chunked(posts, BATCH_SIZE))
    print(f"[claude_classify] {len(batches)} batches of up to {BATCH_SIZE} posts.")

    for batch_idx, batch in enumerate(batches, start=1):
        print(
            f"[claude_classify] Batch {batch_idx}/{len(batches)} "
            f"({len(batch)} posts)..."
        )
        try:
            batch_results, usage = _classify_batch(client, batch)
        except Exception as e:
            print(
                f"[claude_classify] ERROR on batch {batch_idx}: {e}",
                file=sys.stderr,
            )
            print(
                f"[claude_classify] Saving partial results "
                f"({len(all_results)} posts done)...",
                file=sys.stderr,
            )
            _write_results(all_results, partial=True)
            return 1

        all_results.extend(batch_results)
        total_input_tokens += usage["input"]
        total_output_tokens += usage["output"]

        kept = sum(1 for r in batch_results if r.get("is_forecast"))
        print(
            f"[claude_classify] Batch {batch_idx}: kept {kept}/{len(batch)} "
            f"(in_tok={usage['input']}, out_tok={usage['output']})"
        )

        if batch_idx < len(batches):
            time.sleep(INTER_CALL_DELAY_SECS)

    # Haiku pricing as of writing: input $1/M, output $5/M.
    est_cost = (total_input_tokens * 1.0 / 1_000_000) + (total_output_tokens * 5.0 / 1_000_000)

    total_kept = sum(1 for r in all_results if r.get("is_forecast"))
    print(
        f"\n[claude_classify] Done. {total_kept}/{len(all_results)} "
        f"classified as forecasts ({100*total_kept//max(len(all_results),1)}%)."
    )
    print(
        f"[claude_classify] Tokens: in={total_input_tokens}, out={total_output_tokens}. "
        f"Estimated cost: ${est_cost:.4f}"
    )

    _write_results(all_results, partial=False, usage={
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "estimated_cost_usd": est_cost,
        "model": MODEL,
    })
    print(f"[claude_classify] Wrote {OUTPUT_PATH}")
    return 0


def _classify_batch(client: Anthropic, batch: list[dict]) -> tuple[list[dict], dict]:
    posts_payload = []
    for p in batch:
        body = _strip_html(p.get("content_html", ""))[:MAX_POST_CHARS]
        posts_payload.append({
            "wp_id": p["wp_id"],
            "title": _strip_html(p.get("title", "")),
            "date_published": p.get("date_published", ""),
            "body": body,
        })

    user_message = (
        "Classify each of the following Armstrong Economics posts as an "
        "ECM FORECAST or COMMENTARY. Today's date is "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}. "
        "BE STRICT - when in doubt, classify as COMMENTARY.\n\n"
        f"POSTS:\n{json.dumps(posts_payload, ensure_ascii=False, indent=2)}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_PER_CALL,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    parsed = _parse_classification_response(raw_text, batch)

    return parsed, {
        "input": response.usage.input_tokens,
        "output": response.usage.output_tokens,
    }


def _parse_classification_response(raw_text: str, batch: list[dict]) -> list[dict]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse Claude response as JSON: {e}\n"
            f"First 500 chars of response: {cleaned[:500]}"
        )

    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")

    if len(parsed) != len(batch):
        raise ValueError(f"Expected {len(batch)} results, got {len(parsed)}")

    validated: list[dict] = []
    for i, (input_post, result) in enumerate(zip(batch, parsed)):
        if not isinstance(result, dict):
            raise ValueError(f"Result {i} is not an object: {result}")
        for required_key in ("wp_id", "is_forecast", "confidence", "predicted_date", "reason"):
            if required_key not in result:
                raise ValueError(
                    f"Result {i} missing required key '{required_key}': {result}"
                )
        if result["wp_id"] != input_post["wp_id"]:
            raise ValueError(
                f"Result {i} wp_id mismatch: expected "
                f"{input_post['wp_id']}, got {result['wp_id']}"
            )
        validated.append({
            "wp_id": int(result["wp_id"]),
            "title": _strip_html(input_post.get("title", "")),
            "link": input_post.get("link", ""),
            "is_forecast": bool(result["is_forecast"]),
            "confidence": str(result["confidence"]),
            "predicted_date": result["predicted_date"],
            "reason": str(result["reason"]),
        })

    return validated


def _write_results(
    results: list[dict],
    *,
    partial: bool = False,
    usage: dict | None = None,
) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "partial": partial,
        "model": MODEL,
        "post_count": len(results),
        "kept_count": sum(1 for r in results if r.get("is_forecast")),
        "usage": usage,
        "results": results,
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(s: str) -> str:
    if not s:
        return ""
    cleaned = _HTML_TAG_RE.sub("", s)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def _chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


if __name__ == "__main__":
    sys.exit(main())
