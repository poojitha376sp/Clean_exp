#!/usr/bin/env bash
# Shared helpers for the experiment drivers. Source it; it does not run anything itself.
#   source "$(dirname "$0")/lib.sh"
# Everything is resumable: finished suites are skipped and LLM calls are served from .cache/llm.

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
PY="${PY:-.venv/bin/python}"
LOG="${LOG:-runs/run_all.log}"
OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11435}"   # default: the SSH tunnel (server/tunnel_keepalive.sh); with a local GPU: export OLLAMA_BASE_URL=http://localhost:11434
ALL_PROJECTS="doorstop ventilator virtual_clinic"
EXECUTABLE_PROJECTS="doorstop"                           # generated tests can be run; the others get the code audit only
mkdir -p runs

log() { echo "$(date +%T) $*" >> "$LOG"; }

# Generators to run: models.generators minus models.skip (config.yaml), one Ollama tag per line,
# "ollama:" prefix removed.
config_generators() {
  "$PY" -c "from tcgen.util import active_generators; print('\n'.join(g.split(':',1)[1] for g in active_generators()))"
}

wait_for_server() {          # block until the Ollama server answers through the tunnel
  until curl -s -m 5 "$OLLAMA_URL/api/version" > /dev/null; do sleep 30; done
}

wait_for_model() {           # wait_for_model <ollama tag>: block until the tag has been pulled
  local tag=$1 announced=0
  until curl -s -m 10 "$OLLAMA_URL/api/tags" | grep -q "\"name\":\"$tag\""; do
    [ $announced = 0 ] && log "WAIT-DOWNLOAD $tag"; announced=1; sleep 60
  done
}

has_project() { [ -d "inputs/$1/srs" ]; }

# Stages S2,S3 (representation choice + generate/validate/judge loop) for one model on several
# projects. Projects run in parallel; only generator + judge are in GPU memory, so no swapping.
generate() {                 # generate <ollama tag> <project...>
  local tag=$1; shift
  log "GENERATE ollama:$tag : $*"
  local p
  for p in "$@"; do
    $PY -u -m tcgen.run --project "$p" --stages S2,S3 --gen "ollama:$tag" >> "runs/$p.run.log" 2>&1 &
  done
  wait
  log "GENERATE-DONE ollama:$tag"
}

# S6 (run generated tests; executable projects only) and S6A (code audit) for one model.
code_phase() {               # code_phase <ollama tag> <project...>
  local tag=$1; shift
  local p stages
  for p in "$@"; do
    case " $EXECUTABLE_PROJECTS " in *" $p "*) stages=S6,S6A ;; *) stages=S6A ;; esac
    $PY -u -m tcgen.run --project "$p" --stages "$stages" --gen "ollama:$tag" >> "runs/$p.S6.log" 2>&1
  done
  log "CODE-DONE ollama:$tag : $*"
}
