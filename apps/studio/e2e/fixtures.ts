import path from 'node:path';
import fs from 'node:fs';

/**
 * Absolute paths to the committed `.riv` fixtures.
 *
 * These MUST be absolute. `setInputFiles` and `fs.readFileSync` resolve a
 * relative path against the process working directory, not the spec file, so
 * bare `'public/riv/x.riv'` only worked when the suite happened to be launched
 * from `apps/studio`. Run the documented command from the repo root and every
 * one of those specs failed with ENOENT — a suite that passes or fails on where
 * you happened to be standing is not a suite.
 */
// `__dirname`, not `import.meta.url`: Playwright transpiles specs to CommonJS,
// where `import.meta` is a syntax error.
const RIV_DIR = path.resolve(__dirname, '..', 'public', 'riv');

/** Absolute path to a fixture, checked at call time so a typo names itself. */
export function riv(name: string): string {
  const p = path.join(RIV_DIR, name);
  if (!fs.existsSync(p)) {
    throw new Error(`fixture not found: ${p} (looked for "${name}" in ${RIV_DIR})`);
  }
  return p;
}

/** A fixture's bytes, for the specs that hand a buffer to the page. */
export function rivBytes(name: string): Buffer {
  return fs.readFileSync(riv(name));
}

/**
 * Absolute path to a directory for test artifacts (screenshots, frames).
 *
 * Absolute for the same reason the fixtures are: a relative path resolves
 * against the working directory, so running the documented command from the
 * repo root scattered `camera-frames/` and `ui-shots/` into the root — outside
 * the .gitignore rules written for them, and one `git add -A` from being
 * committed.
 */
export function artifactDir(name: string): string {
  const dir = path.resolve(__dirname, '..', name);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}
