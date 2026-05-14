"""
claude_synthesize.py

PASS 2 of the synthesis pipeline. Reads classification_curated.json
(Pass 1.5 output, 43 keeps), looks up the full post body in the raw
archive, and generates the "why this matters" synthesis text for each
forecast using Claude Sonnet.

Same robust architecture as Pass 1 / Pass 1.5: cumulative append,
retry on JSON-shrinkage failures, adaptive batch shrink.

The synthesis output uses ECM-voiced framing ("the ECM forecast
indicates...") and never names Armstrong directly. This aligns with
the app's disclaimer that it's not affiliated with Armstrong
Economics, and honestly frames the synthesis as model-derived
commentary rather than putting words in Armstrong's mouth.

Each output also includes category_suggestion and tag_suggestion so
the eventual merge with manual_events.json produces consistent taxonomy.

Usage:
    python claude_synthesize.py                # process all unsynthesized
    python claude_synthesize.py --limit 5      # test mode on first 5
    python claude_synthesize.py --reset        # wipe and start over

Reads:
    backend/output/classification_curated.json  (Pass 1.5 output)
    backend/output/armstrong_raw_archive.json   (for post bodies)

Writes:
    backend/output/synthesis_results.json       (cumulative)
    backend/output/synthesis_failures.json      (only if batches fail)

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
CURATED_PATH = SCRIPT_DIR.parent / "output" / "classification_curated.json"
ARCHIVE_PATH = SCRIPT_DIR.parent / "output" / "armstrong_raw_archive.json"
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "synthesis_results.json"
FAILURES_PATH = SCRIPT_DIR.parent / "output" / "synthesis_failures.json"

MODEL = "claude-sonnet-4-6"
PRIMARY_BATCH_SIZE = 2
FALLBACK_BATCH_SIZE = 1
MAX_TOKENS_PER_CALL = 2000
INTER_CALL_DELAY_SECS = 0.5
RETRY_DELAY_SECS = 2.0

MAX_POST_CHARS = 8000


SYSTEM_PROMPT = """You are writing concise synthesis text for an ECM forecast tracker app. The app shows scrollable countdown cards for forecasts derived from the Economic Confidence Model (ECM), a 8.6-year cycle model.

CONTEXT:
For each post, you'll receive:
  - title, post body (truncated to ~8000 chars)
  - reason: why the post was classified as a forecast (from prior pass)
  - predicted_date: the ISO date extracted from the post

Your job: write 2-4 sentence synthesis text explaining WHY THIS FORECAST MATTERS and what dynamics support it. Plus classify the forecast into a category + tag.

VOICE / TONE RULES (CRITICAL):
- NEVER name "Armstrong" or "Martin Armstrong" or anything about him as a person.
- Refer to the model as: "the ECM forecast", "the computer model", "the cycle", "the ECM", "the model", "the array".
- Do NOT use first-name-basis voice or fan-style framing.
- Synthesis is in the voice of an analytical journalist describing what the model indicates and what current dynamics relate to it.
- Acceptable phrasings: "The ECM forecast indicates...", "The cycle suggests...", "Per the model...", "The computer points to...", "According to the ECM..."
- For amendments: "The original forecast was amended from X to Y" (no attribution to a person; the MODEL was amended).

LENGTH:
- 2-4 sentences total (~300-500 characters).
- Short enough to fit on a mobile card without scrolling.
- Long enough to convey: (1) what the forecast says, (2) why it matters, (3) what current dynamics align with it.

CONTENT GUIDANCE:
- First sentence: WHAT the forecast indicates (event + approximate timing)
- Middle sentence(s): WHY it matters / what current dynamics support it
- Optional final sentence: WHAT to watch for as the date approaches

CATEGORY CLASSIFICATION (must match manual_events.json taxonomy):
- "ecm_panic": foundational 8.6yr wave inflection points (wave changes, peaks, troughs)
- "ecm_pi_target": Pi cycle (31.4 year) targets within waves
- "geopolitical_cycle": NATO, treaty bodies, near-term political cycle dates
- "long_cycle": 150.8yr Cycle of War, 309.6yr Cycle of Religious Conflict
- "asset_panic_cycle": asset-specific panic cycles (Dow, Gold, currency, bond)

TAG SUGGESTIONS (more specific within category):
- ecm_panic: wave_change, wave_peak, wave_trough, wave_inflection, wave_end
- ecm_pi_target: pi_cycle_peak
- geopolitical_cycle: nato_inflection, nato_peak, election_cycle
- long_cycle: war_cycle_peak, war_cycle_trough, religion_cycle_peak
- asset_panic_cycle: dow_panic, gold_panic, currency_panic, bond_volatility, oil_panic, etc.

If the post is about something that doesn't fit any clear tag, use a reasonable new tag in snake_case.

