/**
 * Colour tokens. Categorical + sequential values come from the dataviz skill's reference palette
 * (validated there for adjacent-pair CVD separation). The diverging arms are hand-stepped from the
 * same blue / red hues and have NOT been run through the validator; if F2 relies on them for
 * anything beyond a heatmap with printed cell values, validate first.
 * The same values exist as CSS custom properties in app/globals.css (--series-N, --seq-N, ...).
 */
export type Mode = "light" | "dark";

export const SERIES: Record<Mode, string[]> = {
  light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
  dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
};
/** CSS references for charts: stable across themes, follow the data-theme / media query. */
export const seriesVar = (i: number) => `var(--series-${(i % 8) + 1})`;

/** Sequential, one hue (blue), light -> dark, 7 steps. Light end = low value. */
export const SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];

/** Diverging: red (negative) <- gray midpoint -> blue (positive), equal arm length. */
export const DIVERGING: Record<Mode, string[]> = {
  light: ["#9e2a2b", "#d03b3b", "#e66767", "#f4b0a8", "#f0efec", "#b7d3f6", "#6da7ec", "#256abf", "#104281"],
  dark: ["#e66767", "#d03b3b", "#a8302f", "#6b2a29", "#383835", "#1c4a82", "#256abf", "#3987e5", "#86b6ef"],
};

/** t in [0,1] -> sequential step (0 = lightest). Values outside are clamped. */
export function sequentialColor(t: number): string {
  const c = Math.min(1, Math.max(0, t));
  return SEQUENTIAL[Math.round(c * (SEQUENTIAL.length - 1))];
}
/** t in [-1,1] -> diverging step; 0 is the gray midpoint. */
export function divergingColor(t: number, mode: Mode = "light"): string {
  const arr = DIVERGING[mode];
  const c = Math.min(1, Math.max(-1, t));
  return arr[Math.round(((c + 1) / 2) * (arr.length - 1))];
}

/** Sequential steps are light->dark, so ink on a cell must flip: true when text should be white. */
export const sequentialNeedsLightText = (t: number): boolean => Math.round(Math.min(1, Math.max(0, t)) * 6) >= 3;

/** Reserved status colours (never use as series). Always pair with an icon + label. */
export const STATUS = { good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b" } as const;

/**
 * Diverged cells/points are NOT on any value scale. Use the neutral hatched fill (CSS class
 * `.qs-diverged-fill`) and the DivergedMarker component, never a scale colour.
 */
export const DIVERGED_CSS_VAR = "var(--diverged)";
