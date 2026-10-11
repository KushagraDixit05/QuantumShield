"""The one reason-mapping table (docs/api_contract.md). raw_reason is always kept by the caller."""
REASONS = ("bad_signature", "wrong_round", "norm_bound_exceeded", "bad_proof", "replay", "not_in_quorum", "other")

_TABLE = {
    "bad_signature": "bad_signature", "scheme_downgrade": "bad_signature", "unsigned": "bad_signature",
    "unknown_key": "bad_signature", "revoked_key": "bad_signature", "key_identity_mismatch": "bad_signature",
    "wrong_round": "wrong_round", "wrong_model_hash": "wrong_round",
    "norm_bound_exceeded": "norm_bound_exceeded",
    "replayed_nonce": "replay", "duplicate_submission": "replay",
    "stale_key": "replay",       # mapped to replay only because rejections.csv shows it with wrong_round on replay runs
    "not_in_quorum": "not_in_quorum",
}

_GATE = {"bad_signature": "signature", "wrong_round": "signature", "replay": "signature",
         "norm_bound_exceeded": "plaintext_norm_gate", "bad_proof": "zk", "not_in_quorum": "consensus"}


def map_reason(raw):
    """raw reason string from the code -> Reason category."""
    if raw.startswith("bad_proof:") or raw == "bad_proof":
        return "bad_proof"
    return _TABLE.get(raw, "other")


def gate_for(reason):
    # "other" covers commitment_mismatch / malformed / wrong_kind / no_proposal, all raised on the verification path
    return _GATE.get(reason, "signature")


def rejection(rnd, client, raw):
    reason = map_reason(raw)
    return {"round": int(rnd), "client": None if client is None else int(client), "reason": reason,
            "raw_reason": raw, "gate": gate_for(reason)}
