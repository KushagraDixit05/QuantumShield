"""Faulty-aggregator modes for consensus-lite.

silent      : never sends a vote.
equivocate  : votes on a wrong hash (here H(W_{t+1}) of a model nudged by one unit).
Honest nodes use HONEST. A fault only changes what a node sends; it never changes how honest
nodes count, so the f=1 bound is a property of the 2f+1 quorum, not of special-casing.
"""
import numpy as np

HONEST, SILENT, EQUIVOCATE = "honest", "silent", "equivocate"
MODES = (HONEST, SILENT, EQUIVOCATE)


def check(mode):
    if mode not in MODES:
        raise ValueError(f"fault mode must be one of {MODES}, got {mode!r}")
    return mode


def vote_model(mode, w_next):
    """The model a node with this fault mode signs its vote over, or None to stay silent."""
    if mode == SILENT:
        return None
    if mode == EQUIVOCATE:
        wrong = np.array(w_next, dtype=np.int64)
        wrong[0] += 1
        return wrong
    return w_next
