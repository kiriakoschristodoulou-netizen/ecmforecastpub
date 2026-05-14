"""
claude_refine.py

PASS 1.5 of the synthesis pipeline. Reads classification_results.json
(Pass 1 output), filters to is_forecast=true entries, and re-classifies
each with a STRICTER prompt requiring:

  - The predicted date must be explicitly attributed to Armstrong's
    ECM, computer, Socrates, or model output (NOT his editorial
    speculation, NOT government/policy dates, NOT historical dates)
  - The post must either present a NEW ECM-derived date OR
    AMEND/REFINE an existing model date

Output: classification_curated.json - the filtered, refined keep list
for Pass 2 synthesis to consume.

Usage:
    python claude_refine.py                # process all Pass 1 keeps
    python claude_refine.py --limit 5      # test mode on first 5 keeps
    python claude_refine.py --reset        # wipe existing curated, start over

Reads:
    backend/output/classification_results.json (Pass 1 output)
    backend/output/armstrong_raw_archive.json  (for post bodies)

Writes:
    backend/output/classification_curated.json (cumulative, can resume)

Environment:
    ANTHROPIC_API_KEY (required)

Same retry / cumulative-append architecture as claude_classify.py.
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
ARCHIVE_PATH = SCRIPT_DIR.parent / "output" / "armstrong_raw_archive.json"
CLASSIFY_PATH = SCRIPT_DIR.parent / "output" / "classification_results.json"
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "classification_curated.json"
FAILURES_PATH = SCRIPT_DIR.parent / "output" / "refine_failures.json"

MODEL = "claude-haiku-4-5-20251001"
PRIMARY_BATCH_SIZE = 5
FALLBACK_BATCH_SIZE = 3
MAX_TOKENS_PER_CALL = 2000
INTER_CALL_DELAY_SECS = 0.5
RETRY_DELAY_SECS = 2.0

MAX_POST_CHARS = 8000


SYSTEM_PROMPT = """You are refining a list of Armstrong Economics blog posts that were already classified as potential ECM forecasts. Your task is to apply a STRICTER filter to identify only posts that genuinely contain model-attributed dated predictions.

CONTEXT:
Martin Armstrong publishes a public Economic Confidence Model (ECM) with specific cycle dates. His blog posts serve different purposes:
  - Some posts REPORT new model output: "The computer is now showing a turning point on Aug 14, 2026"
  - Some posts AMEND existing model output: "The May panic is being delayed to August"
  - Many posts merely REFERENCE existing model dates in passing: "as we approach the 2028 wave..."
  - Many posts contain Armstrong's editorial speculation that is NOT model-attributed: "Trump may invade Venezuela by mid-2026"
  - Many posts report government, policy, or historical dates that Armstrong is just analyzing: "Germany targets 2039 for military buildup"

The app only needs posts in the FIRST TWO CATEGORIES.

KEEP A POST (is_forecast=true) IF AND ONLY IF ALL OF THE FOLLOWING:
  1. The post presents a NEW model-derived dated prediction OR AMENDS/REFINES an existing model date
  2. The date is EXPLICITLY attributed to Armstrong's ECM, computer, Socrates, model, array, or panic cycle
  3. The date is specific to at least month-level precision (year-only is too vague)
  4. The date is in the FUTURE (after today)

DROP A POST (is_forecast=false) IF:
  - The post only references known existing model dates without amending them
    Example: "I have been warning about the 2028 wave for years" - no amendment, drop
  - The date is Armstrong's editorial speculation, NOT model-attributed
    Example: "Trump will likely invade Venezuela in early 2026" - editorial, drop
  - The date is a government, corporate, or policy date Armstrong reports on
    Example: "Germany aims to have its army ready by 2039" - policy date, drop
  - The date is a historical event Armstrong is analyzing
    Example: "The 2008 crisis began..." - historical, drop
  - The date is year-only with no month/quarter specificity
    Example: "Sometime in 2028..." - too vague, drop
  - The post is commentary, news, opinion, or analysis without a specific model-dated amendment
  - The post is meta-commentary about Armstrong's model itself without making a new prediction

DATE EXTRACTION RULES:
  - If Armstrong says "May 17, 2026" -> predicted_date = "2026-05-17"
  - If Armstrong says "August 2026" -> predicted_date = "2026-08-01" (month-level OK)
  - If Armstrong says "Q3 2026" -> predicted_date = null, is_forecast = false (quarter-only too vague)
  - If Armstrong says "into 2028" or "by 2028" or just "2028" -> predicted_date = null, is_forecast = false (year-only too vague)
  - If Armstrong says "next month" or "next year" -> calculate the specific month based on the post's publication date

