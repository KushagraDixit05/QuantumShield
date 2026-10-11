"""FastAPI backend for the QuantumShield UI (docs/api_contract.md). Run from the repo root:
    .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
Never proves: no call to prove_update / client_prove / any prover exists in this package."""
import ast
import asyncio
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from fl import aggregate
from fl.simulate import load_cfg

from . import certificates, common, limitations, overheads, receipts, results, run_queue
from .schemas import (Certificate, ConsensusResponse, Health, ResultsResponse, RunCreated, RunRequest,
                      ScenariosResponse, VerifyRequest, VerifyResponse, LimitationsResponse,
                      ReceiptsResponse, ZkRoundsResponse)

app = FastAPI(title="QuantumShield-FL API")
app.add_middleware(CORSMiddleware,
                   allow_origins=[f"http://{h}:{p}" for h in ("localhost", "127.0.0.1") for p in (3000, 3001)],
                   allow_methods=["GET", "POST"], allow_headers=["*"])

PLOT = common.ROOT / "demo" / "plot.py"
DESCRIPTIONS = {"A": "Benign clients only, classical signatures, plain FedAvg (the baseline).",
                "B": "One poisoned client (scaled update), classical signatures, plain FedAvg.",
                "C": "One poisoned client (scaled update), hybrid signatures and the plaintext norm gate, then FedAvg."}


def _plot_labels():
    """LABELS dict parsed from demo/plot.py (not retyped)."""
    for node in ast.parse(PLOT.read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "LABELS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise HTTPException(404, "LABELS not found in demo/plot.py")


@app.get("/api/health", response_model=Health)
def health():
    return Health(ok=True, prover_lock_held=common.prover_lock_held(), queue_length=run_queue.QUEUE.length())


@app.get("/api/scenarios", response_model=ScenariosResponse)
def scenarios():
    labels = _plot_labels()
    dc = load_cfg(run_queue.CONFIG)
    cfg = load_cfg(dc["base"])
    return dict(source=["demo/run_demo.py:158", "demo/plot.py:23", "configs/demo.yaml"],
                scenarios=[dict(id=k, label=labels[k], attack=a, defence=d, description=DESCRIPTIONS[k])
                           for k, (a, d) in run_queue.SCENARIOS.items()],
                attacks=["none", "scaled", "forged", "replay"], aggregators=list(aggregate.DEFENCES),
                default_seeds=dc["seeds"], default_rounds=cfg["rounds"], live_zk_enabled=False)


@app.post("/api/runs", response_model=RunCreated, status_code=201)
def create_run(req: RunRequest):
    if req.live_zk:
        raise HTTPException(422, "live ZK proving is disabled on this server")
    attack, defence = req.attack, req.defence
    if req.scenario:
        attack, defence = run_queue.SCENARIOS[req.scenario]
    job, pos = run_queue.QUEUE.submit(dict(attack=attack, defence=defence, aggregator=req.aggregator,
                                           seeds=req.seeds, rounds=req.rounds))
    return RunCreated(id=job.id, queue_position=pos)


def _job(run_id):
    job = run_queue.QUEUE.jobs.get(run_id)
    if job is None:
        raise HTTPException(404, "unknown run")
    return job


@app.get("/api/runs/{run_id}/stream")
async def stream(run_id: str):
    job = _job(run_id)

    async def gen():
        i = 0
        while True:
            evs, fin = job.snapshot(i)
            for ev in evs:
                yield f"data: {json.dumps(ev)}\n\n"
            i += len(evs)
            if fin and not evs:
                return
            await asyncio.sleep(0.05)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/results/{name}", response_model=ResultsResponse, response_model_by_alias=True, response_model_exclude_unset=True)
def get_result(name: str):
    return results.get(name)


@app.get("/api/receipts", response_model=ReceiptsResponse)
def get_receipts():
    return receipts.load_receipts()


@app.get("/api/zk/rounds", response_model=ZkRoundsResponse)
def get_zk_rounds():
    return receipts.zk_rounds()


def _state(job, seed):
    if not job.states:
        raise HTTPException(404, "no consensus data yet for this run")
    seed = next(iter(job.states)) if seed is None else seed
    if seed not in job.states:
        raise HTTPException(404, f"no consensus data for seed {seed}")
    return seed, job.states[seed]


@app.get("/api/consensus/{run_id}", response_model=ConsensusResponse)
def consensus(run_id: str, seed: int | None = None):
    job = _job(run_id)
    seed, st = _state(job, seed)
    return dict(run_id=run_id, seed=seed, seeds_available=list(job.states), n=st["n"], f=st["f"], quorum=st["quorum"],
                leader=0, leader_policy="fixed (no rotation)", view_changes=[],
                view_changes_note="not implemented, see D-020",
                rounds=[{k: v for k, v in r.items() if k != "raw_votes"} for r in st["rounds"]])


@app.get("/api/certificates/{run_id}/{round}", response_model=Certificate)
def get_certificate(run_id: str, round: int, seed: int | None = None):
    """The round's signed votes, in a form that can be pasted into POST /api/certificates/verify."""
    seed, st = _state(_job(run_id), seed)
    r = next((x for x in st["rounds"] if x["round"] == round), None)
    if r is None or not r["raw_votes"]:
        raise HTTPException(404, f"round {round} has no votes")
    return dict(run_id=run_id, seed=seed, round=round, votes=r["raw_votes"], certificate_id=r["certificate_id"])


@app.post("/api/certificates/verify", response_model=VerifyResponse)
def verify_certificate(req: VerifyRequest):
    if req.certificate is not None:
        cert = req.certificate.model_dump()
        run_id, seed = cert["run_id"], cert.get("seed")
    else:
        run_id, seed = req.run_id, req.seed
    seed, st = _state(_job(run_id), seed)
    if req.certificate is None:
        r = next((x for x in st["rounds"] if x["round"] == req.round), None)
        if r is None or not r["raw_votes"]:
            raise HTTPException(404, f"round {req.round} has no votes")
        cert = dict(round=req.round, votes=r["raw_votes"])
    # the registry is the run's own public snapshot; a pasted certificate never supplies its own keys
    return certificates.verify(cert, st["registry"], st["mode"], st["pq_alg"], st["classical_alg"], st["f"])


@app.get("/api/limitations", response_model=LimitationsResponse)
def get_limitations():
    return limitations.load()


@app.get("/api/overheads")
def get_overheads():
    return overheads.load()
