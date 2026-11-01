#!/usr/bin/env bash
# Sourced by gpu_ssh.sh and tunnel_keepalive.sh. Loads GPU_USER / GPU_HOST / GPU_PASS from
# the shared .env (one level above the repo) and sets up a throw-away SSH_ASKPASS helper so
# ssh can log in non-interactively. The helper file is deleted when the calling script exits.
# Never print or log GPU_PASS.
SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SERVER_DIR/../../../.env"
export $(grep -E '^GPU_(USER|HOST|PASS)=' "$ENV_FILE" | xargs)
ASK="$(mktemp)"; trap 'rm -f "$ASK"' EXIT
printf '#!/bin/sh\nprintf "%%s\\n" "$GPU_PASS"\n' > "$ASK"; chmod 700 "$ASK"
export SSH_ASKPASS="$ASK" SSH_ASKPASS_REQUIRE=force DISPLAY=:0
