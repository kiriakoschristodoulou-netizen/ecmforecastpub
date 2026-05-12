# ECM Forecasting Alerts — Data Schema (v1.0)

Canonical reference for the data flowing between the GitHub Actions pipeline and the Flutter app. Every field this app cares about is documented here.

## File layout

```
ecmforecastpub/   (public repo)
└── backend/
    └── output/
        ├── events_public.json     ← friends APK reads this
        └── version.json           ← all APKs read this

ecmforecast/      (private repo)
├── backend/
│   └── output/
│       └── events_personal.json   ← personal APK reads this (via embedded PAT)
└── inputs/
    └── private/
        ├── README.md              ← format spec
        ├── 2026-05-15-some-post.md  ← KC's content drops
        └── images/
            └── 2026-05-15-ecm-array.png
```

## events.json (top-level)

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-05-12T08:00:00Z",
  "feed_type": "personal",
  "forecasts": [ ... ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | string | yes | SemVer of this schema. v1 = `"1.0"`. App checks compatibility on parse. |
| `generated_at` | ISO 8601 datetime | yes | When the pipeline produced this file. Shown in app as "Updated N days ago." |
| `feed_type` | string | yes | `"personal"` or `"public"`. App can sanity-check it loaded the right file for its build. |
| `forecasts` | array of forecast objects | yes | All forecasts, past and future, in any order. App sorts client-side. |

## Forecast object

The top-level entity. Each forecast is a card on the home screen.

```json
{
  "id": "armstrong-ecm-dc-2026-07-01",
  "date": "2026-07-01",
  "title": "ECM Directional Change",
  "subtitle": "Armstrong ECM",
  "category": "ecm_directional_change",
  "importance": "high",
  "is_convergence": true,
  "importance_justification": "USMCA review and French OAT auction land in the same week.",
  "synthesis": "Armstrong's ECM marks 1 Jul 2026 as a Directional Change...",
  "source": { "name": "...", "url": "..." },
  "related_events": [ ... ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Stable, unique slug. Format: `{source}-{type}-{YYYY-MM-DD}`. Used as the key for local HIT/MISS records — must not change between pipeline runs for the same forecast. |
| `date` | ISO 8601 date (YYYY-MM-DD) | yes | The forecast target date. App formats per user's date-format setting for display. |
| `title` | string | yes | Short headline shown on the card. Keep under ~40 chars for layout. |
| `subtitle` | string | no | Short context line under the title (e.g., "Armstrong ECM", "Panic Cycle"). |
| `category` | string enum | yes | See [Categories](#categories) below. Used for filtering and category-broken-out HIT rates (v2). |
| `importance` | string enum | yes | `"high"` or `"normal"`. Determines card size and visual treatment. |
| `is_convergence` | boolean | yes | `true` when the forecast has 2+ related events. Triggers the CONVERGENCE! badge. Computed by pipeline. |
| `importance_justification` | string | no | One-sentence explanation of why importance was set as it was. Shown in detail view. Required when LLM bumped from normal to high; optional otherwise. |
| `synthesis` | string | yes | The LLM-generated "why this might matter" content. Multi-paragraph allowed. Plain text, no markdown. Shown in detail view. |
| `source` | source object | yes | The originating source. See below. |
| `related_events` | array of related-event objects | no | Scheduled events within ±5 days of `date`. Empty array means no convergence. Omit field or empty array both acceptable. |

### Categories (forecast)

App treats unknown values as "other" and continues to function. Pipeline may emit any of:

- `ecm_turning_point` — Major ECM cycle date (peak, trough)
- `ecm_directional_change` — DC inside an ECM cycle
- `ecm_panic_cycle` — Panic Cycle (always rule-baseline HIGH per project decisions)
- `armstrong_sovereign_debt` — Sovereign debt crisis dates
- `armstrong_war_cycle` — War cycle dates
- `armstrong_currency` — Currency forecast turning points
- `armstrong_other` — Anything else from Armstrong
- `other` — Catch-all

## Related event object

Scheduled real-world events that cluster near a forecast. Only appear inside `related_events[]`, never as standalone cards.

```json
{
  "date": "2026-07-05",
  "title": "French OAT auction",
  "category": "sovereign_debt",
  "url": "https://www.aft.gouv.fr/..."
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `date` | ISO 8601 date | yes | When this event occurs. Must be within ±5 days of the parent forecast's date (pipeline enforces this). |
| `title` | string | yes | Short description. Keep under ~50 chars. |
| `category` | string enum | yes | See below. |
| `url` | string | no | Link to authoritative source. Optional but recommended. Detail view shows an external-link icon when present. |

### Categories (related event)

- `election` — Any election (state, presidential, parliamentary)
- `central_bank` — Rate decisions, FOMC, ECB, BoJ, etc.
- `sovereign_debt` — Bond auctions, rating actions, IMF program reviews
- `treaty` — USMCA, NATO, EU treaty milestones
- `summit` — G7, G20, NATO summits
- `military` — Escalations, troop deadlines, withdrawal deadlines
- `economic_data` — GDP releases, CPI, employment reports
- `other` — Catch-all

## Source object

```json
{
  "name": "Armstrong Economics",
  "url": "https://www.armstrongeconomics.com/some-post-slug"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Human-readable source name. Shown in detail view. |
| `url` | string | no | Direct link to the originating article/post. Detail view shows external-link icon when present. Omit if the forecast comes from KC's personal notes with no public URL. |

## version.json

Independent file polled by all APKs on launch to detect updates.

```json
{
  "schema_version": "1.0",
  "latest_app_version": "1.0.3",
  "latest_build_code": 4,
  "release_url": "https://github.com/kiriakoschristodoulou-netizen/ecmforecastpub/releases/tag/v1.0.3",
  "release_notes": "Fixed countdown timezone issue. Added Polish translation toggle.",
  "min_supported_schema": "1.0",
  "published_at": "2026-05-12T08:00:00Z"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | string | yes | Schema version of this manifest. v1 = `"1.0"`. |
| `latest_app_version` | string | yes | SemVer string. App compares against `package_info_plus`'s version. |
| `latest_build_code` | integer | yes | Monotonically increasing build code (matches Android `versionCode`). |
| `release_url` | string | yes | Direct link to the GitHub Release page (where the APK lives). |
| `release_notes` | string | no | Short human-readable change summary, shown in the update prompt. |
| `min_supported_schema` | string | yes | If an installed app's known schema version is less than this, app should force an update prompt (cannot dismiss). |
| `published_at` | ISO 8601 datetime | yes | When this release was published. |

## Forward-compatibility rules

The schema will evolve. To avoid breaking old APKs already in friends' hands:

1. **Unknown fields are ignored.** App parsers must not fail on fields they don't recognize. Adding fields = safe.
2. **Unknown enum values fall back to a default.** Unknown `category` → treated as `other`. Unknown `importance` → treated as `normal`. App keeps rendering.
3. **Removed fields default sensibly.** If a future schema removes a field the app expects, app uses a default. Document removals in this file's changelog.
4. **Schema version bumps the major number when breaking.** `1.x` → `2.0` means old apps shouldn't parse new data. `min_supported_schema` in version.json triggers a force-update prompt in that case.
5. **Dates are always ISO 8601 strings.** Display formatting is the app's responsibility, not the schema's.
6. **IDs are stable across pipeline runs.** A forecast for the same source-and-date keeps the same ID forever. If a forecast is retracted, its ID disappears from the array — app should drop local HIT/MISS records that have no matching forecast.

## The CONVERGENCE! rule

`is_convergence = (related_events.length >= 2)`

Since related events are only attached when within ±5 days of the forecast date (pipeline-enforced), having 2+ related events automatically means "2+ supporting indicators within a 10-day envelope." That's the convergence signal.

If `is_convergence` is true, the forecast is also automatically HIGH importance regardless of rule-baseline output (pipeline enforces this too). CONVERGENCE! always implies HIGH; HIGH does not always imply CONVERGENCE!.

## The importance pipeline

The pipeline assigns `importance` through three sequential steps:

1. **Rule baseline.** Source-and-category lookup table assigns initial value:
   - HIGH baseline: ECM turning points, DCs, Panic Cycles, sovereign debt events, G7/major-power elections, NATO/EU pivots, treaty deadlines with active disputes, chokepoint events, major-power military escalations
   - NORMAL baseline: everything else
2. **LLM bump.** Synthesis step can bump normal → high (never the reverse) with a one-sentence justification. Justification stored in `importance_justification`.
3. **Convergence override.** If `is_convergence` is true, importance is forced to HIGH (regardless of rule and LLM output).

A manual `importance_override: "high" | "normal"` field MAY appear in events_personal.json (KC sets it by hand). When present, it wins over all three steps above.

## ID generation rules

Format: `{source}-{type}-{YYYY-MM-DD}`

Examples:
- `armstrong-ecm-dc-2026-07-01` (Armstrong ECM Directional Change, 1 Jul 2026)
- `armstrong-pc-2027-01-31` (Armstrong Panic Cycle, 31 Jan 2027)
- `armstrong-sov-2026-08-14` (Armstrong sovereign debt, 14 Aug 2026)

Rules:
- All lowercase
- Hyphens between segments
- Date segment in ISO format
- If two forecasts share source+type+date (rare), append `-{counter}`

The ID is what local HIT/MISS records key against. Changing an ID after publication loses the user's score.

## Data freshness and retention

- Pipeline runs weekly. `generated_at` reflects the latest run.
- All forecasts (past and future) are kept in events.json indefinitely. Pruning is a future optimization; volume stays low (~5-10 new forecasts/month).
- Past forecasts get the same payload as upcoming ones. The app determines past vs upcoming from `date` vs system clock.
- The app's archive view (>60 days past) reads from the same forecasts array — no separate archive file.

## Private input format

KC drops markdown files into `inputs/private/` in the private repo. Each file represents one piece of content read from the private subscription. The pipeline reads new files there, includes them as context in the synthesis call, and generates/updates forecasts accordingly.

See `inputs/private/README.md` for the full format spec.

Filename convention: `YYYY-MM-DD-short-slug.md`. The leading date is the day KC captured the content, used by the pipeline to order inputs.

Images referenced from markdown drops live in `inputs/private/images/` and are passed directly to Claude as base64-encoded image blocks in the API call. The model can read the chart content alongside the text.

## Changelog

- **1.0 (2026-05-12)** — Initial schema.
