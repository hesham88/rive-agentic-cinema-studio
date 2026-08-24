/**
 * The one place production is named.
 *
 * This exists because it was once named in two places and they disagreed: a
 * deploy went to a different Firebase project entirely, and the test written
 * against it hardcoded that wrong host, so the suite happily verified the wrong
 * site while the real one sat untouched. A single exported constant makes that
 * particular failure impossible.
 *
 * It must match `.firebaserc`'s default project, which is the project the
 * `deploy` script pins with `--project`.
 */
export const PROD_URL = 'https://rive-agentic-studio.web.app';
