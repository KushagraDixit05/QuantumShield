# gaps-X (certificates)

## Done
- `tests/hardening/test_certificates.py`: `.venv/bin/python -m pytest tests/hardening -q` -> `20 passed, 1 warning in 2.71s` (no proving; scenario C seed 0, 6 rounds, plus a seed-1 2-round run).
- `tests/e2e/certificates/certificates.spec.ts`: `cd tests/e2e && npx playwright test certificates/` -> `4 passed (25.3s)`.

## pytest checks
untouched_certificate_valid_for_every_round (6 rounds, incl. epoch-1 round 5; GET-cert verdict == stored-round verdict), signature_flipped (node 2 bad_signature, quorum_met true, valid false), second_signature_of_hybrid_flipped, payload_hash_changed, all_votes_payload_changed (valid false, quorum false), fewer_than_three_votes (2, 1, 0 votes), three_votes_is_exactly_quorum, same_voter_duplicated_to_fake_three_votes (copy 1 ok, copies 2+ `replayed_nonce`, quorum false), two_voters_duplicated_to_fake_three, vote_from_unknown_node_id (relabelled node 9, and extra node-9 vote), payload_agg_id_rewritten_to_unknown_node, round_field_changed (0->1, 1->0, 2->5, 5->0: invalid, quorum false), votes_from_two_rounds_mixed, certificate_from_different_run_pasted_under_this_run_id (both directions; seed-1 certs valid under their own run as control), unknown_run_id_in_pasted_certificate (404), keys_in_the_paste_are_ignored (attacker-signed votes with the attacker's registry in the paste at several places: invalid; genuine cert with junk key fields still valid), key_rotation_epoch_round (rounds 4 and 5 valid; cross-labelling 5<->4 invalid), malformed_input_reported_not_crashed, handler_never_references_secret_keys (comment/docstring-stripped source of backend/certificates.py and the two handlers in backend/main.py contain no `sk`/`_sk`/`secret`), response_and_snapshot_carry_no_secret_fields. `public_keys_only` is asserted true on every verify response.

## Playwright checks
(a) untouched: UI valid + quorum met + "Checked with public keys only" on rounds 0-2, and UI {valid, quorum_met, checked[]} equals POST verify of the GET certificate; stored-round POST gives the same verdict.
(b) control: route handler sees the button's POST body `{run_id, round}`, passes it through, UI valid == backend; second control substitutes the untouched GET certificate via route: still valid.
(c) tampered signature (node 2, round 1) via page.route body substitution: response is 200 (no 4xx), the on-wire verdict equals a direct backend call, UI shows "not valid", exactly one rejected row = node 2 with `bad_signature`, three ok rows, other rounds untouched.
(d) fewer than 3 votes via route: UI "not valid" + "quorum not met", equals backend.
Each test asserts `problems` (minus SSE_ABORT) is empty. No test.skip.

## Blocked
None.

## Needs
- Nothing from lead. Note: UI limitation (cannot edit/paste certificates) is stated in the spec header comment.

## Findings
- No real defect found. Observation: keys are deterministic per seed, so a certificate from a different run with the same seed verifies under another run id (same registry, same votes); a different-seed certificate is rejected. Not treated as a bug.
- Duplicated voter is flagged by the verifier as `replayed_nonce` (not a separate "duplicate" reason); quorum counts distinct nodes.
