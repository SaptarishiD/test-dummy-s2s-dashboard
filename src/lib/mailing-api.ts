import { LIST, WORKER_URL } from "./mailing-config";

export type MailingResult = { ok: boolean; status: number; error?: string };

export interface TurnstileApi {
  render(
    element: HTMLElement,
    options: {
      sitekey: string;
      action: "subscribe";
      theme?: "light" | "dark" | "auto";
      callback: (token: string) => void;
      "expired-callback": () => void;
      "error-callback": () => void;
    },
  ): string;
  reset(widgetId?: string): void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const TURNSTILE_SRC =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
let turnstileLoading: Promise<TurnstileApi> | undefined;

/** Load the Turnstile script once; rejects (never fakes success) if it cannot load. */
export function loadTurnstile(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  turnstileLoading ??= new Promise<TurnstileApi>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = TURNSTILE_SRC;
    script.async = true;
    script.onload = () => {
      if (window.turnstile) resolve(window.turnstile);
      else reject(new Error("Turnstile loaded without an API"));
    };
    script.onerror = () => {
      turnstileLoading = undefined;
      reject(new Error("Turnstile script failed to load"));
    };
    document.head.append(script);
  });
  return turnstileLoading;
}

async function post(path: string, body: unknown): Promise<MailingResult> {
  const response = await fetch(`${WORKER_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(12000),
  });
  let error: string | undefined;
  try {
    error = ((await response.json()) as { error?: string }).error;
  } catch {
    // Non-JSON body: the HTTP status still decides the outcome.
  }
  return { ok: response.ok, status: response.status, error };
}

export const subscribe = (email: string, turnstileToken: string) =>
  post("/api/subscribe", { list: LIST, email, turnstileToken });

export const SERVICE_UNREACHABLE =
  "Could not reach the subscription service. Please check your connection and try again.";

export function subscribeMessage(result: MailingResult): string {
  if (result.ok) {
    return "If you already subscribe, no action is needed. Otherwise, check your inbox for a recent link, open it within 48 hours, and press Confirm subscription.";
  }
  switch (result.error) {
    case "invalid-email":
      return "That does not look like a valid email address.";
    case "turnstile-failed":
      return "The verification check failed. Please try again.";
    case "unknown-list":
      return "Email subscriptions are not open yet. Please check back soon.";
    case "rate-limited":
      return "Too many attempts. Please wait a minute and try again.";
    default:
      return `Something went wrong (HTTP ${result.status}). Please try again later.`;
  }
}
