// Self-update for the desktop app: on launch, fast-forward this checkout to GitHub's main so the desktop never runs
// older screens than the web version (9 Nov 2026: it was 9 commits behind). Other sessions work in this same
// checkout, so it only ever fast-forwards, and only when that cannot touch anyone's work:
//   on main  ·  no changes to tracked files  ·  no local commits missing from GitHub.
// Anything else is skipped with a reason the app shows. No network, no git, a timeout: skipped, never blocking.

import { execFile } from "node:child_process";

export function gitRunner(cwd, timeoutMs = 20000) {
  return (args) => new Promise((resolve, reject) =>
    execFile("git", args, { cwd, windowsHide: true, timeout: timeoutMs }, (err, out, errOut) =>
      err ? reject(new Error(String(errOut || err.message).trim().split("\n")[0])) : resolve(String(out).trim())));
}

export async function version(git) {
  const [commit, date] = (await git(["log", "-1", "--format=%h|%cs"])).split("|");
  return { commit, date };
}

/** Whether GitHub's checks passed on a commit: true, false (a check failed), or null (unknown or still running).
 *  11 Nov 2026 audit: launch fast-forwarded to whatever main was, even a commit whose tests had failed. */
export function checksFromGitHub(token, repo, fetchFn = fetch) {
  return async (sha) => {
    try {
      const r = await fetchFn(`https://api.github.com/repos/${repo}/commits/${sha}/check-runs?per_page=50`, {
        headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" }, signal: AbortSignal.timeout(8000) });
      if (!r.ok) return null;
      const runs = (await r.json()).check_runs || [];
      if (runs.some((c) => ["failure", "timed_out", "startup_failure"].includes(c.conclusion))) return false;
      return runs.length && runs.every((c) => c.status === "completed") ? true : null;
    } catch { return null; }
  };
}

/** Returns { updated, from, to, count, reason, version: {commit, date, branch} }. Never throws.
 *  With isGreen (see checksFromGitHub), a main whose checks failed is not taken. */
export async function selfUpdate(git, { isGreen } = {}) {
  let branch = "";
  try {
    branch = await git(["rev-parse", "--abbrev-ref", "HEAD"]);
    const here = { ...(await version(git)), branch };
    const skip = (reason) => ({ updated: false, reason, version: here });
    if (branch !== "main") return skip(`on branch ${branch}, not main`);
    if (await git(["status", "--porcelain", "--untracked-files=no"])) return skip("uncommitted changes in this folder");
    try { await git(["fetch", "--quiet", "origin", "main"]); } catch { return skip("couldn't reach GitHub"); }
    const ahead = Number(await git(["rev-list", "--count", "origin/main..HEAD"]));
    if (ahead > 0) return skip(`${ahead} local commit${ahead === 1 ? "" : "s"} not on GitHub yet`);
    const count = Number(await git(["rev-list", "--count", "HEAD..origin/main"]));
    if (count === 0) return { updated: false, reason: "up to date", version: here };
    if (isGreen) {
      const target = await git(["rev-parse", "origin/main"]);
      if ((await isGreen(target)) === false) return skip(`GitHub's checks failed on main (${target.slice(0, 7)}): staying on ${here.commit}`);
    }
    await git(["merge", "--ff-only", "--quiet", "origin/main"]);
    const now = await version(git);
    return { updated: true, from: here.commit, to: now.commit, count, reason: `updated ${count} change${count === 1 ? "" : "s"}`,
             version: { ...now, branch } };
  } catch (err) {
    return { updated: false, reason: `update skipped: ${err.message}`, version: { commit: "", date: "", branch } };
  }
}
