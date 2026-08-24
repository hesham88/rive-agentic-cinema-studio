# Environments

Two environments, one build. Development runs locally with no cloud account;
production is a static CDN deploy on Firebase with Firebase Auth.

## Development — local, no account required

```bash
npm install
npm run dev            # Next dev server on http://localhost:3000
```

The studio's core function — load a `.riv`, enumerate it, drive its inputs —
needs **no authentication and no network**. `isFirebaseConfigured()` returns
false when the `NEXT_PUBLIC_FIREBASE_*` variables are absent, and the app runs
in open local mode rather than erroring. That is deliberate: a contributor
should be able to clone and run without provisioning anything.

### The authoring pipeline (separate from the app)

```bash
cd tools/genassets && pip install -e .
python -m genassets.agent.run "a flat-vector rocket icon in three colours"
```

Needs `GEMINI_API_KEY` and `PARALLEL_API_KEY` in `.env` at the repo root
(gitignored; see `.env.example`). The Rive MCP server additionally requires the
Rive desktop app to be **running with a file open** — it is authoring-time
tooling and is never a dependency of the deployed app.

### Tests

```bash
npm test                 # engine unit tests (Vitest)
npm run test:e2e         # browser tests against real .riv files (Playwright)
python -m pytest tools/genassets/tests/   # pipeline tests
```

Playwright runs `workers: 1` on purpose — every test mounts a WebGL context and
a WASM runtime, and parallel workers starve each other into timeouts that look
like product bugs.

## Preview — production build, served locally

```bash
npm run preview          # static build + Firebase hosting emulator on :5000
npm run emulate          # emulator suite: auth :9099, hosting :5000, UI :4000
```

Set `NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST=localhost:9099` in `.env.local` and
the client attaches to the auth emulator, so sign-in flows are exercised without
touching real accounts.

## Production — Firebase Hosting

```bash
npm run deploy           # next build (static export) + firebase deploy
```

**Why Hosting and not App Hosting:** `next build` reports every route as
`Static`, so there is no server to run. The app is a CDN artifact. Firebase Auth
is client-side, so authentication works unchanged on a static host — and a CDN
deploy is cheaper, faster, and has no cold start.

`firebase.json` sets immutable one-year cache headers on `.riv`, `.wasm`, `.js`,
`.css` and `.woff2`. Those are content-addressed or versioned, and the `.riv`
and `.wasm` payloads are the bulk of the transfer.

### Required configuration

Set in `.env.local` for local production builds, and in the Firebase console or
CI for real deploys:

```
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
NEXT_PUBLIC_FIREBASE_PROJECT_ID=
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=
NEXT_PUBLIC_FIREBASE_APP_ID=
```

These are `NEXT_PUBLIC_*` and therefore shipped to the browser — that is correct
for Firebase client config, which is not secret. Access is controlled by Firebase
security rules and authorised domains, not by hiding these values. **Server-side
keys (`GEMINI_API_KEY`, `PARALLEL_API_KEY`) must never be given a
`NEXT_PUBLIC_` prefix**, or they would be embedded in the bundle.

## What deploys and what does not

| Component | Deploys? |
| --- | --- |
| `apps/studio` (the runtime) | **Yes** — static CDN |
| `packages/rive-engine` | Yes, compiled into the app |
| `.riv` assets | Yes, as static files |
| `tools/genassets` (Gemini, Parallel, tracer) | **No** — local authoring |
| Rive MCP server | **No** — local, session-bound |

This split is the project's central constraint: authoring produces `.riv` files,
the runtime consumes them, and nothing in the deployed app depends on the
editor being open.

## Secrets

`scripts/check-secrets.sh` runs before every commit via `.githooks/pre-commit`.
Enable it after cloning:

```bash
git config core.hooksPath .githooks
```

It scans what is **staged**, not the working tree, because that is what a commit
will contain. Three layers:

1. **Forbidden paths** — `.env`, agent tooling directories, `_OPERATIONS/`,
   service-account JSON, `.pem`, `.p12`, `id_rsa`. Caught by path, so a
   `git add -f` or a loosened `.gitignore` cannot get around it.
2. **Credential-shaped content** — Google (`AQ.`/`AIza`), and other vendor
   GitHub, Slack tokens, PEM private keys, GCP service-account JSON. The match
   itself is never printed; a scanner that echoes the secret into CI logs has
   leaked it.
3. **Real values on secret variables** — a 12+ character value assigned to
   `GEMINI_API_KEY` and friends. Placeholders (`your-…`, `example`, `<…>`) pass,
   which is what keeps `.env.example` committable.

Verified against three cases: a real key is blocked, a `_OPERATIONS/` path is
blocked, and `.env.example` placeholders are allowed.

**If a real key is ever committed, rotate it.** Removing the commit does not
help — the repository is public and history is permanent.
