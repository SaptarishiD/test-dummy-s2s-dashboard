/** Mailing-list settings: the only place the Worker URL, Turnstile key and list slug live. */

export const WORKER_URL = "https://s2s-mailing-list.s2s-ashoka.workers.dev";

/**
 * Production Turnstile site key (widget for s2s.scdlds.com; public by design).
 */
export const TURNSTILE_SITE_KEY = "0x4AAAAAAGNon9SM2DBFSs6e";

/** Hidden test list while the signup flow is being tested; switch to "s2s" to go live. */
export const LIST = "s2s-test";
