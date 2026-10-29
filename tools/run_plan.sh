#!/usr/bin/env bash
# User plan 2026-09-26: doorstop = all 5 models; ventilator = 3 (qwen2.5-coder:7b, phi4:14b, gemma3:27b).
# Model-major, projects of the same model in parallel. Waits for a still-running job first.
cd "$(dirname "$0")/.."
[ -n "$1" ] && while kill -0 "$1" 2>/dev/null; do sleep 10; done
run() {  # run <model> <projects...>
  local g=$1; shift
  echo "$(date +%T) MODEL $g : $*" >> runs/run_all.log
  for p in "$@"; do .venv/bin/python -u -m tcgen.run --project "$p" --stages S2,S3 --gen "$g" >> "runs/$p.run.log" 2>&1 & done
  wait
  echo "$(date +%T) MODEL-DONE $g" >> runs/run_all.log
}
run ollama:qwen2.5-coder:7b doorstop ventilator      # resumes/finishes anything left
run ollama:llama3.1:8b doorstop
run ollama:deepseek-coder-v2:16b doorstop
echo "$(date +%T) DOORSTOP-READY-EXCEPT phi4,gemma3" >> runs/run_all.log
run ollama:phi4:14b doorstop ventilator
run ollama:gemma3:27b doorstop ventilator
echo "$(date +%T) ALL-DONE doorstop(5) ventilator(3)" >> runs/run_all.log
