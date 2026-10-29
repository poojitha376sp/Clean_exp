#!/usr/bin/env bash
# Final plan: Phi-4 unusable on this server -> doorstop 4th = Gemma-3-27B, ventilator 2nd = Llama-3.1-8B.
cd "$(dirname "$0")/.."
run() { local g=$1; shift; echo "$(date +%T) MODEL $g : $*" >> runs/run_all.log
  for p in "$@"; do .venv/bin/python -u -m tcgen.run --project "$p" --stages S2,S3 --gen "$g" >> "runs/$p.run.log" 2>&1 & done
  wait; echo "$(date +%T) MODEL-DONE $g" >> runs/run_all.log; }
run ollama:gemma3:27b doorstop
run ollama:llama3.1:8b ventilator
echo "$(date +%T) ALL-DONE doorstop(4) ventilator(2)" >> runs/run_all.log