OUTPUT FORMAT:
Respond with ONLY a JSON array, one object per post, in the SAME ORDER as input. No prose before or after. Each object MUST have exactly these keys:
  - wp_id (integer): match the input
  - synthesis (string): the 2-4 sentence summary text, ECM-voiced
  - category_suggestion (string): one of the 5 categories
  - tag_suggestion (string): a tag, ideally from the list above
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Synthesize only the first N pending. 0 = all.",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Wipe existing synthesis_results.json and start over.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "[claude_synthesize] ERROR: set ANTHROPIC_API_KEY in environment.",
            file=sys.stderr,
        )
        return 1

    if not CURATED_PATH.exists():
        print(
            f"[claude_synthesize] ERROR: {CURATED_PATH} not found. "
            f"Run claude_refine.py first.",
            file=sys.stderr,
        )
        return 1

    if not ARCHIVE_PATH.exists():
        print(
            f"[claude_synthesize] ERROR: {ARCHIVE_PATH} not found.",
            file=sys.stderr,
        )
        return 1

    # Load Pass 1.5 keeps.
    with CURATED_PATH.open("r", encoding="utf-8") as f:
        curated_payload = json.load(f)
    curated_results = curated_payload.get("results", [])
    pass15_keeps = [r for r in curated_results if r.get("is_forecast")]
    print(
        f"[claude_synthesize] Pass 1.5 has {len(curated_results)} total results, "
        f"{len(pass15_keeps)} marked as forecasts."
    )

    # Load raw archive for body content.
    with ARCHIVE_PATH.open("r", encoding="utf-8") as f:
        archive_payload = json.load(f)
    raw_by_id = {int(p["wp_id"]): p for p in archive_payload.get("posts", [])}

    # Load existing synthesis results (cumulative-append mode).
    existing_results: list[dict] = []
    existing_failures: list[dict] = []
    if args.reset:
        if OUTPUT_PATH.exists():
            OUTPUT_PATH.unlink()
            print("[claude_synthesize] --reset: deleted existing results.")
        if FAILURES_PATH.exists():
            FAILURES_PATH.unlink()
            print("[claude_synthesize] --reset: deleted existing failures log.")
    else:
        existing_results = _load_existing_results()
        existing_failures = _load_existing_failures()

    done_ids = {int(r["wp_id"]) for r in existing_results}
    failed_ids = {int(p["wp_id"]) for f in existing_failures for p in f.get("posts", [])}
    skip_ids = done_ids | failed_ids

    if existing_results:
        print(
            f"[claude_synthesize] Resume: {len(existing_results)} posts already "
            f"synthesized."
        )

    # Build pending list. For each kept post, attach the raw body + the
    # Pass 1.5 reason + predicted_date for Claude to draw on.
    pending: list[dict] = []
    for keep in pass15_keeps:
        wp_id = int(keep["wp_id"])
        if wp_id in skip_ids:
            continue
        raw = raw_by_id.get(wp_id)
        if raw is None:
            print(
                f"[claude_synthesize] WARN: wp_id {wp_id} kept by Pass 1.5 "
                f"not found in archive; skipping.",
                file=sys.stderr,
            )
            continue
        pending.append({
            "wp_id": wp_id,
            "title": _strip_html(raw.get("title", "")),
            "body": _strip_html(raw.get("content_html", ""))[:MAX_POST_CHARS],
            "link": raw.get("link", ""),
            "date_published": raw.get("date_published", ""),
            "pass15_reason": keep.get("reason", ""),
            "pass15_predicted_date": keep.get("predicted_date"),
        })

    if args.limit > 0:
        pending = pending[: args.limit]

    if not pending:
        print("[claude_synthesize] Nothing to do - all Pass 1.5 keeps already synthesized.")
        return 0

    print(f"[claude_synthesize] Synthesizing {len(pending)} pending posts.")

    client = Anthropic(api_key=api_key)

    new_results: list[dict] = existing_results.copy()
    new_failures: list[dict] = existing_failures.copy()
    total_input_tokens = 0
    total_output_tokens = 0

    batches = list(_chunked(pending, PRIMARY_BATCH_SIZE))
    print(f"[claude_synthesize] {len(batches)} batches of up to {PRIMARY_BATCH_SIZE} posts.")

    for batch_idx, batch in enumerate(batches, start=1):
        print(
            f"[claude_synthesize] Batch {batch_idx}/{len(batches)} "
            f"({len(batch)} posts)..."
        )

        batch_results, usage, error = _synthesize_with_retries(client, batch)

        if batch_results is not None:
            new_results.extend(batch_results)
            total_input_tokens += usage["input"]
            total_output_tokens += usage["output"]

            print(
                f"[claude_synthesize] Batch {batch_idx}: {len(batch_results)} "
                f"synthesized (in_tok={usage['input']}, out_tok={usage['output']})"
            )
        else:
            new_failures.append({
                "batch_idx_at_failure": batch_idx,
                "logged_at": datetime.now(timezone.utc).isoformat(),
                "error": str(error),
                "posts": [
                    {"wp_id": p["wp_id"], "title": p.get("title", "")}
                    for p in batch
                ],
            })
            print(
                f"[claude_synthesize] Batch {batch_idx}: FAILED after retries. "
                f"Logged {len(batch)} posts to failures. Continuing.",
                file=sys.stderr,
            )
            _write_failures(new_failures)

        # Sonnet pricing: input $3/M, output $15/M.
        est_cost = (total_input_tokens * 3.0 / 1_000_000) + (total_output_tokens * 15.0 / 1_000_000)
        _write_results(new_results, partial=(batch_idx < len(batches)), usage={
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "estimated_cost_usd": est_cost,
            "model": MODEL,
        })

        if batch_idx < len(batches):
            time.sleep(INTER_CALL_DELAY_SECS)

    est_cost = (total_input_tokens * 3.0 / 1_000_000) + (total_output_tokens * 15.0 / 1_000_000)
    total_failed = sum(len(f.get("posts", [])) for f in new_failures)

    print(
        f"\n[claude_synthesize] Done. {len(new_results)} forecasts synthesized."
    )
    if total_failed:
        print(
            f"[claude_synthesize] {total_failed} posts in failures log "
            f"({FAILURES_PATH}); investigate or clear file to retry."
        )
    print(
        f"[claude_synthesize] Tokens this run: in={total_input_tokens}, "
        f"out={total_output_tokens}. Estimated incremental cost: ${est_cost:.4f}"
    )
    print(f"[claude_synthesize] Total results in {OUTPUT_PATH}: {len(new_results)}")
    return 0


