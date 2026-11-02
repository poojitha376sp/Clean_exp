#!/usr/bin/env bash
# Build a double-blind (anonymised) copy of this repository for the replication package.
#
#   tools/make_anonymous_package.sh [OUT_DIR]        # default: ../clean_exp_anonymous  (must not exist)
#
# What it does (the working repository is never modified):
#   1. copies the tracked + untracked-but-not-ignored files, WITHOUT git history (history holds
#      author names/e-mails), so .env, .cache and other ignored files can never be included;
#   2. leaves out this script, paper sources/PDFs/slides, logs, archives, installers, weights and Ollama tarballs;
#   3. neutralises identifying strings inside the copied text files (usernames inside pytest temp
#      paths in the saved results, workstation paths, server names, author names, e-mails);
#   4. fails (exit 1, copy left in place for inspection) if any identifying token or secret-looking
#      string is still found outside inputs/ (vendored third-party code keeps its own attribution).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="${1:-../clean_exp_anonymous}"
[ ! -e "$OUT" ] || { echo "refusing to overwrite existing $OUT" >&2; exit 2; }
mkdir -p "$OUT"

# 1+2: file list
git ls-files -co --exclude-standard -z | while IFS= read -r -d '' f; do
  [ -f "$f" ] || continue
  case "$f" in
    .env|.env.*) [ "$f" = ".env.example" ] || continue ;;
    main.tex|main-1.pdf|repoSimpleExpl.pdf|paper/paper.*|paper/IEEEtran.cls) continue ;;   # the paper itself
    tools/make_anonymous_package.sh) continue ;;     # authors-only: it lists the strings it removes
    paper/*.pptx|*.pptx|*.docx|*.log|*.zst|*.tar|*.tar.*|*.tgz|*.zip|*.gguf|*.safetensors|*.bin|*.run|*.deb) continue ;;
    paper/fig/*.pdf) continue ;;                                                            # rebuilt by reproduce.sh
    .cache/*|*S6_workspace_gated*|*S6_pyenv*|.postqode/*) continue ;;
  esac
  mkdir -p "$OUT/$(dirname "$f")"; cp -p "$f" "$OUT/$f"
done

# 3: neutralise identifying strings in text files outside inputs/
find "$OUT" -type f -not -path "$OUT/inputs/*" -print0 | while IFS= read -r -d '' f; do
  grep -qI . "$f" 2>/dev/null || continue
  sed -i -E \
    -e 's#pytest-of-[A-Za-z0-9_.-]+#pytest-of-user#g' \
    -e 's#/home/[A-Za-z0-9_.-]+#/home/user#g' \
    -e 's#Honours-Testing#workspace#g' \
    -e 's#rubyserc#gpu-server#g' \
    -e 's#\bSERC\b#institutional#g; s#\bserc\b#user#g' \
    -e 's#poojitha376[A-Za-z0-9_-]*#anonymous#g' \
    -e 's#[A-Za-z0-9._%+-]+@(gmail|research\.[a-z.]+)[A-Za-z.]*#anonymous@example.org#g' \
    -e 's#Poojitha( J)?, Arushi( Tandon)?, Brahma( Reddy Korraprolu)?#Anonymous authors#g' \
    "$f"
done

# 4: verify
fail=0
TOK='poojitha|arushi|tandon|korraprolu|brahma|raghu|iiit|hyderabad|rubyserc|gmail|itstandon|honours-testing|international institute'
if hits=$(grep -rIniE "$TOK|/home/(arushi|serc|poojitha)" "$OUT" --exclude-dir=inputs 2>/dev/null | head -20) && [ -n "$hits" ]; then
  echo "IDENTIFYING TOKENS STILL PRESENT:"; echo "$hits" | cut -c1-200; fail=1
fi
SEC='gsk_[A-Za-z0-9]{10,}|sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{20,}|hf_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|GPU_PASS=[^[:space:]]+|LLM2_API_KEY=[^[:space:]#]+'
if hits=$(grep -rIniE "$SEC" "$OUT" --exclude-dir=inputs 2>/dev/null | head -10) && [ -n "$hits" ]; then
  echo "SECRET-LOOKING STRINGS PRESENT:"; echo "$hits" | cut -c1-120; fail=1
fi
n=$(find "$OUT" -type f | wc -l)
[ $fail = 0 ] && echo "OK: $n files in $OUT, no identifying tokens or secrets found" \
              || { echo "NOT SAFE TO SUBMIT: fix the above ($n files in $OUT)"; exit 1; }
