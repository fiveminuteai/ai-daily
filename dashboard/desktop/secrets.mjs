// Secrets for the desktop app come only from Windows Credential Manager, under names "FiveMinuteAI/<name>".
// They are read on demand, kept in this process's memory, and never written to a file, a log or a response.

import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT = fileURLToPath(new URL("./cred.ps1", import.meta.url));
export const CREDENTIALS = {
  github: { label: "GitHub token", user: "github", why: "pipeline, history, posts, controls, stats" },
  zoho: { label: "Zoho Mail app password", user: "hello@fiveminuteai.net", why: "the Mail screen (read-only inbox)" },
};
const cache = new Map();

function run(file, args) {
  return new Promise((resolve) => {
    execFile(file, args, { windowsHide: true, timeout: 20000, maxBuffer: 1 << 20 }, (err, stdout) => {
      resolve({ code: err ? (typeof err.code === "number" ? err.code : 1) : 0, stdout: String(stdout || "") });
    });
  });
}

/** {user, secret} or null. runner is injectable for tests. */
export async function readCredential(name, { runner = run } = {}) {
  if (!Object.hasOwn(CREDENTIALS, name)) throw new Error("unknown credential");
  if (cache.has(name)) return cache.get(name);
  const { code, stdout } = await runner("powershell.exe",
    ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, "-Target", `FiveMinuteAI/${name}`]);
  if (code !== 0 || !stdout.trim()) return null;
  try {
    const { user, secret } = JSON.parse(stdout);
    if (!secret) return null;
    const value = { user: user || "", secret };
    cache.set(name, value);
    return value;
  } catch {
    return null;
  }
}

export function forget(name) { cache.delete(name); }

/** Which FiveMinuteAI/* credentials exist (names only), parsed from `cmdkey /list`. */
export async function listCredentials({ runner = run } = {}) {
  const { stdout } = await runner("cmdkey.exe", ["/list:FiveMinuteAI/*"]);
  return parseCmdkeyList(stdout);
}

export function parseCmdkeyList(text) {
  const names = new Set();
  for (const m of String(text).matchAll(/Target:\s*(?:LegacyGeneric:target=)?FiveMinuteAI\/([a-z0-9-]+)/gi)) names.add(m[1].toLowerCase());
  return Object.fromEntries(Object.keys(CREDENTIALS).map((k) => [k, names.has(k)]));
}

export function addCommand(name) {
  const c = CREDENTIALS[name];
  return `cmdkey /generic:FiveMinuteAI/${name} /user:${c.user} /pass`;
}
