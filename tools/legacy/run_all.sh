#!/usr/bin/env bash
# ARCHIVED (kept for provenance, superseded by tools/run_experiment.sh; see tools/README.md).
# Worker A: doorstop, then ventilator (forward model order), then virtual_clinic. Resumable.
cd "$(dirname "$0")/../.."
for p in doorstop ventilator virtual_clinic; do
  echo "$(date +%T) START $p" >> runs/run_all.log
  .venv/bin/python -u -m tcgen.run --project "$p" --stages S2,S3 >> "runs/$p.run.log" 2>&1
  echo "$(date +%T) DONE $p (exit $?)" >> runs/run_all.log
done
