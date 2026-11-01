// A thin GitHub REST client for one repository. The token comes from the Worker's environment and is only ever
// placed in the Authorization header: never logged, never returned to the browser.

const API = "https://api.github.com";
const cache = new Map();           // finished runs' jobs and logs never change: keep them per isolate
const CACHE_MAX = 300;

// Every other GET: fresh for 45 s, then served stale (up to 30 min) while one background request refreshes it,
// so a screen never waits on GitHub twice. Any write clears it. Kept per fetch function, so tests with their own
// fake fetch never share entries.
const FRESH_MS = 45e3;
const STALE_MS = 30 * 60e3;
const GET_MAX = 600;
const DEFAULT_OWNER = {};
const getCaches = new WeakMap();

export class GitHubError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

export class GitHub {
  // local: optional {file(path), list(path)}: a local checkout used for files main doesn't have yet (dev server only)
  constructor({ token, repo, fetchImpl, local = null }) {
    this.local = local;
    if (!/^[\w.-]+\/[\w.-]+$/.test(repo || "")) throw new Error("REPO must look like owner/name");
    this.token = token;
    this.repo = repo;
    this.fetch = fetchImpl || globalThis.fetch.bind(globalThis);
    this.owner = fetchImpl || DEFAULT_OWNER;
    this.calls = 0;
  }

  store() {
    if (!getCaches.has(this.owner)) getCaches.set(this.owner, new Map());
    return getCaches.get(this.owner);
  }

  req(path, opts = {}) {
    const { method = "GET", accept = "application/vnd.github+json", raw = false } = opts;
    const store = this.store();
    if (method !== "GET") {
      store.clear();                     // a write may change anything we have cached
      return this.send(path, opts);
    }
    const key = `${this.repo}|${accept}|${raw ? 1 : 0}|${path}`;
    const hit = store.get(key);
    const now = Date.now();
    if (hit && "value" in hit && now - hit.at < STALE_MS) {
      if (now - hit.at > FRESH_MS && !hit.refreshing) {
        hit.refreshing = this.send(path, opts)
          .then((value) => store.set(key, { at: Date.now(), value }))
          .catch(() => { hit.refreshing = null; });     // keep serving the stale copy; try again next time
      }
      return Promise.resolve(hit.value);
    }
    if (hit?.inflight) return hit.inflight;           // the same request is already on its way
    const inflight = this.send(path, opts).then(
      (value) => { store.set(key, { at: Date.now(), value }); return value; },
      (err) => { store.delete(key); throw err; });
    store.set(key, { inflight });
    if (store.size > GET_MAX) store.delete(store.keys().next().value);
    return inflight;
  }

  async send(path, { method = "GET", body, accept = "application/vnd.github+json", raw = false } = {}) {
    this.calls += 1;
    const res = await this.fetch(`${API}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${this.token}`, Accept: accept, "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "fiveminuteai-dashboard", ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 404 && method === "GET") return null;
    if (!res.ok) {
      let msg = `${res.status}`;
      try { msg = `${res.status} ${(await res.json()).message || ""}`.trim(); } catch { /* not JSON */ }
      throw new GitHubError(res.status, `GitHub ${method} ${path.split("?")[0]}: ${msg}`);
    }
    if (res.status === 204) return {};
    return raw ? res.text() : res.json();
  }

  r(path) { return `/repos/${this.repo}${path}`; }

  async cached(key, done, load) {
    if (cache.has(key)) return cache.get(key);
    const v = await load();
    if (done) {
      if (cache.size >= CACHE_MAX) cache.delete(cache.keys().next().value);
      cache.set(key, v);
    }
    return v;
  }

  runs(workflow, { created, perPage = 30 } = {}) {
    const q = new URLSearchParams({ per_page: String(perPage), ...(created ? { created } : {}) });
    return this.req(this.r(`/actions/workflows/${workflow}/runs?${q}`)).then((d) => d?.workflow_runs || []);
  }

  jobs(run) {
    return this.cached(`jobs:${run.id}`, run.status === "completed",
      () => this.req(this.r(`/actions/runs/${run.id}/jobs?per_page=50`)).then((d) => d?.jobs || []));
  }

  jobLog(job) {
    return this.cached(`log:${job.id}`, job.status === "completed",
      () => this.req(this.r(`/actions/jobs/${job.id}/logs`), { raw: true }).catch(() => ""));
  }

  /** A file on main as text, or null if it does not exist. With a local checkout, a file main doesn't have yet
   *  (one only on an unmerged branch) comes from the checkout; main always wins, so new posts still show. */
  async file(path, ref = "main") {
    const remote = await this.req(this.r(`/contents/${path}?ref=${ref}`), { accept: "application/vnd.github.raw+json", raw: true });
    return remote ?? (this.local ? this.local.file(path) : null);
  }

  async json(path) {
    const t = await this.file(path);
    if (t == null) return null;
    try { return JSON.parse(t); } catch { return null; }
  }

  /** The file's metadata (with sha and base64 content), for an update. */
  fileMeta(path) { return this.send(this.r(`/contents/${path}?ref=main`)); }          // never cached: a write needs the current sha

  async listDir(path) {
    const remote = await this.req(this.r(`/contents/${path}?ref=main`)).then((d) => (Array.isArray(d) ? d : []));
    if (!this.local) return remote;
    const names = new Set(remote.map((f) => f.name));
    return [...remote, ...(await this.local.list(path)).filter((f) => !names.has(f.name))];
  }

  putFile(path, { content, sha, message }) {
    return this.req(this.r(`/contents/${path}`), { method: "PUT", body: { message, content: b64encode(content), ...(sha ? { sha } : {}), branch: "main" } });
  }

  dispatch(workflow, inputs = {}) {
    return this.req(this.r(`/actions/workflows/${workflow}/dispatches`), { method: "POST", body: { ref: "main", inputs } });
  }
}

/**
 * The desktop app saves the default cache when it stops and loads it when it starts, so the first screen shows the
 * last known state at once and refreshes itself in the background. Only GitHub responses (public repository data);
 * no token. Entries come back marked old, so every one is refreshed on first use.
 */
export function exportCache() {
  const gets = [...(getCaches.get(DEFAULT_OWNER) || new Map())].filter(([, e]) => "value" in e).map(([k, e]) => [k, e.at, e.value]);
  return { version: 1, saved: Date.now(), gets, done: [...cache] };
}

export function importCache(data, now = Date.now()) {
  if (!data || data.version !== 1 || now - data.saved > 24 * 3600e3) return 0;
  const store = getCaches.get(DEFAULT_OWNER) || new Map();
  getCaches.set(DEFAULT_OWNER, store);
  // aged past fresh but inside stale: shown at once, refreshed on first use
  for (const [k, , value] of data.gets || []) store.set(k, { at: now - FRESH_MS - 1, value });
  for (const [k, v] of data.done || []) if (cache.size < CACHE_MAX) cache.set(k, v);
  return store.size;
}

export function b64decode(b64) {
  const bin = atob(String(b64).replace(/\s/g, ""));
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
}

export function b64encode(text) {
  const bytes = new TextEncoder().encode(text);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}
