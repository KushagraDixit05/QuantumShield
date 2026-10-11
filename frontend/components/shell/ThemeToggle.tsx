"use client";
import { useSyncExternalStore } from "react";

const EVT = "qs-theme-change";
function subscribe(cb: () => void) {
  window.addEventListener(EVT, cb);
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", cb);
  return () => {
    window.removeEventListener(EVT, cb);
    mq.removeEventListener("change", cb);
  };
}
function current(): "light" | "dark" {
  const set = document.documentElement.getAttribute("data-theme");
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, current, () => "light" as const);
  const next = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      className="qs-btn"
      suppressHydrationWarning
      aria-label={`Switch to ${next} theme`}
      onClick={() => {
        document.documentElement.setAttribute("data-theme", next);
        try {
          localStorage.setItem("qs-theme", next);
        } catch {
          /* storage unavailable: choice lasts for this page view */
        }
        window.dispatchEvent(new Event(EVT));
      }}
    >
      <span suppressHydrationWarning>{theme === "dark" ? "Dark" : "Light"}</span> theme
    </button>
  );
}
