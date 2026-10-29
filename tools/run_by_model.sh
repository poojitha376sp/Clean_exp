#!/usr/bin/env bash
# Model-major driver: for each generator, run all given projects IN PARALLEL for that
# one model, then move on. Only (generator + judge) sit in GPU memory -> no swapping.
#   tools/run_by_model.sh doorstop ventilator        (resumable: finished suites are skipped)
cd "$(dirname "$0")/.."
GENS=$(.venv/bin/python -c "from tcgen.util import CFG; print(' '.join(CFG['models']['generators']))")
for g in $GENS; do
  echo "$(date +%T) MODEL $g : $*" >> runs/run_all.log
  for p in "$@"; do
    .venv/bin/python -u -m tcgen.run --project "$p" --stages S2,S3 --gen "$g" >> "runs/$p.run.log" 2>&1 &
  done
  wait
  echo "$(date +%T) MODEL-DONE $g" >> runs/run_all.log
done
echo "$(date +%T) ALL-DONE $*" >> runs/run_all.log
