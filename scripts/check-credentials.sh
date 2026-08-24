#!/usr/bin/env bash
# Block secrets from entering the repository.
#
# Runs as a pre-commit hook and in CI. Scans what is actually STAGED, not the
# working tree, because that is what a commit will contain.
#
# The repo is public and git history is permanent: a key committed once is
# compromised even if the next commit removes it. This exists so that safety is
# mechanical rather than a thing someone has to remember.
set -euo pipefail

RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; OFF=$'\033[0m'
fail=0

staged=$(git diff --cached --name-only --diff-filter=ACM || true)
[ -z "$staged" ] && { echo "${GREEN}no staged files${OFF}"; exit 0; }

# --- 1. Files that must never be committed, whatever they contain -------------
# Matched by path. .gitignore already excludes these; this catches `git add -f`
# and any future gitignore edit that loosens them.
forbidden_paths='(^|/)\.env($|\.)|(^|/)\.[a-z-]*(agent|remember|assistant)[a-z-]*/|(^|/)_OPERATIONS/|service-account.*\.json$|\.pem$|\.p12$|(^|/)id_rsa'

while IFS= read -r f; do
  [ -z "$f" ] && continue
  if [[ "$f" =~ \.env\.example$ ]]; then continue; fi
  if echo "$f" | grep -qE "$forbidden_paths"; then
    echo "${RED}BLOCKED${OFF} $f — this path must never be committed"
    fail=1
  fi
done <<< "$staged"

# --- 2. Secret-shaped content in staged diffs ---------------------------------
# Each pattern targets a real credential format rather than the word "key", so
# documentation and variable names do not trip it.
declare -a patterns=(
  'AQ\.[A-Za-z0-9_-]{30,}'                      # Google AI Studio (newer form)
  'AIza[0-9A-Za-z_-]{30,}'                      # Google API key (classic form)
  'sk-[A-Za-z0-9]{20,}'                         # OpenAI-style
  'sk-ant-[A-Za-z0-9_-]{20,}'                   # vendor key prefix
  'ghp_[A-Za-z0-9]{30,}'                        # GitHub PAT
  'xox[baprs]-[A-Za-z0-9-]{10,}'                # Slack
  '-----BEGIN [A-Z ]*PRIVATE KEY-----'          # PEM private key
  '"private_key"[[:space:]]*:'                  # GCP service-account JSON
)

added=$(git diff --cached -U0 --diff-filter=ACM | grep '^+' | grep -v '^+++' || true)

for p in "${patterns[@]}"; do
  # `-e` is required: several patterns begin with '-' (e.g. the PEM header),
  # which grep would otherwise parse as an option.
  if echo "$added" | grep -qE -e "$p"; then
    echo "${RED}BLOCKED${OFF} staged content matches a credential pattern"
    # Never echo the match itself - that would print the secret into a log.
    echo "    pattern: ${p}"
    fail=1
  fi
done

# --- 3. A real value assigned to a known secret variable ----------------------
# Catches a key pasted into a variable name the patterns above do not cover.
# Placeholder values (as in .env.example) and empty assignments are allowed.
secret_vars='GEMINI_API_KEY|PARALLEL_API_KEY|GOOGLE_API_KEY|OPENAI_API_KEY|FIREBASE_PRIVATE_KEY'
assignments=$(echo "$added" | grep -E "^\+[[:space:]]*($secret_vars)[[:space:]]*=" || true)

if [ -n "$assignments" ]; then
  # A value counts as real when it is 12+ non-space characters and does not
  # look like a placeholder.
  real=$(echo "$assignments" \
    | grep -E '=[[:space:]]*[^[:space:]]{12,}' \
    | grep -viE 'your-|example|placeholder|changeme|xxx|dummy|fake|test-key|<' || true)
  if [ -n "$real" ]; then
    echo "${RED}BLOCKED${OFF} a secret variable is being assigned a real-looking value"
    echo "$real" | head -3 | sed 's/=.*/=<redacted>/' | sed 's/^/    /'
    fail=1
  fi
fi

if [ "$fail" -ne 0 ]; then
  cat <<EOM

${YELLOW}This repository is public and git history is permanent.${OFF}
A credential committed once is compromised even if a later commit removes it.

  * Put secrets in .env (gitignored). Document them in .env.example with
    placeholder values only.
  * If a real key has already been committed, ROTATE IT — removing the commit
    is not sufficient.

EOM
  exit 1
fi

echo "${GREEN}secret scan clean${OFF} ($(echo "$staged" | wc -l | tr -d ' ') staged files)"
