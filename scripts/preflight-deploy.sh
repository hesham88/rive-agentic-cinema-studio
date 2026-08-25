#!/usr/bin/env bash
# Runs before `npm run deploy`.
#
# Two things are checked, both of which have actually gone wrong here:
#
#   1. The Firebase CLI is not a declared dependency — `npm run deploy` calls a
#      globally installed binary. A fresh clone therefore fails at the last
#      step, after a full build, with a bare "command not found".
#
#   2. The CLI keeps a MACHINE-LOCAL active project that silently overrides
#      .firebaserc. On this machine it points somewhere else entirely. The
#      deploy script pins `--project rive-agentic-studio`, which wins — but the
#      failure mode is a human running a bare `firebase deploy` instead, which
#      has already published this site over an unrelated project and destroyed
#      it. This prints both, side by side, before anything is built.
set -euo pipefail

BOLD=$'\033[1m'; RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; OFF=$'\033[0m'
EXPECTED=rive-agentic-studio

if ! command -v firebase > /dev/null 2>&1; then
  cat <<EOM
${RED}firebase CLI not found${OFF}

`npm run deploy` needs it, and it is deliberately not a dependency of this
repo — it is ~200MB and only the owner deploys. Install it once:

    npm install -g firebase-tools
    firebase login

EOM
  exit 1
fi

echo "${BOLD}deploy preflight${OFF}"
echo "  firebase CLI   $(firebase --version 2>/dev/null | head -1)"
# .firebaserc has no .json extension, so `require` cannot infer its type.
echo "  .firebaserc    $(node -e "console.log(JSON.parse(require('fs').readFileSync('.firebaserc','utf8')).projects.default)" 2>/dev/null || echo '?')"

active=$(firebase use 2>/dev/null | head -1 || true)
echo "  CLI active     ${active:-<none>}"
echo "  pinned target  ${GREEN}${EXPECTED}${OFF}  (via --project)"

if [ -n "$active" ] && ! echo "$active" | grep -q "$EXPECTED"; then
  echo
  echo "${YELLOW}note${OFF} the CLI's active project is NOT ${EXPECTED}."
  echo "     That is survivable here because the deploy pins --project, but it"
  echo "     is exactly why a bare \`firebase deploy\` must never be run."
fi

echo
echo "After the deploy, read the ${BOLD}hosting[...]${OFF} target in the output."
echo "It must read ${GREEN}hosting[${EXPECTED}]${OFF}."
echo
