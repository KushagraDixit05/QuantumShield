"""Table of the MVP attacks: name -> {kind, builder, expected_reason_prefix, ...}.

builder(session, t, client, delta, **ctx) -> (env, delta_received, receipt) = what the aggregator receives.
`expected_reason_prefix` is the reason string Verifier.verify_envelope really returns (checked by
tests/test_attacks.py). `needs` lists the setup a test must provide. Attacks never prove anything.
"""
from . import envelope_attacks as ea
from . import poison


def _scaled(session, t, client, delta, s=50, **_):
    """Poisoned update signed with the attacker's OWN valid key and no proof (it cannot make one: the
    guest rejects the norm bound). Under a ZkPolicy verifier (v1 envelope, no proof_hash): bad_proof:missing_proof_hash (missing_receipt if it signed a hash but sent no receipt). The plain norm
    check (fl.aggregate.accepted_by_norm) also rejects it."""
    d = poison.scaled(delta, s)
    return session.client_envelope(t, client, d), d, None


def _forged(session, t, client, delta, stripped=False, **_):
    """Victim's Ed25519 key only. Junk PQ signature -> bad_signature; stripped (Ed25519 alone) -> scheme_downgrade."""
    env, d = ea.forge_with_classical_key(session, client, t, poison.scaled(delta, 3), stripped=stripped)
    return env, d, None


def _replay(session, t, client, delta, env=None, **_):
    """The old envelope resent verbatim (`env`): wrong_round in a later round, replayed_nonce if resent
    in the same round after it was admitted."""
    return env, delta, None


def _swap(session, t, client, delta, receipt_a=None, hash_matches=True, **_):
    return ea.swap_proof(session, t, client, delta, receipt_a, hash_matches)


ATTACKS = {
    "scaled": dict(kind="poison", builder=_scaled, expected_reason_prefix="bad_proof:missing_proof_hash",
                   needs="ZkPolicy verifier; plain norm check also rejects", mode="hybrid"),
    "forged": dict(kind="envelope", builder=_forged, expected_reason_prefix="bad_signature",
                   variants={"stripped": "scheme_downgrade"}, needs="pq or hybrid verifier; accepted under classical"),
    "replay": dict(kind="envelope", builder=_replay, expected_reason_prefix="wrong_round",
                   variants={"same_round": "replayed_nonce"}, needs="a previously admitted envelope"),
    "swap": dict(kind="envelope", builder=_swap, expected_reason_prefix="bad_proof:journal_mismatch",
                 variants={"hash_mismatch": "bad_proof:hash_mismatch"}, needs="ZkPolicy verifier, another client's receipt"),
}
