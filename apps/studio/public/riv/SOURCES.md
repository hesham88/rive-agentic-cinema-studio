# Fixture sources

Test fixtures for the inspector's Playwright suite. All are real `.riv` binaries.

| File | Source | Notes |
| --- | --- | --- |
| `sample.riv` | https://cdn.rive.app/animations/vehicles.riv | Rive's own public sample. Primary fixture, referenced by `e2e/inspector.spec.ts`. |
| `juice_v7.riv` | https://cdn.rive.app/animations/juice_v7.riv | Second fixture, smaller. |
| `corrupt.riv` | generated locally | Deliberately invalid — the literal bytes `not a rive file`. Proves the parse-error path. |

These come from Rive's public CDN rather than the Marketplace, so no account or
license acceptance is involved. Replace or supplement with Marketplace files in
slice 2, recording their licenses here.
