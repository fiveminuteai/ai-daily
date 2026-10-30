// The desktop app's own data (roadmap, account notes, settings) lives in %APPDATA%\FiveMinuteAI as small JSON files:
// on this computer only, never in git, never secrets. Writes go to a temp file first, then replace, so a crash can't
// leave half a file.

import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

export function dataDir(env = process.env) {
  return env.FMA_DATA_DIR || join(env.APPDATA || join(homedir(), "AppData", "Roaming"), "FiveMinuteAI");
}

export class Store {
  constructor(dir = dataDir()) { this.dir = dir; }

  async read(name, fallback) {
    if (!/^[a-z-]+$/.test(name)) throw new Error("bad store name");
    try {
      return JSON.parse(await readFile(join(this.dir, `${name}.json`), "utf-8"));
    } catch (err) {
      if (err.code === "ENOENT") return typeof fallback === "function" ? fallback() : fallback;
      throw err;
    }
  }

  async write(name, value) {
    if (!/^[a-z-]+$/.test(name)) throw new Error("bad store name");
    await mkdir(this.dir, { recursive: true });
    const file = join(this.dir, `${name}.json`);
    const tmp = `${file}.${process.pid}.tmp`;
    await writeFile(tmp, `${JSON.stringify(value, null, 1)}\n`, "utf-8");
    await rename(tmp, file);
    return value;
  }
}
