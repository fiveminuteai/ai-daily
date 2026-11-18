"""One prompt-tuning pass on the 35B under the shared heavy-job lock (19 Nov 2026, Pavan: "Yes, do it", to bring
the local model up to the current rules). The nightly task will keep it up to date when the 35B is up; this is the
first pass, run while the server is loaded so nothing has to start it.

    python docs/pilots/tune_35b_locked.py            log: ../fma-tune-35b.log

The 35B is never started or stopped here (aicli's start-llama.ps1 owns it). If it is down, nothing runs.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, r"C:\Users\saipa\Personal\Projects\AI\TradingAgents\TradeDesk\alpha")
import heavy_lock  # noqa: E402

LOG = ROOT.parent / "fma-tune-35b.log"


def log(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%F %T ") + str(msg) + "\n")


def main() -> int:
    from fma.llm import local_providers
    if not any(p.model == "qwen3.6-35b-a3b" for p in local_providers()):
        log("the 35B is not up: nothing to tune")
        return 3
    try:
        with heavy_lock.hold("fma-tune-35b", max_minutes=420, max_wait=1800, log=log):
            log("holding the heavy-job lock; tuning qwen3.6-35b-a3b (light search, then held-out scoring)")
            from fma.tune import tune
            r = tune("light", "qwen3.6-35b-a3b", search=True)
            for k in ("facts", "jokes"):
                log(f"{k}: {r[k]['verdict']}")
            log("done")
            return 0
    except heavy_lock.Busy as exc:
        log(f"lock busy: {exc}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
