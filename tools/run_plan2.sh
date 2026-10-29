#!/usr/bin/env bash
# User plan (2026-09-26, final): Gemma-3-27B dropped (too slow).
# doorstop = 4 models; ventilator = 2 (qwen2.5-coder:7b, phi4:14b). Model-major.
cd "$(dirname "$0")/.."
[ -n "$1" ] && while kill -0 "$1" 2>/dev/null; do sleep 10; done
run() {
  local g=$1; shift
  echo "$(date +%T) MODEL $g : $*" >> runs/run_all.log
  for p in "$@"; do .venv/bin/python -u -m tcgen.run --project "$p" --stages S2,S3 --gen "$g" >> "runs/$p.run.log" 2>&1 & done
  wait
  echo "$(date +%T) MODEL-DONE $g" >> runs/run_all.log
}
run ollama:qwen2.5-coder:7b doorstop ventilator
run ollama:llama3.1:8b doorstop
run ollama:deepseek-coder-v2:16b doorstop
run ollama:phi4:14b doorstop ventilator
echo "$(date +%T) ALL-DONE doorstop(4) ventilator(2)" >> runs/run_all.log
