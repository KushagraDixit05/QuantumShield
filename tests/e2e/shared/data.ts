// Ground truth loaders. Every expected number in an e2e check comes from one of these files; nothing is typed in.
import { readFileSync } from "node:fs";
import path from "node:path";
import { ROOT } from "./config";

const read = (rel: string) => readFileSync(path.join(ROOT, rel), "utf8");

export function readCsv(rel: string): Record<string, string>[] {
  const [head, ...lines] = read(rel).trim().split(/\r?\n/);
  const cols = head.split(",");
  return lines.map((l) => Object.fromEntries(l.split(",").map((v, i) => [cols[i], v])));
}

export type ScenarioRow = { attack: string; defence: string; seed: number; final_acc: number; diverged_round: number | null; finalized_rounds: number; rejected: number };
export const SCENARIOS_CSV = "demo/results/scenarios.csv";
export const SCENARIOS_JSON = "demo/results/scenarios.json";
export const REJECTIONS_CSV = "demo/results/rejections.csv";

export function scenarioRows(): ScenarioRow[] {
  return readCsv(SCENARIOS_CSV).map((r) => ({
    attack: r.attack, defence: r.defence, seed: Number(r.seed), final_acc: Number(r.final_acc),
    diverged_round: r.diverged_round === "" ? null : Number(r.diverged_round),
    finalized_rounds: Number(r.finalized_rounds), rejected: Number(r.rejected),
  }));
}

/** Seed-0 curves. Index 0 is the untrained model; round r of a run is index r + 1. Values are rounded to 6 dp; after
 *  divergence the stored curve holds 0.0 (D-012 convention), which the UI must show as DIVERGED, never as a number. */
export function curves(): { rounds: number; seed: number; all: Record<string, number[]> } {
  return JSON.parse(read(SCENARIOS_JSON));
}

export type RejRow = { attack: string; defence: string; seed: number; round: number; client: number; reason: string };
export function storedRejections(): RejRow[] {
  return readCsv(REJECTIONS_CSV).map((r) => ({ attack: r.attack, defence: r.defence, seed: Number(r.seed), round: Number(r.round), client: Number(r.client), reason: r.reason }));
}

/** The presets exactly as demo/run_demo.py:158 defines them. */
export const PRESETS = { A: { attack: "none", defence: "off" }, B: { attack: "scaled", defence: "off" }, C: { attack: "scaled", defence: "on" } } as const;

// Tolerances (docs/e2e_map.md). The UI prints accuracies with toFixed(4).
export const TOL_DISPLAY_VS_6DP = 0.00005 + 1e-9; // 4-dp display vs 6-dp stored curve
export const TOL_EXACT = 1e-9;                     // 4-dp display vs 4-dp CSV, or UI vs backend value at the same precision

export const mean = (a: number[]) => a.reduce((s, x) => s + x, 0) / a.length;
export const sampleStd = (a: number[]) => (a.length < 2 ? NaN : Math.sqrt(a.reduce((s, x) => s + (x - mean(a)) ** 2, 0) / (a.length - 1)));
export const populationStd = (a: number[]) => Math.sqrt(a.reduce((s, x) => s + (x - mean(a)) ** 2, 0) / a.length);
