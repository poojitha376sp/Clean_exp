#!/usr/bin/env bash
# Code comparison re-run with per-test-case retrieval + codebase map (v2).
cd "$(dirname "$0")/.."
D="--gen ollama:qwen2.5-coder:7b --gen ollama:llama3.1:8b --gen ollama:deepseek-coder-v2:16b --gen ollama:gemma3:27b"
V="--gen ollama:qwen2.5-coder:7b --gen ollama:llama3.1:8b"
echo "$(date +%T) CODE-PHASE v2 start" >> runs/run_all.log
( .venv/bin/python -u -m tcgen.run --project doorstop --stages S6 $D > runs/doorstop.S6.log 2>&1
  echo "$(date +%T) DOORSTOP S6 v2 execution done" >> runs/run_all.log
  .venv/bin/python -u -m tcgen.run --project doorstop --stages S6A $D > runs/doorstop.S6A.log 2>&1
  echo "$(date +%T) DOORSTOP S6A v2 audit done" >> runs/run_all.log ) &
( .venv/bin/python -u -m tcgen.run --project ventilator --stages S6A $V > runs/ventilator.S6A.log 2>&1
  echo "$(date +%T) VENTILATOR S6A v2 audit done" >> runs/run_all.log ) &
wait
echo "$(date +%T) CODE-PHASE v2 done; VENTILATOR S6A audit done" >> runs/run_all.log
