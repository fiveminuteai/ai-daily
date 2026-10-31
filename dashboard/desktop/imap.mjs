// A minimal, read-only IMAP client: log in, open a folder read-only (EXAMINE, so nothing is marked as read), read the
// newest messages' envelopes (date, from, subject, read/unread), log out. No message bodies. No dependencies.
// Zoho: imap.zoho.in (India) or imap.zoho.com, port 993, TLS, with an app password.

import { connect as tlsConnect } from "node:tls";

export class ImapError extends Error {}

/** Tokenise an IMAP response into nested arrays of atoms/strings; NIL becomes null. Literals arrive as quoted strings. */
export function parseList(text) {
  let i = 0;
  function value() {
    while (text[i] === " ") i++;
    const ch = text[i];
    if (ch === "(") {
      i++;
      const out = [];
      for (;;) {
        while (text[i] === " ") i++;
        if (text[i] === ")") { i++; return out; }
        if (i >= text.length) throw new ImapError("unbalanced list");
        out.push(value());
      }
    }
    if (ch === '"') {
      let s = "";
      i++;
      while (i < text.length && text[i] !== '"') {
        if (text[i] === "\\") i++;
        s += text[i++];
      }
      i++;
      return s;
    }
    const m = /^[^\s()"]+(\[[^\]]*\])?/.exec(text.slice(i));
    if (!m) throw new ImapError("bad token");
    i += m[0].length;
    return m[0] === "NIL" ? null : m[0];
  }
  const out = [];
  while (i < text.length) {
    while (text[i] === " ") i++;
    if (i < text.length) out.push(value());
  }
  return out;
}

/** RFC 2047 encoded words (=?UTF-8?B?...?= and =?UTF-8?Q?...?=). */
export function decodeWords(s) {
  if (!s) return "";
  return String(s).replace(/=\?([^?]+)\?([BbQq])\?([^?]*)\?=(\s+(?==\?))?/g, (_, charset, enc, data) => {
    try {
      const bytes = enc.toUpperCase() === "B"
        ? Buffer.from(data, "base64")
        : Buffer.from(data.replace(/_/g, " ").replace(/=([0-9A-Fa-f]{2})/g, (__, h) => String.fromCharCode(parseInt(h, 16))), "latin1");
      return new TextDecoder(/utf-?8/i.test(charset) ? "utf-8" : charset).decode(bytes);
    } catch {
      return data;
    }
  });
}

function address(list) {
  const a = Array.isArray(list) && list[0];
  if (!Array.isArray(a)) return { name: "", email: "" };
  return { name: decodeWords(a[0] || ""), email: a[2] && a[3] ? `${a[2]}@${a[3]}` : "" };
}

/** One "* n FETCH (...)" line into a message summary. */
export function parseFetch(line) {
  const m = /^\* (\d+) FETCH (\(.*\))\s*$/s.exec(line);
  if (!m) return null;
  const [items] = parseList(m[2]);
  const get = (k) => { const at = items.findIndex((x) => typeof x === "string" && x.toUpperCase() === k); return at >= 0 ? items[at + 1] : undefined; };
  const env = get("ENVELOPE") || [];
  const flags = get("FLAGS") || [];
  const internal = get("INTERNALDATE");
  const date = Date.parse(internal || env[0] || "");
  return {
    seq: Number(m[1]), uid: Number(get("UID")) || null,
    date: Number.isFinite(date) ? new Date(date).toISOString() : null,
    subject: decodeWords(env[1] || "") || "(no subject)",
    from: address(env[2]),
    unread: !flags.some((f) => String(f).toLowerCase() === "\\seen"),
    flagged: flags.some((f) => String(f).toLowerCase() === "\\flagged"),
  };
}

const quote = (s) => `"${String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;

/**
 * Newest `limit` messages of a folder, newest first, plus totals.
 * connect(opts) must return a duplex socket; tests pass a plain TCP connect to a fake server.
 */
export async function fetchInbox({ host, port = 993, user, pass, folder = "INBOX", limit = 25, connect = tlsConnect, timeoutMs = 20000 }) {
  const sock = connect({ host, port, servername: host });
  sock.setEncoding?.("latin1");
  let buf = "";
  let waiter = null;
  let closed = false;
  const fail = (err) => { if (waiter) { const w = waiter; waiter = null; w.reject(err); } };
  sock.on("data", (d) => { buf += d; waiter?.check(); });
  sock.on("error", (e) => fail(new ImapError(`connection failed (${e.code || e.message})`)));
  sock.on("close", () => { closed = true; fail(new ImapError("connection closed")); });
  const timer = setTimeout(() => { fail(new ImapError("timed out")); sock.destroy(); }, timeoutMs);

  // Read until a line matching `done` arrives; a literal {n} is inlined as a quoted string (line breaks become spaces).
  function until(done) {
    return new Promise((resolve, reject) => {
      const lines = [];
      waiter = {
        reject,
        check() {
          for (;;) {
            const nl = buf.indexOf("\r\n");
            if (nl < 0) return;
            let line = buf.slice(0, nl);
            const lit = /\{(\d+)\}$/.exec(line);
            if (lit) {
              const n = Number(lit[1]);
              if (buf.length < nl + 2 + n) return;               // wait for the whole literal
              const bytes = buf.slice(nl + 2, nl + 2 + n);
              const q = `"${bytes.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/[\r\n]+/g, " ")}"`;
              buf = line.slice(0, lit.index) + q + buf.slice(nl + 2 + n);
              continue;
            }
            buf = buf.slice(nl + 2);
            line = Buffer.from(line, "latin1").toString("utf-8");
            lines.push(line);
            if (done(line)) { waiter = null; resolve(lines); return; }
          }
        },
      };
      waiter.check();
    });
  }
  let n = 0;
  async function cmd(text) {
    const tag = `a${++n}`;
    sock.write(`${tag} ${text}\r\n`);
    const lines = await until((l) => l.startsWith(`${tag} `));
    const last = lines.at(-1);
    if (!/^\S+ OK/i.test(last)) {
      throw new ImapError(/AUTHENTICATIONFAILED|LOGIN|AUTH/i.test(last) || text.startsWith("LOGIN")
        ? "login failed: check the app password" : `server said: ${last.replace(/^\S+ /, "").slice(0, 120)}`);
    }
    return lines;
  }
  try {
    const greet = await until(() => true);
    if (!/^\* (OK|PREAUTH)/i.test(greet[0])) throw new ImapError("unexpected greeting");
    await cmd(`LOGIN ${quote(user)} ${quote(pass)}`);
    const sel = await cmd(`EXAMINE ${quote(folder)}`);
    const exists = Number((sel.find((l) => / EXISTS$/i.test(l)) || "").match(/^\* (\d+)/)?.[1] || 0);
    let messages = [];
    if (exists > 0) {
      const from = Math.max(1, exists - limit + 1);
      const lines = await cmd(`FETCH ${from}:${exists} (UID FLAGS INTERNALDATE ENVELOPE)`);
      messages = lines.map(parseFetch).filter(Boolean).sort((a, b) => b.seq - a.seq);
    }
    const unseen = await cmd("SEARCH UNSEEN");
    const unread = ((unseen.find((l) => /^\* SEARCH/i.test(l)) || "").replace(/^\* SEARCH\s*/i, "").trim().split(/\s+/).filter(Boolean)).length;
    sock.write(`a${++n} LOGOUT\r\n`);
    return { folder, total: exists, unread, messages };
  } finally {
    clearTimeout(timer);
    if (!closed) sock.end();
  }
}
