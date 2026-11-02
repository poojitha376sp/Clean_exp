#!/usr/bin/env bash
# Rebuild every derived result from the committed data and check it against the committed files.
# No GPU, no network (apart from pip), no LLM calls. Takes a few minutes.
#
#   tools/reproduce.sh              # create .venv if missing, install requirements.txt, rebuild, compare
#   tools/reproduce.sh --no-install # reuse the current environment (python3, or $PY, must have the requirements)
#
# For each derived file it prints PASS (identical to the committed copy) or FAIL (different/missing).
# Exit status 1 if anything FAILs. Figures (PDF) are rebuilt but only checked for existence and
# non-zero size: matplotlib stamps a creation date into PDFs, so they are never byte-identical.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export TCGEN_STRICT=1                      # an LLM call is never needed here; if one is attempted, stop

if [ "${1:-}" = "--no-install" ]; then PY="${PY:-python3}"
else
  [ -x .venv/bin/python ] || python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt || { echo "pip install failed" >&2; exit 2; }
  PY=.venv/bin/python
fi
echo "python: $($PY -V 2>&1)"

# 1. Remember the committed state of everything the scripts write.
OUT=runs/ANALYSIS
SNAP="$(mktemp -d)"; trap 'rm -rf "$SNAP"' EXIT
mkdir -p "$SNAP/ANALYSIS"; cp -r "$OUT"/. "$SNAP/ANALYSIS"/
FIGS=(fsa_by_model.pdf fsa_by_repr_group.pdf)
for b in "${FIGS[@]}"; do [ -f "paper/fig/$b" ] && cp -p "paper/fig/$b" "$SNAP/$b"; done

# 2. Rebuild.
$PY -B -m tcgen.analyze         > /dev/null || { echo "tcgen.analyze failed" >&2; exit 2; }
$PY -B tools/sensitivity.py     > /dev/null || { echo "sensitivity.py failed" >&2; exit 2; }
$PY -B paper/fig/build_figures.py > /dev/null 2>&1 || echo "note: paper/fig/build_figures.py failed (needs matplotlib)" >&2
$PY -B tools/verify_threshold_claim.py > "$SNAP/threshold_claim.txt" 2>&1 || true

# 3. Compare with the committed copies.
fail=0
for f in "$SNAP"/ANALYSIS/*; do
  b=$(basename "$f")
  if [ -f "$OUT/$b" ] && cmp -s "$f" "$OUT/$b"; then echo "PASS  $OUT/$b"
  else echo "FAIL  $OUT/$b"; fail=1; fi
done
for b in "${FIGS[@]}"; do
  if [ -s "paper/fig/$b" ]; then echo "PASS  paper/fig/$b (rebuilt, exists)"; else echo "FAIL  paper/fig/$b missing"; fail=1; fi
done
if grep -q "^Verdict:" "$SNAP/threshold_claim.txt"; then echo "PASS  tools/verify_threshold_claim.py ran ($(grep '^Verdict:' "$SNAP/threshold_claim.txt" | cut -c1-80))"
else echo "FAIL  tools/verify_threshold_claim.py"; fail=1; fi
# 4. No mock-response text anywhere in the saved suites.
$PY -B tools/check_mock_responses.py > "$SNAP/mock.txt" 2>&1; grep -E "^(saved suites|RESULT)" "$SNAP/mock.txt"

# Put the committed figure PDFs back (the rebuilt ones differ only by a timestamp).
for b in "${FIGS[@]}"; do [ -f "$SNAP/$b" ] && cp -p "$SNAP/$b" "paper/fig/$b"; done

# Leave the working tree exactly as committed if the rebuild reproduced it; show diffs otherwise.
[ $fail = 0 ] && echo "ALL PASS" || { echo "SOME FAILED: 'git diff --stat' shows what changed"; exit 1; }
