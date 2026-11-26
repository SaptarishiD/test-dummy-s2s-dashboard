import { mountSubscribeBox } from "../components/SubscribeBox";

/** Stand-alone Subscribe page (#subscribe): the email sign-up form on its own. */
export function renderSubscribePage(container: HTMLElement): void {
  container.innerHTML = `
    <section class="subscribe-page" aria-label="Subscribe">
      <div class="subscribe-card" id="subscribe-box"></div>
    </section>
  `;
  mountSubscribeBox(container.querySelector<HTMLElement>("#subscribe-box")!);
}
