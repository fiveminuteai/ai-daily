"""Static risk scan of a downloaded skill folder, run before anything in it is read as instructions or executed.
Usage: python -I skillscan.py <folder>. Reads files as bytes/text only; imports and runs nothing from the folder."""
import ast
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

root = Path(sys.argv[1])
RISKY_IMPORTS = {"socket", "subprocess", "requests", "urllib", "http", "httpx", "aiohttp", "ftplib", "smtplib",
                 "paramiko", "ctypes", "pickle", "marshal", "base64", "winreg", "shutil", "os", "webbrowser",
                 "telnetlib", "ssl", "asyncio", "multiprocessing", "importlib", "zipfile", "tarfile", "tempfile"}
RISKY_CALLS = {"eval", "exec", "compile", "__import__", "system", "popen", "Popen", "run", "call", "check_output",
               "urlopen", "urlretrieve", "remove", "unlink", "rmtree", "getenv", "environ", "startfile", "open"}
INJECT = re.compile(r"ignore (all |any )?(previous|prior|above)|disregard (the|your|all)|system prompt|"
                    r"do not (tell|inform|mention to) the user|without (asking|telling|informing)|"
                    r"api[_ -]?key|access[_ -]?token|password|secret|credential|\.env\b|ssh|id_rsa|"
                    r"curl |wget |powershell|Invoke-|cmd\.exe|\| ?(sh|bash)\b|chmod|sudo|rm -rf|base64|"
                    r"send (it|this|them|the) to|upload (it|this|them) to|exfiltrat|webhook|pastebin|ngrok|"
                    r"auto[- ]?(post|publish|follow|like|dm|comment)|bypass|evade|detection|rate limit|"
                    r"bot|fake (engagement|followers|accounts)|buy followers|scrap", re.I)
URL = re.compile(r"https?://[^\s)\"'>\]]+")
report = {"files": 0, "bytes": 0, "types": {}, "python": {}, "urls": {}, "inject_hits": [], "hidden_chars": [],
          "binary": [], "plugin": {}, "sha256": {}}

for f in sorted(p for p in root.rglob("*") if p.is_file()):
    rel = f.relative_to(root).as_posix()
    data = f.read_bytes()
    report["files"] += 1
    report["bytes"] += len(data)
    report["types"][f.suffix or "(none)"] = report["types"].get(f.suffix or "(none)", 0) + 1
    report["sha256"][rel] = hashlib.sha256(data).hexdigest()[:16]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        report["binary"].append(rel)
        continue
    if b"\x00" in data:
        report["binary"].append(rel)
        continue
    hidden = sorted({f"U+{ord(ch):04X}" for ch in text if unicodedata.category(ch) in ("Cf", "Co", "Cn")
                     or 0xE0000 <= ord(ch) <= 0xE007F})
    if hidden:
        report["hidden_chars"].append((rel, hidden))
    for u in URL.findall(text):
        host = u.split("/")[2]
        report["urls"].setdefault(host, set()).add(rel)
    for n, line in enumerate(text.splitlines(), 1):
        for m in INJECT.finditer(line):
            report["inject_hits"].append((rel, n, m.group(0).lower(), line.strip()[:140]))
    if f.suffix == ".py":
        info = {"imports": set(), "risky_calls": set(), "lines": text.count("\n") + 1, "parse": "ok",
                "writes_files": False}
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    info["imports"] |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom):
                    info["imports"].add((node.module or "").split(".")[0])
                elif isinstance(node, ast.Call):
                    fn = node.func
                    name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""
                    if name in RISKY_CALLS:
                        info["risky_calls"].add(name)
                    if name in ("open", "write_text", "write_bytes"):
                        src = ast.unparse(node)
                        if name != "open" or re.search(r"['\"][wax]b?\+?['\"]", src):
                            info["writes_files"] = True
        except SyntaxError as exc:
            info["parse"] = f"syntax error: {exc}"
        info["risky_imports"] = sorted(info["imports"] & RISKY_IMPORTS)
        info["imports"] = sorted(info["imports"])
        info["risky_calls"] = sorted(info["risky_calls"])
        report["python"][rel] = info
    if rel.startswith(".claude-plugin/") and f.suffix == ".json":
        try:
            j = json.loads(text)
            report["plugin"][rel] = {"keys": sorted(j) if isinstance(j, dict) else type(j).__name__,
                                     "hooks": j.get("hooks") if isinstance(j, dict) else None,
                                     "mcp": j.get("mcpServers") if isinstance(j, dict) else None,
                                     "commands": j.get("commands") if isinstance(j, dict) else None}
        except ValueError as exc:
            report["plugin"][rel] = f"bad json: {exc}"

print("files", report["files"], "bytes", report["bytes"], "types", report["types"])
print("binary or undecodable:", report["binary"] or "none")
print("hidden/format characters:", report["hidden_chars"] or "none")
print("plugin manifests:", json.dumps(report["plugin"], default=str)[:600])
print("\nPYTHON")
for rel, i in report["python"].items():
    print(f"  {rel}: {i['lines']} lines, parse {i['parse']}, imports {i['imports']}, risky imports {i['risky_imports']}, "
          f"risky calls {i['risky_calls']}, writes files {i['writes_files']}")
print("\nURL HOSTS")
for host, files in sorted(report["urls"].items()):
    print(f"  {host}: {sorted(files)}")
print("\nWORDS TO READ WITH CARE:", len(report["inject_hits"]))
seen = {}
for rel, n, word, line in report["inject_hits"]:
    seen.setdefault(word, []).append((rel, n, line))
for word, hits in sorted(seen.items(), key=lambda kv: -len(kv[1])):
    print(f"  {word!r} x{len(hits)}; e.g. {hits[0][0]}:{hits[0][1]}: {hits[0][2]}")
