import type { Gate, Reason, Rejection } from "@/lib/api";

export const REASON_LABEL: Record<Reason, string> = {
  bad_signature: "bad signature",
  wrong_round: "wrong round",
  norm_bound_exceeded: "plaintext norm gate (not ZK)",
  bad_proof: "failed proof",
  replay: "replay",
  not_in_quorum: "not in quorum",
  other: "other",
};
export const REASONS = Object.keys(REASON_LABEL) as Reason[];

const GATE: Record<Reason, Gate> = {
  bad_signature: "signature",
  wrong_round: "signature",
  norm_bound_exceeded: "plaintext_norm_gate",
  bad_proof: "zk",
  replay: "signature",
  not_in_quorum: "consensus",
  other: "signature",
};

/**
 * Category of a raw reason string from a stored CSV (the stored file has no category column).
 * Mirrors the mapping table in docs/api_contract.md; the raw string is always shown beside it.
 */
export function categorize(raw: string): Reason {
  if (["bad_signature", "scheme_downgrade", "unsigned", "unknown_key", "revoked_key", "key_identity_mismatch"].includes(raw)) return "bad_signature";
  if (raw === "wrong_round" || raw === "wrong_model_hash") return "wrong_round";
  if (raw === "norm_bound_exceeded") return "norm_bound_exceeded";
  if (raw.startsWith("bad_proof")) return "bad_proof";
  if (["replayed_nonce", "duplicate_submission", "stale_key"].includes(raw)) return "replay";
  if (raw === "not_in_quorum") return "not_in_quorum";
  return "other";
}

export interface LogRow extends Rejection {
  seed: number | null;
  /** attack/defence of the stored run (stored view only). */
  scenario?: string;
}

export function storedRow(r: Record<string, string | number | boolean | null>): LogRow {
  const raw = String(r.reason ?? "");
  const reason = categorize(raw);
  return {
    round: Number(r.round),
    client: typeof r.client === "number" ? r.client : null,
    seed: typeof r.seed === "number" ? r.seed : null,
    reason,
    raw_reason: raw,
    gate: GATE[reason],
    scenario: `${r.attack ?? "?"} / defence ${r.defence ?? "?"}`,
  };
}
