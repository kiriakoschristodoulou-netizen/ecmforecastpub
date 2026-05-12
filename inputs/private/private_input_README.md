# Private input drops

This directory holds content captured from KC's private subscription (Armstrong Economics private blog). The weekly GitHub Action reads new files here, includes them as context in the Claude synthesis call, and folds any forecasts found into `events_personal.json`.

## How to add a drop

1. Read something worth capturing on the private blog.
2. Create a new file: `inputs/private/YYYY-MM-DD-short-slug.md` (date = day you captured it).
3. Fill the frontmatter (see below).
4. Paste an excerpt or write your own summary in the body.
5. If charts matter, save the screenshot to `inputs/private/images/` and reference it from the body.
6. Commit (web UI, phone, anywhere - it's just a markdown file).
7. The next weekly pipeline run picks it up.

You can drop multiple files per week. The pipeline orders them by filename date.

## File format

```markdown
---
captured_at: 2026-05-15
source_title: "Q3 ECM Array Refinement"
source_url: https://www.armstrongeconomics.com/private/some-post-slug
forecast_dates_mentioned:
  - 2026-07-01
  - 2026-08-14
  - 2027-01-31
relevance: high
notes: "Updated July date to the 1st (was previously the 2nd). Confirms convergence with USMCA review."
---

# Q3 ECM Array Refinement

Excerpt or summary goes here. Plain markdown. Can include images:

![ECM array Q3 2026](images/2026-05-15-ecm-array.png)

Whatever I want the LLM to see when generating the synthesis. The body can be:

- A direct paste of relevant paragraphs from the article
- Your own notes interpreting what the article says
- A description of a chart in your own words
- Questions you have about the content

The pipeline includes the full body verbatim in the Claude API call, alongside any referenced images as base64-encoded image blocks. The model sees both at once.
```

## Frontmatter fields

| Field | Required | Description |
|---|---|---|
| `captured_at` | yes | ISO date when you captured the content. Matches filename date. |
| `source_title` | yes | The article or post title from the source. |
| `source_url` | no | URL to the original post (even if paywalled - the LLM never fetches it, but the URL goes into the forecast's `source.url` field for your future reference). |
| `forecast_dates_mentioned` | no | YAML list of ISO dates the article references. Helps the pipeline associate this drop with existing forecasts or create new ones. |
| `relevance` | no | `low` / `normal` / `high`. Hints to the pipeline how heavily to weight this drop. Default: `normal`. |
| `notes` | no | Short free-text note for your future self. Not used by the pipeline; useful when you re-read the file later. |

## Image handling

Place screenshots in `inputs/private/images/`. Reference them via standard markdown:

```markdown
![alt text describing the chart](images/2026-05-15-ecm-array.png)
```

The pipeline:
1. Resolves the path
2. Reads the bytes
3. Base64-encodes them
4. Includes them in the Claude API call as image content blocks

Cost: each image adds roughly 1-2k tokens to the API call. Cents per image at our volume.

Recommended image specs:
- PNG or JPEG
- Under 2 MB each (Claude handles larger but it slows the call)
- Crop tight to the chart - whitespace wastes tokens
- Filename: `YYYY-MM-DD-short-description.png` matching the drop date

Images live in the private repo forever. Repo size stays small (a few MB per year at typical drop frequency).

## What the pipeline does with drops

1. **Reads all `.md` files in this directory** (recursively but not into `images/`).
2. **Sorts by `captured_at`** (oldest first - lets newer drops correct older ones).
3. **Includes them as context** in a Claude API call alongside:
   - Public Armstrong RSS feed content
   - Scheduled-event calendar (elections, central bank meetings, treaty deadlines)
   - The previous run's `events_personal.json` (for stability of IDs)
4. **Claude returns** a new `events_personal.json` with:
   - Updated forecasts (existing IDs preserved, content refined)
   - New forecasts (with fresh IDs)
   - Importance justifications when bumping
   - Related events attached within ±5 days
5. **Pipeline commits** the new events_personal.json to the private repo.
6. **Personal APK** fetches it on next launch.

## Drops are not auto-deleted

A drop you make in May 2026 stays in the directory forever. The pipeline reads everything every run, so older drops continue to inform forecasts indefinitely. If you want to retire a drop (e.g., a forecast that's been clearly superseded), move it to `inputs/private/archive/` - the pipeline ignores that folder.

## Example: minimal drop

```markdown
---
captured_at: 2026-05-15
source_title: "Note on July ECM correction"
---

Armstrong corrected the July ECM date from the 2nd to the 1st. No other changes.
```

That's a valid drop. The pipeline will read this on the next run and update the existing 2026-07-02 forecast's date to 2026-07-01 (preserving the ID's stable reference, regenerating the slug if needed).

## Example: image-heavy drop

```markdown
---
captured_at: 2026-05-15
source_title: "Q3 ECM Array, full chart"
source_url: https://www.armstrongeconomics.com/private/q3-array
forecast_dates_mentioned:
  - 2026-07-01
  - 2026-11-12
  - 2027-01-31
relevance: high
---

# Q3 ECM Array, full chart

The full array shows three relevant dates in our forward window:

![Q3 ECM array showing July 2026, Nov 2026, Jan 2027 markers](images/2026-05-15-ecm-q3-array.png)

The chart marks 2027-01-31 with a notation I haven't seen before - looks like a sub-pivot indicator nested inside the broader Panic Cycle marker. Worth noting in the synthesis.

The November 2026 marker is described as "minor" in the chart legend - this is the same date Armstrong has called a "micro-turn" in earlier public posts.
```

The pipeline reads this, looks at the chart image, and can generate synthesis that cites both the article text and observations from the chart itself.
