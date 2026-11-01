#!/usr/bin/env bash
# One command for the whole experiment: every generator in config.yaml x every project.
#
#   tools/run_experiment.sh                          # phases gen then code, all models, all projects
#   tools/run_experiment.sh --phase gen              # generation only (S2,S3)
#   tools/run_experiment.sh --phase code             # stage the code, then S6/S6A only
#   tools/run_experiment.sh --projects "doorstop ventilator" --models "qwen2.5-coder:7b llama3.1:8b"
#
# Needs the tunnel (tools/server/tunnel_keepalive.sh) and the models pulled
# (tools/server/pull_models.sh). Safe to re-run after an outage: it waits for the server and
# for each model, and finished suites/cached calls are reused. Progress goes to runs/run_all.log.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

PHASE=all PROJECTS="$ALL_PROJECTS" MODELS=""
while [ $# -gt 0 ]; do
  case $1 in
    --phase) PHASE=$2; shift 2 ;;
    --projects) PROJECTS=$2; shift 2 ;;
    --models) MODELS=$2; shift 2 ;;
    *) echo "unknown option: $1 (see header of this script)" >&2; exit 2 ;;
  esac
done
[ -n "$MODELS" ] || MODELS=$(config_generators)
projects=""; for p in $PROJECTS; do has_project "$p" && projects="$projects $p" || echo "skip $p: ../inputs/$p/srs missing" >&2; done
[ -n "$projects" ] || { echo "no project inputs found under ../inputs" >&2; exit 1; }

wait_for_server
log "START phase=$PHASE projects=$projects"

if [ "$PHASE" = all ] || [ "$PHASE" = gen ]; then
  for tag in $MODELS; do wait_for_model "$tag"; generate "$tag" $projects; done
  log "ALL-GENERATION-DONE"
fi

if [ "$PHASE" = all ] || [ "$PHASE" = code ]; then
  stage_code $projects
  for tag in $MODELS; do code_phase "$tag" $projects; done
fi
log "ALL-DONE"
