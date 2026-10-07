#!/bin/bash
# Wait until all 4 full_mu*.npz exist and full run reports ALL FULL RUNS DONE.
# Exits 0 on completion so the runtime delivers the result to the monitor agent.
DIR=/home/hatch/workspace/yade-rve-pann/.worktrees/T08/w1/for_worker/T08/w1
LOG=$DIR/full.log
while true; do
  DONE=1
  for mu in 2.8e+04 3.2e+04; do
    for c in ref pann; do
      [ -f "$DIR/full_mu${mu}_${c}.npz" ] || DONE=0
    done
  done
  if [ "$DONE" = "1" ] && grep -q "ALL FULL RUNS DONE" "$LOG" 2>/dev/null; then
    echo "WAIT_DONE: all 4 full runs complete at $(date -u +%FT%TZ)"
    ls -la "$DIR"/full_mu*.npz
    exit 0
  fi
  sleep 900
done
