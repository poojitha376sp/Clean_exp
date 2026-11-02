#!/usr/bin/env bash
# Sourced by gpu_ssh.sh and tunnel_keepalive.sh. Reads the SSH target from the shared .env (one
# level above the repo; template: .env.example) and fills the array SSH_AUTH_OPTS.
#
#   GPU_USER, GPU_HOST   required
#   GPU_SSH_KEY          recommended: path to a private key. Used with -i, no password needed.
#   GPU_PASS             optional fallback when no key is set. Handed to ssh through a throw-away
#                        SSH_ASKPASS helper that is deleted when the calling script exits.
# Never print or log any of these values.
SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SERVER_DIR/../../../.env}"
[ -r "$ENV_FILE" ] || { echo "missing $ENV_FILE (copy .env.example there and fill it in)" >&2; return 1 2>/dev/null || exit 1; }
export $(grep -E '^GPU_(USER|HOST|PASS|SSH_KEY)=' "$ENV_FILE" | xargs)
: "${GPU_USER:?GPU_USER not set in $ENV_FILE}" "${GPU_HOST:?GPU_HOST not set in $ENV_FILE}"
SSH_AUTH_OPTS=()
if [ -n "${GPU_SSH_KEY:-}" ]; then
  SSH_AUTH_OPTS=(-i "${GPU_SSH_KEY/#\~/$HOME}" -o IdentitiesOnly=yes -o BatchMode=yes)
elif [ -n "${GPU_PASS:-}" ]; then
  ASK="$(mktemp)"; trap 'rm -f "$ASK"' EXIT
  printf '#!/bin/sh\nprintf "%%s\\n" "$GPU_PASS"\n' > "$ASK"; chmod 700 "$ASK"
  export SSH_ASKPASS="$ASK" SSH_ASKPASS_REQUIRE=force DISPLAY=:0
fi   # else: ssh-agent / default keys
