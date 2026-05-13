// src/index.ts
//
// Cloudflare Worker handling telemetry for ECM Forecasting Alerts.
//
// POST /ping
//   Body: { install_uuid: string, app_version: string }
//   Writes/updates a KV entry: install:<uuid> -> { app_version, last_seen_iso }
//   Returns 204 No Content on success, error JSON otherwise.
//   No auth - any caller can ping with any UUID. That's fine; the worst
//   a malicious caller can do is inflate counts, which doesn't matter
//   at this scale.
//
// GET /stats?key=SECRET
//   Returns aggregated counts: total installs, DAU-7, DAU-30, version
//   distribution. Requires query param 'key' matching STATS_KEY secret.
//   Personal-build APK is the only caller that has the key.
//
// Anything else: 404.

export interface Env {
  TELEMETRY_KV: KVNamespace;
  STATS_KEY?: string;
}

interface InstallRecord {
  app_version: string;
  last_seen_iso: string;
}

interface PingRequest {
  install_uuid?: unknown;
  app_version?: unknown;
}

interface StatsResponse {
  total_installs: number;
  active_last_7d: number;
  active_last_30d: number;
  version_distribution: Record<string, number>;
  generated_at: string;
}

const KV_PREFIX = 'install:';

// --- Validation helpers ---

// Simple UUID v4 shape check. We don't strictly enforce v4 since the
// Dart side uses uuid package and any version is fine; this is just
// a sanity gate against arbitrary unbounded strings.
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isValidUuid(value: unknown): value is string {
  return typeof value === 'string' && UUID_RE.test(value);
}

// App version: SemVer-ish, capped to a reasonable length.
function isValidAppVersion(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.length > 0 &&
    value.length <= 32 &&
    /^[0-9A-Za-z.+\-_]+$/.test(value)
  );
}

// --- Handlers ---

async function handlePing(request: Request, env: Env): Promise<Response> {
  let body: PingRequest;
  try {
    body = (await request.json()) as PingRequest;
  } catch {
    return jsonError(400, 'invalid_json');
  }

  if (!isValidUuid(body.install_uuid)) {
    return jsonError(400, 'invalid_install_uuid');
  }
  if (!isValidAppVersion(body.app_version)) {
    return jsonError(400, 'invalid_app_version');
  }

  const record: InstallRecord = {
    app_version: body.app_version,
    last_seen_iso: new Date().toISOString(),
  };

  await env.TELEMETRY_KV.put(
    `${KV_PREFIX}${body.install_uuid}`,
    JSON.stringify(record),
  );

  return new Response(null, { status: 204 });
}

async function handleStats(
  request: Request,
  env: Env,
): Promise<Response> {
  const url = new URL(request.url);
  const providedKey = url.searchParams.get('key');
  const expected = env.STATS_KEY;

  if (!expected || providedKey !== expected) {
    return jsonError(401, 'unauthorized');
  }

  // Page through all install:* keys.
  // For our scale (<<10k entries) this is fine in a single request.
  // If we ever approach KV list limits (1000 keys per page), the
  // pagination loop handles it.
  const now = Date.now();
  const sevenDaysAgo = now - 7 * 24 * 60 * 60 * 1000;
  const thirtyDaysAgo = now - 30 * 24 * 60 * 60 * 1000;

  let totalInstalls = 0;
  let active7 = 0;
  let active30 = 0;
  const versionDist: Record<string, number> = {};

  let cursor: string | undefined;
  // Safety cap: at our scale we should never hit this. If we do, the
  // returned numbers will be a lower bound and we'll know it's time
  // to redesign the stats path.
  const MAX_PAGES = 50;
  for (let page = 0; page < MAX_PAGES; page++) {
    const listResult = await env.TELEMETRY_KV.list({
      prefix: KV_PREFIX,
      cursor,
    });

    for (const key of listResult.keys) {
      const raw = await env.TELEMETRY_KV.get(key.name);
      if (raw == null) continue;

      let rec: InstallRecord;
      try {
        rec = JSON.parse(raw) as InstallRecord;
      } catch {
        continue; // corrupt entry, skip
      }
      if (
        typeof rec.app_version !== 'string' ||
        typeof rec.last_seen_iso !== 'string'
      ) {
        continue;
      }

      totalInstalls++;
      const lastSeenMs = Date.parse(rec.last_seen_iso);
      if (!isNaN(lastSeenMs)) {
        if (lastSeenMs >= sevenDaysAgo) active7++;
        if (lastSeenMs >= thirtyDaysAgo) active30++;
      }
      versionDist[rec.app_version] =
        (versionDist[rec.app_version] ?? 0) + 1;
    }

    if (listResult.list_complete) break;
    cursor = listResult.cursor;
    if (!cursor) break;
  }

  const response: StatsResponse = {
    total_installs: totalInstalls,
    active_last_7d: active7,
    active_last_30d: active30,
    version_distribution: versionDist,
    generated_at: new Date().toISOString(),
  };

  return new Response(JSON.stringify(response), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

function jsonError(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: code }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

// --- Entry point ---

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === 'POST' && url.pathname === '/ping') {
      return handlePing(request, env);
    }
    if (request.method === 'GET' && url.pathname === '/stats') {
      return handleStats(request, env);
    }

    return jsonError(404, 'not_found');
  },
};
