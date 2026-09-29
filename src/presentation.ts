import "./styles/presentation.css";

const slides = Array.from(document.querySelectorAll<HTMLElement>(".slide"));
const counter = document.querySelector<HTMLElement>("#slide-counter")!;
const progress = document.querySelector<HTMLElement>("#slide-progress")!;
let current = 0;
let touchStartX: number | undefined;

function indexFromHash(): number {
  const match = window.location.hash.match(/^#slide-(\d+)$/);
  if (!match) return 0;
  return Math.max(0, Math.min(slides.length - 1, Number(match[1]) - 1));
}

function show(index: number, updateHistory = true): void {
  current = Math.max(0, Math.min(slides.length - 1, index));
  slides.forEach((slide, slideIndex) => {
    const active = slideIndex === current;
    slide.classList.toggle("is-active", active);
    slide.hidden = !active;
    slide.setAttribute("aria-hidden", String(!active));
  });
  counter.textContent = `${current + 1} / ${slides.length}`;
  progress.style.width = `${((current + 1) / slides.length) * 100}%`;
  document.title = `${slides[current].dataset.title} · FuXi Extremes`;
  if (updateHistory) {
    window.history.replaceState(null, "", `#slide-${current + 1}`);
  }
  slides[current].focus({ preventScroll: true });
}

function toggleFullscreen(): void {
  if (document.fullscreenElement) {
    void document.exitFullscreen();
  } else {
    void document.documentElement.requestFullscreen();
  }
}

document.querySelectorAll<HTMLButtonElement>("[data-action]").forEach((button) => {
  button.addEventListener("click", () => {
    if (button.dataset.action === "previous") show(current - 1);
    if (button.dataset.action === "next") show(current + 1);
    if (button.dataset.action === "fullscreen") toggleFullscreen();
  });
});

window.addEventListener("keydown", (event) => {
  if (["ArrowRight", "PageDown", " "].includes(event.key)) {
    event.preventDefault();
    show(current + 1);
  }
  if (["ArrowLeft", "PageUp"].includes(event.key)) {
    event.preventDefault();
    show(current - 1);
  }
  if (event.key === "Home") show(0);
  if (event.key === "End") show(slides.length - 1);
  if (event.key.toLowerCase() === "f") toggleFullscreen();
});

window.addEventListener("hashchange", () => show(indexFromHash(), false));
window.addEventListener("touchstart", (event) => {
  touchStartX = event.changedTouches[0]?.clientX;
}, { passive: true });
window.addEventListener("touchend", (event) => {
  if (touchStartX === undefined) return;
  const distance = (event.changedTouches[0]?.clientX ?? touchStartX) - touchStartX;
  touchStartX = undefined;
  if (Math.abs(distance) < 50) return;
  show(current + (distance < 0 ? 1 : -1));
}, { passive: true });

slides.forEach((slide) => {
  slide.tabIndex = -1;
});
show(indexFromHash(), false);