CONFIDENCE LEVELS:
  - "high": Armstrong explicitly attributes the date to his computer/ECM/Socrates AND the date is specific to a day or specific month
  - "medium": Attribution is implied (e.g. discussion of his model output without naming it explicitly) OR date is month-level
  - "low": You are uncertain whether this meets the criteria

OUTPUT FORMAT:
Respond with ONLY a JSON array, one object per post, in the SAME ORDER as input. No prose before or after. Each object MUST have exactly these keys:
  - wp_id (integer): match the input
  - is_forecast (boolean)
  - confidence ("high" | "medium" | "low")
  - predicted_date (string YYYY-MM-DD or null - MUST be null if is_forecast=false)
  - reason (string, max 1 sentence; if is_forecast=true must cite the specific model attribution AND the specific predicted event AND the future date)
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Refine only the first N pending posts. 0 = all.",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Wipe existing classification_curated.json and start over.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "[claude_refine] ERROR: set ANTHROPIC_API_KEY in environment.",
            file=sys.stderr,
        )
        return 1

    if not CLASSIFY_PATH.exists():
        print(
            f"[claude_refine] ERROR: {CLASSIFY_PATH} not found. "
            f"Run claude_classify.py first.",
            file=sys.stderr,
        )
        return 1

    if not ARCHIVE_PATH.exists():
        print(
            f"[claude_refine] ERROR: {ARCHIVE_PATH} not found. "
            f"Run wp_backfill.py first.",
            file=sys.stderr,
        )
        return 1

    # Load Pass 1 keeps.
    with CLASSIFY_PATH.open("r", encoding="utf-8") as f:
        classify_payload = json.load(f)
    pass1_results = classify_payload.get("results", [])
    pass1_keeps = [r for r in pass1_results if r.get("is_forecast")]
    print(
        f"[claude_refine] Pass 1 has {len(pass1_results)} total results, "
        f"{len(pass1_keeps)} marked as forecasts."
    )

    # Load raw archive for body content.
    with ARCHIVE_PATH.open("r", encoding="utf-8") as f:
        archive_payload = json.load(f)
    raw_by_id = {int(p["wp_id"]): p for p in archive_payload.get("posts", [])}

    # Load existing curated results (cumulative-append mode).
    existing_results: list[dict] = []
    existing_failures: list[dict] = []
    if args.reset:
        if OUTPUT_PATH.exists():
            OUTPUT_PATH.unlink()
            print("[claude_refine] --reset: deleted existing curated results.")
        if FAILURES_PATH.exists():
            FAILURES_PATH.unlink()
            print("[claude_refine] --reset: deleted existing failures log.")
    else:
        existing_results = _load_existing_results()
        existing_failures = _load_existing_failures()

    done_ids = {int(r["wp_id"]) for r in existing_results}
    failed_ids = {int(p["wp_id"]) for f in existing_failures for p in f.get("posts", [])}
    skip_ids = done_ids | failed_ids

    if existing_results:
        kept_so_far = sum(1 for r in existing_results if r.get("is_forecast"))
        print(
            f"[claude_refine] Resume: {len(existing_results)} posts already "
            f"refined ({kept_so_far} kept after refinement)."
        )

    # Build the pending list. We need the FULL POST BODY from the archive,
    # not just the Pass 1 metadata, because Pass 1.5 re-reads with stricter rules.
    pending: list[dict] = []
    for keep in pass1_keeps:
        wp_id = int(keep["wp_id"])
        if wp_id in skip_ids:
            continue
        raw = raw_by_id.get(wp_id)
        if raw is None:
            print(
                f"[claude_refine] WARN: wp_id {wp_id} kept by Pass 1 not "
                f"found in archive; skipping.",
                file=sys.stderr,
            )
            continue
        pending.append(raw)

    if args.limit > 0:
        pending = pending[: args.limit]

    if not pending:
        print("[claude_refine] Nothing to do - all Pass 1 keeps already refined.")
        return 0

    print(f"[claude_refine] Refining {len(pending)} pending posts.")

    client = Anthropic(api_key=api_key)

    new_results: list[dict] = existing_results.copy()
    new_failures: list[dict] = existing_failures.copy()
    total_input_tokens = 0
    total_output_tokens = 0

    batches = list(_chunked(pending, PRIMARY_BATCH_SIZE))
    print(f"[claude_refine] {len(batches)} batches of up to {PRIMARY_BATCH_SIZE} posts.")

    for batch_idx, batch in enumerate(batches, start=1):
        print(
            f"[claude_refine] Batch {batch_idx}/{len(batches)} "
            f"({len(batch)} posts)..."
        )

        batch_results, usage, error = _refine_with_retries(client, batch)

        if batch_results is not None:
            new_results.extend(batch_results)
            total_input_tokens += usage["input"]
            total_output_tokens += usage["output"]

            kept = sum(1 for r in batch_results if r.get("is_forecast"))
            print(
                f"[claude_refine] Batch {batch_idx}: kept {kept}/{len(batch)} "
                f"(in_tok={usage['input']}, out_tok={usage['output']})"
            )
        else:
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
                f"[claude_refine] Batch {batch_idx}: FAILED after all retries. "
                f"Logged {len(batch)} posts to failures. Continuing.",
                file=sys.stderr,
            )
            _write_failures(new_failures)

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
        f"\n[claude_refine] Done. {total_kept}/{len(new_results)} kept after "
        f"refinement ({100*total_kept//max(len(new_results),1)}% of Pass 1 keeps survived)."
    )
    if total_failed:
        print(
            f"[claude_refine] {total_failed} posts in failures log "
            f"({FAILURES_PATH}); investigate or clear file to retry."
        )
    print(
        f"[claude_refine] Tokens this run: in={total_input_tokens}, out={total_output_tokens}. "
        f"Estimated incremental cost: ${est_cost:.4f}"
    )
    print(f"[claude_refine] Total curated entries in {OUTPUT_PATH}: {len(new_results)}")
    return 0


