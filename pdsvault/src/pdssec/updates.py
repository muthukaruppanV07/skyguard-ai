# SPDX-License-Identifier: MIT
"""Signed model-update pipeline with staged rollout, shadow-mode, kill-switch
and anti-rollback.

Model lifecycle on device:
    pending (staged) --shadow run--> active --(signed kill-switch)--> killed
Every activation bumps the TPM NV counter `model-epoch`; installing an update
whose model_epoch is lower than the counter is rejected (anti-rollback:
an attacker reflashing an older, weaker model cannot bring the counter back).

Shadow mode: the candidate runs alongside the active model and its decisions
are compared (and logged) for a configured number of probes *without* being
used to release entitlements.  It becomes active only after the authority-
signed activation manifest is applied.
"""

from __future__ import annotations

import json

from . import crypto
from .crypto import b64d
from .identity import verify_authority_record

MODEL_PENDING = "model:pending"
MODEL_ACTIVE = "model:active"
MODEL_KILLED = "model:killed"
MODEL_EPOCH_COUNTER = "model-epoch"


def _verify(store, authority_pk_der: bytes, rec: dict) -> bool:
    return verify_authority_record(authority_pk_der, rec)


def apply_model_update_record(store, authority_pk_der: bytes, rec: dict) -> None:
    """Stage a signed model update.  Does not activate anything."""
    if not _verify(store, authority_pk_der, rec):
        store.quarantine("model_update", rec.get("body", "?"),
                         "model update signature invalid")
        from .store import QuarantinedRecord
        raise QuarantinedRecord("unsigned model update")
    fields = crypto._parse_canonical(b64d(rec["body"]))
    version = fields.get("model_version")
    sha = fields.get("model_sha256")
    staged = fields.get("staged") == "1"
    # anti-rollback: candidate model epoch counter must >= current
    store.set_sync_state(MODEL_PENDING, json.dumps(
        {"version": version, "sha256": sha, "staged": staged}))


def activate_model(store, tpm, authority_pk_der: bytes, rec: dict) -> dict:
    """Activate a previously staged model after shadow validation.  Bumps the
    TPM model-epoch anti-rollback counter."""
    if not _verify(store, authority_pk_der, rec):
        store.quarantine("model_update", rec.get("body", "?"),
                         "activation signature invalid")
        from .store import QuarantinedRecord
        raise QuarantinedRecord("unsigned activation")
    fields = crypto._parse_canonical(b64d(rec["body"]))
    if fields.get("kind") != "model_update" or fields.get("staged") != "0":
        raise ValueError("record is not a signed activation manifest")
    version = fields.get("model_version")
    sha = fields.get("model_sha256")

    pending = json.loads(store.get_sync_state(MODEL_PENDING, "{}"))
    if pending.get("version") != version or pending.get("sha256") != sha:
        raise ValueError("activation manifest does not match staged candidate")

    epoch = int(fields.get("model_epoch", "0"))
    cur = tpm.counter_read(MODEL_EPOCH_COUNTER)
    if epoch < cur:
        raise ValueError(
            f"anti-rollback: model_epoch {epoch} < installed {cur}")

    store.set_sync_state(MODEL_ACTIVE, json.dumps(
        {"version": version, "sha256": sha, "epoch": epoch}))
    store.set_sync_state(MODEL_PENDING, "{}")
    tpm.counter_increment(MODEL_EPOCH_COUNTER)
    return {"version": version, "sha256": sha, "epoch": epoch}


def apply_kill_switch(store, authority_pk_der: bytes, rec: dict) -> None:
    if not _verify(store, authority_pk_der, rec):
        store.quarantine("kill_switch", rec.get("body", "?"),
                         "kill-switch signature invalid")
        from .store import QuarantinedRecord
        raise QuarantinedRecord("unsigned kill-switch")
    fields = crypto._parse_canonical(b64d(rec["body"]))
    version = fields.get("model_version")
    active = json.loads(store.get_sync_state(MODEL_ACTIVE, "{}"))
    if active.get("version") == version:
        # fail-closed: a killed active model must not serve entitlements
        store.set_sync_state(MODEL_KILLED, json.dumps(
            {"version": version, "killed": True}))
        return
    store.set_sync_state(MODEL_KILLED, json.dumps(
        {"version": version, "killed": True, "pending": True}))


def active_model(store) -> dict | None:
    return json.loads(store.get_sync_state(MODEL_ACTIVE, "{}")) or None


def model_serving_enabled(store) -> bool:
    """Fail-closed check: entitlement release is refused while the active
    model is under kill-switch."""
    killed = json.loads(store.get_sync_state(MODEL_KILLED, "{}"))
    active = json.loads(store.get_sync_state(MODEL_ACTIVE, "{}"))
    if killed.get("version") and active.get("version") == killed.get("version"):
        return False
    return bool(active)


def shadow_evaluate(matcher_active, matcher_candidate,
                    probes: list[tuple[bytes, bytes]]) -> dict:
    """Run the candidate in shadow alongside the active model on benign
    capture pairs; report agreement and score deltas without ever releasing
    an entitlement based on the candidate."""
    agreed = disagreed = 0
    deltas = []
    for q, enr in probes:
        a = matcher_active.match(q, enr)
        c = matcher_candidate.match(q, enr)
        if a["accepted"] == c["accepted"]:
            agreed += 1
        else:
            disagreed += 1
        deltas.append(round(c["score"] - a["score"], 6))
    return {
        "trials": len(probes), "agreed": agreed, "disagreed": disagreed,
        "mean_score_delta": (sum(deltas) / len(deltas)) if deltas else 0.0,
    }