// A thin GitHub REST client for one repository. The token comes from the Worker's environment and is only ever
// placed in the Authorization header: never logged, never returned to the browser.

const API = "https://api.github.com";
const cache = new Map();           // finished runs' jobs and logs never change: keep them per isolate
const CACHE_MAX = 300;

export class GitHubError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

export class GitHub {
  // local: optional {file(path), list(path)} reading committed files from a local checkout (dev server only)
  constructor({ token, repo, fetchImpl = globalThis.fetch.bind(globalThis), local = null }) {
    this.local = local;
    if (!/^[\w.-]+\/[\w.-]+$/.test(repo || "")) throw new Error("REPO must look like owner/name");
    this.token = token;
    this.repo = repo;
    this.fetch = fetchImpl;
    this.calls = 0;
  }

  async req(path, { method = "GET", body, accept = "application/vnd.github+json", raw = false } = {}) {
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

  /** A file on main as text, or null if it does not exist. */
  file(path, ref = "main") {
    if (this.local) return this.local.file(path);
    return this.req(this.r(`/contents/${path}?ref=${ref}`), { accept: "application/vnd.github.raw+json", raw: true });
  }

  async json(path) {
    const t = await this.file(path);
    if (t == null) return null;
    try { return JSON.parse(t); } catch { return null; }
  }

  /** The file's metadata (with sha and base64 content), for an update. */
  fileMeta(path) { return this.req(this.r(`/contents/${path}?ref=main`)); }

  listDir(path) {
    if (this.local) return this.local.list(path);
    return this.req(this.r(`/contents/${path}?ref=main`)).then((d) => (Array.isArray(d) ? d : []));
  }

  putFile(path, { content, sha, message }) {
    return this.req(this.r(`/contents/${path}`), { method: "PUT", body: { message, content: b64encode(content), sha, branch: "main" } });
  }

  dispatch(workflow, inputs = {}) {
    return this.req(this.r(`/actions/workflows/${workflow}/dispatches`), { method: "POST", body: { ref: "main", inputs } });
  }
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
