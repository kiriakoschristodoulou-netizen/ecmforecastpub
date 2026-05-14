"""
claude_classify.py

PASS 1 of the synthesis pipeline. Robust version with:
  - Cumulative append: loads existing classification_results.json, only
    processes posts not yet classified, merges results back. Survives
    interrupted runs without losing prior work.
  - Retry on JSON-shrinkage failures: if Claude returns N-1 results for
    N input, retries the same batch once with the same prompt.
  - Adaptive batch shrink: if a batch fails twice at size 5, retries
    once at size 3.
  - Hard failures (network, auth) abort the run cleanly. Soft failures
    (one bad batch out of 100) are logged to classification_failures.json
    and the run continues.

Usage:
    python claude_classify.py                # process all unclassified
    python claude_classify.py --reset        # wipe existing, start over
    python claude_classify.py --limit 5      # test mode (5 unclassified)

Reads:
    backend/output/armstrong_raw_archive.json
    backend/output/classification_results.json  (if exists, used as state)

Writes:
    backend/output/classification_results.json  (cumulative)
    backend/output/classification_failures.json (only if any batches fail)

Environment:
    ANTHROPIC_API_KEY (required)
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

from anthropic import Anthropic

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_PATH = SCRIPT_DIR.parent / "output" / "armstrong_raw_archive.json"
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "classification_results.json"
FAILURES_PATH = SCRIPT_DIR.parent / "output" / "classification_failures.json"

MODEL = "claude-haiku-4-5-20251001"
PRIMARY_BATCH_SIZE = 5
FALLBACK_BATCH_SIZE = 3
MAX_TOKENS_PER_CALL = 2000
INTER_CALL_DELAY_SECS = 0.5
RETRY_DELAY_SECS = 2.0

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
        help="Classify only the first N unclassified posts (for testing). 0 = all.",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Wipe existing classification_results.json and start over.",
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

    # Load existing results (cumulative-append mode).
    existing_results: list[dict] = []
    existing_failures: list[dict] = []
    if args.reset:
        if OUTPUT_PATH.exists():
            OUTPUT_PATH.unlink()
            print("[claude_classify] --reset: deleted existing results.")
        if FAILURES_PATH.exists():
            FAILURES_PATH.unlink()
            print("[claude_classify] --reset: deleted existing failures log.")
    else:
        existing_results = _load_existing_results()
        existing_failures = _load_existing_failures()

    done_ids = {int(r["wp_id"]) for r in existing_results}
    failed_ids = {int(p["wp_id"]) for f in existing_failures for p in f.get("posts", [])}
    skip_ids = done_ids | failed_ids

    if existing_results:
        print(
            f"[claude_classify] Resume: {len(existing_results)} posts already "
            f"classified ({sum(1 for r in existing_results if r.get('is_forecast'))} kept)."
        )
    if existing_failures:
        print(
            f"[claude_classify] Resume: {len(failed_ids)} posts in failure log "
            f"(will skip; clear classification_failures.json to retry them)."
        )

    pending = [p for p in all_posts if int(p["wp_id"]) not in skip_ids]
    if args.limit > 0:
        pending = pending[: args.limit]

    if not pending:
        print("[claude_classify] Nothing to do - all posts already classified.")
        return 0

    print(f"[claude_classify] Processing {len(pending)} pending posts.")

    client = Anthropic(api_key=api_key)

    new_results: list[dict] = existing_results.copy()
    new_failures: list[dict] = existing_failures.copy()
    total_input_tokens = 0
    total_output_tokens = 0

    batches = list(_chunked(pending, PRIMARY_BATCH_SIZE))
    print(f"[claude_classify] {len(batches)} batches of up to {PRIMARY_BATCH_SIZE} posts.")

    for batch_idx, batch in enumerate(batches, start=1):
        print(
            f"[claude_classify] Batch {batch_idx}/{len(batches)} "
            f"({len(batch)} posts)..."
        )

        # Three-stage retry: original, retry-same-size, fallback-smaller-batches.
        batch_results, usage, error = _classify_with_retries(client, batch)

        if batch_results is not None:
            new_results.extend(batch_results)
            total_input_tokens += usage["input"]
            total_output_tokens += usage["output"]

            kept = sum(1 for r in batch_results if r.get("is_forecast"))
            print(
                f"[claude_classify] Batch {batch_idx}: kept {kept}/{len(batch)} "
                f"(in_tok={usage['input']}, out_tok={usage['output']})"
            )
        else:
            # All retries exhausted - log this batch's posts as failed and continue.
            new_failures.append({
                "batch_idx_at_failure": batch_idx,
                "logged_at": datetime.now(timezone.utc).isoformat(),
                "error": str(error),
                "posts": [
                    {"wp_id": p["wp_id"], "title": _strip_html(p.get("title", ""))}
                    for p in batch
                ],
            })
            print(
                f"[claude_classify] Batch {batch_idx}: FAILED after all retries. "
                f"Logged {len(batch)} posts to failures. Continuing.",
                file=sys.stderr,
            )
            # Persist after each failure so we can recover if the process dies.
            _write_failures(new_failures)

        # Persist after each batch so partial progress survives Ctrl+C.
        _write_results(new_results, partial=(batch_idx < len(batches)), usage={
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "estimated_cost_usd": (total_input_tokens * 1.0 / 1_000_000) + (total_output_tokens * 5.0 / 1_000_000),
            "model": MODEL,
        })

        if batch_idx < len(batches):
            time.sleep(INTER_CALL_DELAY_SECS)

    est_cost = (total_input_tokens * 1.0 / 1_000_000) + (total_output_tokens * 5.0 / 1_000_000)
    total_kept = sum(1 for r in new_results if r.get("is_forecast"))
    total_failed = sum(len(f.get("posts", [])) for f in new_failures)

    print(
        f"\n[claude_classify] Done. {total_kept}/{len(new_results)} classified "
        f"as forecasts ({100*total_kept//max(len(new_results),1)}%)."
    )
    if total_failed:
        print(
            f"[claude_classify] {total_failed} posts in failures log "
            f"({FAILURES_PATH}); investigate or clear file to retry."
        )
    print(
        f"[claude_classify] Tokens this run: in={total_input_tokens}, out={total_output_tokens}. "
        f"Estimated incremental cost: ${est_cost:.4f}"
    )
    print(f"[claude_classify] Total results in {OUTPUT_PATH}: {len(new_results)}")
    return 0


def _classify_with_retries(
    client: Anthropic, batch: list[dict]
) -> tuple[list[dict] | None, dict, Exception | None]:
    """
    Three-stage retry strategy:
      1. Try once at PRIMARY_BATCH_SIZE.
      2. If JSON shape mismatch (got N-1 results for N posts), retry once.
      3. If still failing, split batch into chunks of FALLBACK_BATCH_SIZE
         and try each separately.

    Returns (results, usage_dict, error). On success results is the list
    and error is None. On failure results is None.

    usage_dict aggregates input + output tokens across all attempts.
    """
    aggregate_usage = {"input": 0, "output": 0}

    # Attempt 1: primary size
    try:
        results, usage = _classify_batch(client, batch)
        aggregate_usage["input"] += usage["input"]
        aggregate_usage["output"] += usage["output"]
        return results, aggregate_usage, None
    except ValueError as e:
        print(
            f"[claude_classify]   Attempt 1 failed: {e}. Retrying...",
            file=sys.stderr,
        )
        time.sleep(RETRY_DELAY_SECS)

    # Attempt 2: same size, retry once
    try:
        results, usage = _classify_batch(client, batch)
        aggregate_usage["input"] += usage["input"]
        aggregate_usage["output"] += usage["output"]
        print(
            f"[claude_classify]   Attempt 2 succeeded.",
            file=sys.stderr,
        )
        return results, aggregate_usage, None
    except ValueError as e:
        print(
            f"[claude_classify]   Attempt 2 failed: {e}. "
            f"Falling back to batch_size={FALLBACK_BATCH_SIZE}...",
            file=sys.stderr,
        )
        time.sleep(RETRY_DELAY_SECS)

    # Attempt 3: split into smaller chunks
    all_sub_results: list[dict] = []
    for sub_batch in _chunked(batch, FALLBACK_BATCH_SIZE):
        try:
            results, usage = _classify_batch(client, sub_batch)
            all_sub_results.extend(results)
            aggregate_usage["input"] += usage["input"]
            aggregate_usage["output"] += usage["output"]
        except ValueError as e:
            print(
                f"[claude_classify]   Sub-batch (size {len(sub_batch)}) failed: {e}",
                file=sys.stderr,
            )
            return None, aggregate_usage, e

    print(
        f"[claude_classify]   Fallback to smaller batches succeeded.",
        file=sys.stderr,
    )
    return all_sub_results, aggregate_usage, None


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


def _load_existing_results() -> list[dict]:
    if not OUTPUT_PATH.exists():
        return []
    try:
        with OUTPUT_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(
            f"[claude_classify] WARN: could not read existing results "
            f"({e}); starting fresh.",
            file=sys.stderr,
        )
        return []

    results = payload.get("results")
    if not isinstance(results, list):
        return []
    return [r for r in results if isinstance(r, dict) and r.get("wp_id") is not None]


def _load_existing_failures() -> list[dict]:
    if not FAILURES_PATH.exists():
        return []
    try:
        with FAILURES_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    failures = payload.get("failures")
    if not isinstance(failures, list):
        return []
    return failures


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


def _write_failures(failures: list[dict]) -> None:
    FAILURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "failure_count": len(failures),
        "post_count": sum(len(f.get("posts", [])) for f in failures),
        "failures": failures,
    }
    with FAILURES_PATH.open("w", encoding="utf-8") as f:
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
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(
            "\n[claude_classify] Interrupted by user. "
            "Progress saved to classification_results.json. "
            "Run again to resume from where you stopped.",
            file=sys.stderr,
        )
        sys.exit(130)