def _synthesize_with_retries(
    client: Anthropic, batch: list[dict]
) -> tuple[list[dict] | None, dict, Exception | None]:
    """
    Three-stage retry: primary -> retry same -> fallback to size 1.
    """
    aggregate_usage = {"input": 0, "output": 0}

    try:
        results, usage = _synthesize_batch(client, batch)
        aggregate_usage["input"] += usage["input"]
        aggregate_usage["output"] += usage["output"]
        return results, aggregate_usage, None
    except ValueError as e:
        print(f"[claude_synthesize]   Attempt 1 failed: {e}. Retrying...", file=sys.stderr)
        time.sleep(RETRY_DELAY_SECS)

    try:
        results, usage = _synthesize_batch(client, batch)
        aggregate_usage["input"] += usage["input"]
        aggregate_usage["output"] += usage["output"]
        print(f"[claude_synthesize]   Attempt 2 succeeded.", file=sys.stderr)
        return results, aggregate_usage, None
    except ValueError as e:
        print(
            f"[claude_synthesize]   Attempt 2 failed: {e}. "
            f"Falling back to batch_size={FALLBACK_BATCH_SIZE}...",
            file=sys.stderr,
        )
        time.sleep(RETRY_DELAY_SECS)

    all_sub_results: list[dict] = []
    for sub_batch in _chunked(batch, FALLBACK_BATCH_SIZE):
        try:
            results, usage = _synthesize_batch(client, sub_batch)
            all_sub_results.extend(results)
            aggregate_usage["input"] += usage["input"]
            aggregate_usage["output"] += usage["output"]
        except ValueError as e:
            print(
                f"[claude_synthesize]   Sub-batch (size {len(sub_batch)}) "
                f"failed: {e}",
                file=sys.stderr,
            )
            return None, aggregate_usage, e

    print(
        f"[claude_synthesize]   Fallback to smaller batches succeeded.",
        file=sys.stderr,
    )
    return all_sub_results, aggregate_usage, None


def _synthesize_batch(client: Anthropic, batch: list[dict]) -> tuple[list[dict], dict]:
    posts_payload = []
    for p in batch:
        posts_payload.append({
            "wp_id": p["wp_id"],
            "title": p["title"],
            "date_published": p.get("date_published", ""),
            "reason": p.get("pass15_reason", ""),
            "predicted_date": p.get("pass15_predicted_date"),
            "body": p["body"],
        })

    user_message = (
        "For each Armstrong Economics post below, write a 2-4 sentence "
        "synthesis using ECM-voiced framing (never name Armstrong). "
        "Today's date is "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.\n\n"
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

    parsed = _parse_synthesis_response(raw_text, batch)

    return parsed, {
        "input": response.usage.input_tokens,
        "output": response.usage.output_tokens,
    }


def _parse_synthesis_response(raw_text: str, batch: list[dict]) -> list[dict]:
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
        for required_key in ("wp_id", "synthesis", "category_suggestion", "tag_suggestion"):
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
            "title": input_post["title"],
            "link": input_post.get("link", ""),
            "predicted_date": input_post.get("pass15_predicted_date"),
            "synthesis": str(result["synthesis"]),
            "category_suggestion": str(result["category_suggestion"]),
            "tag_suggestion": str(result["tag_suggestion"]),
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
            f"[claude_synthesize] WARN: could not read existing results "
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
            "\n[claude_synthesize] Interrupted. Progress saved. "
            "Run again to resume.",
            file=sys.stderr,
        )
        sys.exit(130)
