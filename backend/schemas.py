from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

Attack = Literal["none", "scaled", "forged", "replay"]
Aggregator = Literal["fedavg", "norm_filter", "median", "clip"]
Reason = Literal["bad_signature", "wrong_round", "norm_bound_exceeded", "bad_proof", "replay", "not_in_quorum", "other"]


class Rejection(BaseModel):
    round: int
    client: Optional[int]
    reason: Reason
    raw_reason: str
    gate: Literal["signature", "plaintext_norm_gate", "zk", "consensus"]


class Scenario(BaseModel):
    id: Literal["A", "B", "C"]
    label: str
    attack: Literal["none", "scaled"]
    defence: Literal["off", "on"]
    description: str


class ScenariosResponse(BaseModel):
    source: list[str]
    scenarios: list[Scenario]
    attacks: list[Attack]
    aggregators: list[Aggregator]
    default_seeds: list[int]
    default_rounds: int
    live_zk_enabled: Literal[False] = False


class RunRequest(BaseModel):
    scenario: Optional[Literal["A", "B", "C"]] = None
    attack: Optional[Attack] = None
    defence: Optional[Literal["on", "off"]] = None
    aggregator: Aggregator = "fedavg"
    seeds: list[int] = Field(..., min_length=1, max_length=5)
    rounds: Optional[int] = Field(None, ge=1, le=50)
    live_zk: bool = False

    @model_validator(mode="after")
    def _check(self):
        if self.scenario is None and (self.attack is None or self.defence is None):
            raise ValueError("give either scenario, or both attack and defence")
        if any(s < 0 or s > 10**6 for s in self.seeds):
            raise ValueError("each seed must be in 0..1000000")
        return self


class RunCreated(BaseModel):
    id: str
    queue_position: int


class ResultsResponse(BaseModel):
    name: str
    source: list[str]
    columns: list[str]
    rows: list[dict[str, Any]]
    json_: Optional[dict[str, Any]] = Field(None, alias="json")
    markdown: Optional[str] = None
    diverged_note: Optional[dict[str, str]] = None

    model_config = {"populate_by_name": True}


class ConsensusVote(BaseModel):
    node: int
    signer_alg: str
    hash: str
    valid: bool


class ConsensusRound(BaseModel):
    round: int
    model_hash: Optional[str]
    votes: list[ConsensusVote]
    finalized: bool
    equivocators: list[int]
    bad_votes: int
    certificate_id: Optional[str]


class ConsensusResponse(BaseModel):
    run_id: str
    seed: int
    seeds_available: list[int]
    n: int
    f: int
    quorum: int
    leader: int
    leader_policy: str
    view_changes: list[Any]
    view_changes_note: str
    rounds: list[ConsensusRound]


class CertVote(BaseModel):
    node: int
    payload: str
    sigs: list[dict[str, str]]


class Certificate(BaseModel):
    run_id: str
    seed: Optional[int] = None
    round: int
    votes: list[CertVote]
    certificate_id: Optional[str] = None


class VerifyRequest(BaseModel):
    run_id: Optional[str] = None
    round: Optional[int] = None
    seed: Optional[int] = None
    certificate: Optional[Certificate] = None

    @model_validator(mode="after")
    def _check(self):
        if self.certificate is None and (self.run_id is None or self.round is None):
            raise ValueError("give run_id and round, or a certificate")
        return self


class CheckedVote(BaseModel):
    node: Optional[int]
    ok: bool
    reason: str


class VerifyResponse(BaseModel):
    valid: bool
    quorum_met: bool
    checked: list[CheckedVote]
    public_keys_only: Literal[True] = True
    source: str


class Health(BaseModel):
    ok: bool
    live_zk_enabled: Literal[False] = False
    prover_lock_held: bool
    queue_length: int


class LimitationItem(BaseModel):
    n: int
    text: str


class LimitationSection(BaseModel):
    title: str
    items: list[LimitationItem]


class LimitationsResponse(BaseModel):
    source: str
    sections: list[LimitationSection]


class Hardware(BaseModel):
    cpu: Optional[str]
    threads: Optional[int]
    ram: Optional[str]
    os: Optional[str]
    gpu_used: Literal[False] = False
    zkvm: Optional[str]
    source: str
    note: Optional[str] = None


class Receipt(BaseModel):
    id: str
    path: str
    bytes: int
    generated: str
    journal_bytes: int
    round: Optional[int]
    client: Optional[int]
    image_id: Optional[str]
    prove_s: Optional[float]
    cycles: Optional[int]
    peak_rss_mb: Optional[float]
    verified: Optional[bool]
    verify_s: Optional[float]
    verify_error: Optional[str]
    replayed: Literal[True] = True
    label: str


class ReceiptsResponse(BaseModel):
    source: list[str]
    hardware: Hardware
    receipts: list[Receipt]


class ZkRound(BaseModel):
    round: int
    client: int
    role: str
    status: Literal["verified", "no_receipt", "rejected", "unverified"]
    reason: Optional[str]
    receipt_id: Optional[str]
    label: str
    replayed: Literal[True] = True
    consensus_accuracy: Optional[float] = None
    consensus_model_hash: Optional[str] = None


class ZkRoundsResponse(BaseModel):
    source: list[str]
    rounds: list[ZkRound]
