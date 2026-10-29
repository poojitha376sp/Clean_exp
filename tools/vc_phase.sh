#!/usr/bin/env bash
# virtual_clinic in the background, after doorstop + ventilator code work is finished.
cd "$(dirname "$0")/.."
until grep -q "VENTILATOR S6A audit done" runs/run_all.log && grep -q "DOORSTOP S6A audit done" runs/run_all.log; do sleep 30; done
for g in ollama:qwen2.5-coder:7b ollama:llama3.1:8b; do
  echo "$(date +%T) MODEL $g : virtual_clinic" >> runs/run_all.log
  .venv/bin/python -u -m tcgen.run --project virtual_clinic --stages S2,S3 --gen "$g" >> runs/virtual_clinic.run.log 2>&1
  echo "$(date +%T) MODEL-DONE $g virtual_clinic" >> runs/run_all.log
done
[ -d ../inputs/virtual_clinic/code ] || mv ../.code_staging/virtual_clinic ../inputs/virtual_clinic/code
.venv/bin/python -u -m tcgen.run --project virtual_clinic --stages S6A --gen ollama:qwen2.5-coder:7b --gen ollama:llama3.1:8b > runs/virtual_clinic.S6A.log 2>&1
echo "$(date +%T) VIRTUAL_CLINIC done (exit $?)" >> runs/run_all.log
