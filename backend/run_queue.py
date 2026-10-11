"""Single-worker job queue. One run at a time; a run is not started while a prover holds .zk_prove.lock."""
import queue
import threading
import time
import uuid

from fl.simulate import load_cfg

from . import common, runner

CONFIG = "configs/demo.yaml"
SCENARIOS = {"A": ("none", "off"), "B": ("scaled", "off"), "C": ("scaled", "on")}
LOCK_POLL_S = 1.0
MAX_JOBS = 100


def base_cfg():
    return load_cfg(load_cfg(CONFIG)["base"])


class Job:
    def __init__(self, req):
        self.id = uuid.uuid4().hex[:12]
        self.req = req
        self.events = []
        self.finished = False
        self.states = {}          # seed -> consensus state of the runner
        self._lock = threading.Lock()

    def push(self, ev, last=False):
        with self._lock:
            self.events.append(ev)
            if last:
                self.finished = True

    def snapshot(self, i):
        with self._lock:
            return self.events[i:], self.finished


class JobQueue:
    def __init__(self):
        self.jobs = {}
        self.order = []
        self.q = queue.Queue()
        self._mu = threading.Lock()
        self._worker = None
        self.pending = 0          # queued + running

    def length(self):
        with self._mu:
            return self.pending

    def submit(self, req):
        job = Job(req)
        with self._mu:
            position = self.pending
            self.pending += 1
            self.jobs[job.id] = job
            self.order.append(job.id)
            while len(self.order) > MAX_JOBS:           # drop the oldest finished job
                old = next((j for j in self.order if self.jobs[j].finished), None)
                if old is None:
                    break
                self.order.remove(old)
                del self.jobs[old]
            if self._worker is None:
                self._worker = threading.Thread(target=self._loop, daemon=True, name="qs-run-worker")
                self._worker.start()
        job.push(dict(type="queued", position=position))
        self.q.put(job)
        return job, position

    def _loop(self):
        while True:
            job = self.q.get()
            try:
                self._run(job)
            except Exception as e:  # noqa: BLE001
                job.push(dict(type="error", message=f"{type(e).__name__}: {e}"), last=True)
            finally:
                with self._mu:
                    self.pending -= 1

    def _run(self, job):
        while common.prover_lock_held():                # a prover (6 min, 2.4 GB) is running: wait for it
            job.push(dict(type="queued", position=0))
            time.sleep(LOCK_POLL_S)
        r = job.req
        cfg = base_cfg()
        if r.get("rounds"):
            cfg["rounds"] = r["rounds"]
        attack, defence = r["attack"], r["defence"]
        results = []
        for seed in r["seeds"]:
            job.push(dict(type="started", seed=seed, attack=attack, defence=defence, aggregator=r["aggregator"],
                          rounds=cfg["rounds"]))
            res = runner.run_seed(cfg, attack, defence == "on", r["aggregator"], seed, emit=job.push)
            job.states[seed] = res["consensus"]
            done = runner.seed_summary(seed, res)
            results.append(done)
            job.push(done)
        job.push(dict(type="done", results=results,
                      source="computed live by backend.runner (mirrors demo/run_demo.py:run_scenario)"), last=True)


QUEUE = JobQueue()
