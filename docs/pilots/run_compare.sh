#!/usr/bin/env bash
# Runs the 7B vs 35B comparison (docs/pilots/compare_models.py) only when the machine has room: it waits up to 2 hours
# for 8 GB of free memory and a reachable, idle 35B server, then runs 35B then 7B, and writes DONE (or GAVE_UP).
# 14 Nov 2026: a first try ran at 133 MB free; the 35B server made one token every 20 s.
OUT="$1"
cd "$(dirname "$0")/../.." || exit 1
mkdir -p "$OUT"
free_mb() { powershell -NoProfile -Command "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)"; }
idle() { curl -s -m 10 http://127.0.0.1:8080/slots | python -c "import json,sys; print(any(s['is_processing'] for s in json.load(sys.stdin)))" 2>/dev/null; }
for i in $(seq 1 24); do
  f=$(free_mb | tr -d '\r'); b=$(idle | tr -d '\r')
  echo "$(date '+%F %T') free ${f} MB, 35B busy: ${b}" >> "$OUT/wait.log"
  if [ "${f:-0}" -ge 8000 ] && [ "$b" = "False" ]; then
    OPENBLAS_NUM_THREADS=2 PYTHONIOENCODING=utf-8 python docs/pilots/compare_models.py run 35b "$OUT" >> "$OUT/run-35b.log" 2>&1
    OPENBLAS_NUM_THREADS=2 PYTHONIOENCODING=utf-8 python docs/pilots/compare_models.py run 7b "$OUT" >> "$OUT/run-7b.log" 2>&1
    echo done > "$OUT/DONE"; exit 0
  fi
  sleep 300
done
echo "no room for 2 hours" > "$OUT/GAVE_UP"
