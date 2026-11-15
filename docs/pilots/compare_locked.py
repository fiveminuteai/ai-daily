"""Runs the 7B vs 35B comparison under the machine-wide heavy-job lock (15 Nov 2026), so it never overlaps the
trading desks' heavy jobs or the aicli proofs (which also wait for any compare_models process).

    python docs/pilots/compare_locked.py OUT_DIR

Takes the lock (waits up to 1 h), starts the 35B with aicli's start-llama.ps1 (it refuses during a hold or with too
little RAM), runs 35B then 7B one request at a time, writes OUT/DONE or OUT/GAVE_UP, and releases the lock."""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, r"C:\Users\saipa\Personal\Projects\AI\TradingAgents\TradeDesk\alpha")
import heavy_lock  # noqa: E402  the trading desks' own lock: same file, same protocol

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "locked.log"


def log(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%F %T ") + msg + "\n")


def up() -> bool:
    try:
        return urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=5).status == 200
    except OSError:
        return False


def main() -> int:
    try:
        with heavy_lock.hold("fma-compare-7b-35b", max_minutes=240, max_wait=3600, log=log):
            log("holding the heavy-job lock")
            if not up():
                r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                    r"C:\Users\saipa\Personal\Projects\AI\aicli\scripts\start-llama.ps1"],
                                   capture_output=True, text=True, timeout=900)
                log("start-llama: " + (r.stdout.strip().splitlines() or ["(no output)"])[-1])
            # 15 Nov 04:18: refused at 10 GB free (needs 13). Samples are resumable, so the 7B half runs anyway and a
            # later try fills in only what is missing.
            models = ["35b", "7b"] if up() else ["7b"]
            env = {"OPENBLAS_NUM_THREADS": "2", "PYTHONIOENCODING": "utf-8"}
            import os
            for which in models:
                log(f"run {which}")
                with (OUT / f"run-{which}.log").open("a", encoding="utf-8") as f:
                    subprocess.run([sys.executable, str(ROOT / "docs/pilots/compare_models.py"), "run", which, str(OUT)],
                                   cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, env={**os.environ, **env})
            have = {w: len(list(OUT.glob(f"{w}-*.json"))) for w in ("35b", "7b")}
            log(f"samples on disk: {have}")
            if min(have.values()) >= 18:
                (OUT / "DONE").write_text("done", encoding="utf-8")
                log("done")
                return 0
            (OUT / "PARTIAL").write_text(str(have), encoding="utf-8")
            return 4
    except heavy_lock.Busy as exc:
        log(f"lock busy: {exc}")
        (OUT / "GAVE_UP").write_text(f"heavy-job lock busy: {exc}", encoding="utf-8")
        return 3


if __name__ == "__main__":
    sys.exit(main())
