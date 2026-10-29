#!/usr/bin/env bash
# Ventilator: code audit (C++ firmware can't be executed here). Starts only after all
# ventilator generation is done (tests frozen before the code is moved in).
cd "$(dirname "$0")/.."
until grep -q "ALL-DONE doorstop(4) ventilator(2)" runs/run_all.log; do sleep 20; done
echo "$(date +%T) VENTILATOR generation complete -> code audit" >> runs/run_all.log
[ -d ../inputs/ventilator/code ] || mv ../.code_staging/ventilator ../inputs/ventilator/code
.venv/bin/python -u -m tcgen.run --project ventilator --stages S6A --gen ollama:qwen2.5-coder:7b --gen ollama:llama3.1:8b > runs/ventilator.S6A.log 2>&1
echo "$(date +%T) VENTILATOR S6A audit done (exit $?)" >> runs/run_all.log
