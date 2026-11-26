import { TURNSTILE_SITE_KEY } from "../lib/mailing-config";
import {
  loadTurnstile,
  SERVICE_UNREACHABLE,
  subscribe,
  subscribeMessage,
} from "../lib/mailing-api";

const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
let boxCount = 0;

/** "Get the forecast by email" form. The Turnstile widget is loaded on first focus of the email field. */
export function mountSubscribeBox(host: HTMLElement): void {
  const id = `mailing-box-${++boxCount}`;
  host.innerHTML = `
    <form class="mailing-box" novalidate aria-labelledby="${id}-title">
      <div class="mailing-box__intro">
        <h2 class="mailing-box__title" id="${id}-title">Get the forecast by email</h2>
        <p>The S2S forecast briefing in your inbox. Confirm by email. Each issue includes an unsubscribe link.</p>
      </div>
      <div class="mailing-box__form">
        <div class="mailing-box__row">
          <label class="ops-visually-hidden" for="${id}-email">Email address</label>
          <input id="${id}-email" class="mailing-box__input" type="email" name="email"
            autocomplete="email" inputmode="email" placeholder="Your email address" required />
          <button class="mailing-box__button" type="submit">Subscribe</button>
        </div>
        <div class="mailing-box__turnstile" hidden></div>
        <p class="mailing-box__message" role="status" aria-live="polite"></p>
      </div>
    </form>
  `;
  const form = host.querySelector<HTMLFormElement>("form")!;
  const input = form.querySelector<HTMLInputElement>("input")!;
  const button = form.querySelector<HTMLButtonElement>("button")!;
  const widgetHost = form.querySelector<HTMLElement>(".mailing-box__turnstile")!;
  const message = form.querySelector<HTMLElement>(".mailing-box__message")!;

  let token = "";
  let widgetId: string | undefined;
  let widgetStarted = false;

  const show = (text: string, kind: "ok" | "error" | "info") => {
    message.textContent = text;
    message.dataset.kind = kind;
  };

  const startWidget = async () => {
    if (widgetStarted) return;
    widgetStarted = true;
    try {
      const turnstile = await loadTurnstile();
      widgetHost.hidden = false;
      widgetId = turnstile.render(widgetHost, {
        sitekey: TURNSTILE_SITE_KEY,
        action: "subscribe",
        theme: "light",
        callback: (value) => { token = value; },
        "expired-callback": () => { token = ""; },
        "error-callback": () => {
          token = "";
          show("The verification check failed to run. Reload the page and try again.", "error");
        },
      });
    } catch {
      widgetStarted = false;
      show("The verification check could not be loaded (a blocker or network issue). Reload the page and try again.", "error");
    }
  };

  input.addEventListener("focus", () => { void startWidget(); });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = input.value.trim();
    if (!EMAIL_SHAPE.test(email)) {
      show("Enter a valid email address.", "error");
      input.focus();
      return;
    }
    if (!token) {
      void startWidget();
      show("Please wait for the verification check to finish, then press Subscribe again.", "info");
      return;
    }
    button.disabled = true;
    form.setAttribute("aria-busy", "true");
    show("Sending…", "info");
    try {
      const result = await subscribe(email, token);
      show(subscribeMessage(result), result.ok ? "ok" : "error");
      if (result.ok) input.value = "";
    } catch {
      show(SERVICE_UNREACHABLE, "error");
    } finally {
      token = "";
      if (widgetId !== undefined) window.turnstile?.reset(widgetId);
      button.disabled = false;
      form.removeAttribute("aria-busy");
    }
  });
}
