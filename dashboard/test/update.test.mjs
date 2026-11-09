// Self-update against real git repos in a temp folder: a bare "GitHub" and the app's clone.
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { gitRunner, selfUpdate } from "../desktop/update.mjs";

async function setup() {
  const dir = await mkdtemp(join(tmpdir(), "fma-update-"));
  const origin = join(dir, "origin.git"), app = join(dir, "app"), other = join(dir, "other");
  const g = (cwd) => gitRunner(cwd);
  await g(dir)(["init", "--quiet", "--bare", "-b", "main", origin]);
  for (const c of [app, other]) await g(dir)(["clone", "--quiet", origin, c]);
  for (const c of [app, other]) {
    await g(c)(["config", "user.email", "t@example.com"]);
    await g(c)(["config", "user.name", "t"]);
    await g(c)(["checkout", "--quiet", "-B", "main"]);
  }
  const commit = async (c, file, text) => {
    await writeFile(join(c, file), text);
    await g(c)(["add", file]);
    await g(c)(["commit", "--quiet", "-m", `${file}: ${text}`]);
  };
  await commit(other, "a.txt", "v1");
  await g(other)(["push", "--quiet", "origin", "main"]);
  await g(app)(["pull", "--quiet", "origin", "main"]);
  const head = (c) => g(c)(["rev-parse", "--short", "HEAD"]);
  const newer = async () => { await commit(other, "a.txt", "v2"); await g(other)(["push", "--quiet", "origin", "main"]); };
  return { dir, origin, app, g, commit, head, newer, done: () => rm(dir, { recursive: true, force: true }) };
}

test("a clean main that is behind fast-forwards to GitHub", async () => {
  const s = await setup();
  try {
    await s.newer();
    const r = await selfUpdate(s.g(s.app));
    assert.equal(r.updated, true);
    assert.equal(r.count, 1);
    assert.equal(await readFile(join(s.app, "a.txt"), "utf-8"), "v2");
    assert.equal(r.version.commit, await s.head(s.app));
    assert.equal((await selfUpdate(s.g(s.app))).reason, "up to date");
  } finally { await s.done(); }
});

test("uncommitted changes to tracked files are never touched", async () => {
  const s = await setup();
  try {
    await s.newer();
    await writeFile(join(s.app, "a.txt"), "someone's unsaved work");
    const before = await s.head(s.app);
    const r = await selfUpdate(s.g(s.app));
    assert.equal(r.updated, false);
    assert.match(r.reason, /uncommitted/);
    assert.equal(await s.head(s.app), before);
    assert.equal(await readFile(join(s.app, "a.txt"), "utf-8"), "someone's unsaved work");
  } finally { await s.done(); }
});

test("untracked files do not block an update", async () => {
  const s = await setup();
  try {
    await s.newer();
    await writeFile(join(s.app, "scratch.txt"), "draft");
    assert.equal((await selfUpdate(s.g(s.app))).updated, true);
    assert.equal(await readFile(join(s.app, "scratch.txt"), "utf-8"), "draft");
  } finally { await s.done(); }
});

test("another branch, local commits, or no network: skipped with a reason", async () => {
  const s = await setup();
  try {
    await s.newer();
    await s.g(s.app)(["checkout", "--quiet", "-b", "voiced-reels"]);
    assert.match((await selfUpdate(s.g(s.app))).reason, /on branch voiced-reels/);
    await s.g(s.app)(["checkout", "--quiet", "main"]);

    await s.commit(s.app, "b.txt", "local");              // diverged: local commit + newer GitHub commit
    const before = await s.head(s.app);
    const r = await selfUpdate(s.g(s.app));
    assert.equal(r.updated, false);
    assert.match(r.reason, /1 local commit not on GitHub/);
    assert.equal(await s.head(s.app), before);

    await s.g(s.app)(["remote", "set-url", "origin", join(s.dir, "gone.git")]);
    assert.match((await selfUpdate(s.g(s.app))).reason, /couldn't reach GitHub/);
  } finally { await s.done(); }
});

test("not a git folder: skipped, never thrown", async () => {
  const dir = await mkdtemp(join(tmpdir(), "fma-nogit-"));
  try {
    const r = await selfUpdate(gitRunner(dir));
    assert.equal(r.updated, false);
    assert.match(r.reason, /update skipped/);
  } finally { await rm(dir, { recursive: true, force: true }); }
});
