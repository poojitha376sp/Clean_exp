#!/usr/bin/env bash
# Second worker: same generation, models in reverse order, so it meets run_all.sh in the middle.
cd "$(dirname "$0")/.."
GENS=$(.venv/bin/python -c "from tcgen.util import CFG; print(' '.join('--gen ' + g for g in reversed(CFG['models']['generators'])))")
for p in ventilator virtual_clinic; do
  echo "$(date +%T) START-REV $p" >> runs/run_all.log
  .venv/bin/python -u -m tcgen.run --project "$p" --stages S2,S3 $GENS >> "runs/$p.rev.log" 2>&1
  echo "$(date +%T) DONE-REV $p (exit $?)" >> runs/run_all.log
done
