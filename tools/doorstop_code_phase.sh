#!/usr/bin/env bash
# Starts only when every doorstop generator has all its suites (test generation finished),
# then brings in the code, runs the generated tests (S6) and the code audit (S6A).
cd "$(dirname "$0")/.."
GENS="qwen2.5-coder_7b llama3.1_8b deepseek-coder-v2_16b gemma3_27b"
ready() { for g in $GENS; do [ "$(ls runs/doorstop/ollama_$g/S3_S5_suites 2>/dev/null | wc -l)" -ge 4 ] || return 1; done; }
until ready; do sleep 20; done
echo "$(date +%T) DOORSTOP generation complete -> code phase" >> runs/run_all.log
[ -d ../inputs/doorstop/code ] || mv ../.code_staging/doorstop ../inputs/doorstop/code
GENARGS=""; for g in qwen2.5-coder:7b llama3.1:8b deepseek-coder-v2:16b gemma3:27b; do GENARGS="$GENARGS --gen ollama:$g"; done
.venv/bin/python -u -m tcgen.run --project doorstop --stages S6 $GENARGS > runs/doorstop.S6.log 2>&1
echo "$(date +%T) DOORSTOP S6 execution done (exit $?)" >> runs/run_all.log
.venv/bin/python -u -m tcgen.run --project doorstop --stages S6A $GENARGS > runs/doorstop.S6A.log 2>&1
echo "$(date +%T) DOORSTOP S6A audit done (exit $?)" >> runs/run_all.log