def _refine_with_retries(
    client: Anthropic, batch: list[dict]
) -> tuple[list[dict] | None, dict, Exception | None]:
    aggregate_usage = {"input": 0, "output": 0}

    try:
        results, usage = _refine_batch(client, batch)
        aggregate_usage["input"] += usage["input"]
        aggregate_usage["output"] += usage["output"]
        return results, aggregate_usage, None
    except ValueError as e:
        print(f"[claude_refine]   Attempt 1 failed: {e}. Retrying...", file=sys.stderr)
        time.sleep(RETRY_DELAY_SECS)

    try:
        results, usage = _refine_batch(client, batch)
        aggregate_usage["input"] += usage["input"]
        aggregate_usage["output"] += usage["output"]
        print(f"[claude_refine]   Attempt 2 succeeded.", file=sys.stderr)
        return results, aggregate_usage, None
    except ValueError as e:
        print(
            f"[claude_refine]   Attempt 2 failed: {e}. "
            f"Falling back to batch_size={FALLBACK_BATCH_SIZE}...",
            file=sys.stderr,
        )
        time.sleep(RETRY_DELAY_SECS)

    all_sub_results: list[dict] = []
    for sub_batch in _chunked(batch, FALLBACK_BATCH_SIZE):
        try:
            results, usage = _refine_batch(client, sub_batch)
            all_sub_results.extend(results)
            aggregate_usage["input"] += usage["input"]
            aggregate_usage["output"] += usage["output"]
        except ValueError as e:
            print(
                f"[claude_refine]   Sub-batch (size {len(sub_batch)}) failed: {e}",
                file=sys.stderr,
            )
            return None, aggregate_usage, e

    print(f"[claude_refine]   Fallback to smaller batches succeeded.", file=sys.stderr)
    return all_sub_results, aggregate_usage, None


def _refine_batch(client: Anthropic, batch: list[dict]) -> tuple[list[dict], dict]:
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
        "Apply the STRICT refinement criteria to each Armstrong Economics "
        "post below. Today's date is "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}. "
        "ONLY keep posts that present a NEW or AMENDED model-attributed "
        "dated prediction with at least month-level specificity. BE STRICT.\n\n"
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

    parsed = _parse_refine_response(raw_text, batch)

    return parsed, {
        "input": response.usage.input_tokens,
        "output": response.usage.output_tokens,
    }


def _parse_refine_response(raw_text: str, batch: list[dict]) -> list[dict]:
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

        is_forecast = bool(result["is_forecast"])
        predicted_date = result["predicted_date"]
        # Sanity check: if is_forecast=false, predicted_date must be null.
        if not is_forecast and predicted_date is not None:
            predicted_date = None

        validated.append({
            "wp_id": int(result["wp_id"]),
            "title": _strip_html(input_post.get("title", "")),
            "link": input_post.get("link", ""),
            "is_forecast": is_forecast,
            "confidence": str(result["confidence"]),
            "predicted_date": predicted_date,
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
            f"[claude_refine] WARN: could not read existing curated results "
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
        "input_post_count": len(results),
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
            "\n[claude_refine] Interrupted by user. "
            "Progress saved. Run again to resume.",
            file=sys.stderr,
        )
        sys.exit(130)
