#!/bin/bash
# T08 full-run watchdog: restart run_full.py if it dies (checkpoint resume),
# exit when all 4 full_mu*.npz exist and full run reports ALL FULL RUNS DONE.
WT=/home/hatch/workspace/yade-rve-pann/.worktrees/T08/w1
PY=/home/hatch/workspace/venvs/rve-pann/bin/python
DIR=$WT/for_worker/T08/w1
LOG=$DIR/full.log
cd "$WT" || exit 1
RESTARTS=0
echo "[monitor] started $(date -u +%FT%TZ), watching full run"
while true; do
  DONE=1
  for mu in 2.8e+04 3.2e+04; do
    for c in ref pann; do
      [ -f "$DIR/full_mu${mu}_${c}.npz" ] || DONE=0
    done
  done
  if [ "$DONE" = "1" ] && grep -q "ALL FULL RUNS DONE" "$LOG" 2>/dev/null; then
    echo "[monitor] ALL 4 full runs complete at $(date -u +%FT%TZ)"
    grep -A6 "^\[full\] SUMMARY" "$LOG" | tail -6
    exit 0
  fi
  if ! pgrep -f "for_worker/T08/w1/run_full.py" >/dev/null; then
    # double-check to avoid duplicate launches
    sleep 10
    if ! pgrep -f "for_worker/T08/w1/run_full.py" >/dev/null; then
      echo "[monitor] $(date -u +%FT%TZ) run_full.py dead, restarting (resume from checkpoint)"
      nohup "$PY" for_worker/T08/w1/run_full.py >> "$LOG" 2>&1 &
      RESTARTS=$((RESTARTS+1))
      echo "[monitor] restart #$RESTARTS, pid $!"
    fi
  fi
  sleep 600
done
