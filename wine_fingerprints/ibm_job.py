"""Submit once or retrieve the frozen Wine pilot. Remote actions are explicit."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math

import numpy as np
from qiskit import qpy
from ibm_access import create_service
from qiskit_ibm_runtime.executor_sampler import Sampler
from qiskit_ibm_runtime.options_models import SamplerOptions
from sklearn.svm import SVC

from benchmark import ROOT, scores
from model import psd_features
from pilot import unpack

FOLDER = ROOT / "results/pilot"
RECEIPT = FOLDER / "ibm_job.json"


def charged_seconds(metrics):
    """Support current charge-time metrics and legacy quantum_seconds."""
    usage = metrics.get("usage", {})
    value = usage.get("qpu_charge_time_seconds")
    if value is None:
        value = usage.get("quantum_seconds")
    return value


def verify_preflight(preflight, usage, isa_bytes, logical_bytes):
    if preflight.get("offline") or preflight.get("submitted"):
        raise ValueError("Require a live, unsubmitted backend preflight")
    for key, content in [("isa_sha256", isa_bytes), ("logical_sha256", logical_bytes)]:
        if hashlib.sha256(content).hexdigest() != preflight[key]:
            raise ValueError(f"Frozen circuit checksum mismatch: {key}")
    remaining = usage.get("usage_remaining_seconds")
    if remaining is None or not math.isfinite(float(remaining)) or float(remaining) < 480:
        raise ValueError("Cannot verify at least 480 seconds of remaining instance allowance")
    if preflight["max_execution_time"] != 360 or preflight["circuits"] != 186 or preflight["shots"] != 1024:
        raise ValueError("Workload differs from the approved pilot budget")
    estimate = preflight["estimated_seconds"]
    if not math.isfinite(estimate) or not 0 < estimate <= 300:
        raise ValueError("Timing estimate exceeds the planning limit")


def submit():
    if RECEIPT.exists():
        raise RuntimeError("Submission receipt already exists. Retrieve the existing job; do not resubmit.")
    preflight = json.loads((FOLDER / "ibm_preflight.json").read_text())
    service = create_service()
    backend = service.backend(preflight["backend"])
    if not backend.status().operational:
        raise RuntimeError("Prepared backend is not operational")
    usage = service.usage()
    verify_preflight(preflight, usage, (FOLDER/"ibm_isa.qpy").read_bytes(),
                     (FOLDER/"logical_circuits.qpy").read_bytes())
    with (FOLDER / "ibm_isa.qpy").open("rb") as f:
        circuits = qpy.load(f)
    if len(circuits) != 186:
        raise ValueError("Circuit count mismatch")
    options = SamplerOptions(default_shots=1024, max_execution_time=360)
    options.twirling.enable_gates = False
    options.twirling.enable_measure = False
    options.dynamical_decoupling.enable = False
    options.execution.rep_delay = preflight["rep_delay"]
    options.environment.job_tags = ["quantum-wine-fingerprints"]
    sampler = Sampler(mode=backend, options=options)
    receipt = dict(state="submission_attempted", backend=backend.name,
                   timestamp=datetime.now(timezone.utc).isoformat(),
                   max_execution_time=360, reserved_seconds=120,
                   remaining_before_seconds=usage["usage_remaining_seconds"],
                   isa_sha256=preflight["isa_sha256"])
    # Exclusive create BEFORE the network mutation: ambiguous failures cannot auto-retry.
    with RECEIPT.open("x") as f:
        json.dump(receipt, f, indent=2)
    job = sampler.run(circuits, shots=1024)
    receipt.update(state="submitted", job_id=job.job_id())
    RECEIPT.write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


def collect():
    receipt = json.loads(RECEIPT.read_text())
    if "job_id" not in receipt:
        raise RuntimeError("Submission outcome ambiguous. Inspect IBM Workloads for the recorded tag/time; never retry automatically.")
    service = create_service()
    job = service.job(receipt["job_id"])
    status = job.status()
    status = getattr(status, "name", str(status))
    print("Job status:", status)
    if status not in {"DONE", "ERROR", "CANCELLED"}:
        return
    metrics = job.metrics()
    receipt.update(state=status, quantum_seconds=charged_seconds(metrics))
    RECEIPT.write_text(json.dumps(receipt, indent=2))
    (FOLDER / "ibm_metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    if status != "DONE":
        print("Job did not complete; usage recorded. No retry.")
        return
    result = job.result()
    if len(result) != 186:
        raise ValueError("Unexpected result count")
    counts = [item.data.meas.get_counts() for item in result]
    if not all(sum(c.values()) == 1024 for c in counts):
        raise ValueError("Unexpected shot totals")
    (FOLDER / "ibm_counts.json").write_text(json.dumps(counts))
    manifest = json.loads((FOLDER / "manifest.json").read_text())
    inputs = np.load(FOLDER / "inputs.npz")
    ka, kb = unpack([c.get("0000", 0)/1024 for c in counts], manifest["pairs"])
    fa, fb = psd_features(ka, kb)
    predictions = SVC(C=manifest["C"], kernel="linear").fit(fa, inputs["train_labels"]).predict(fb)
    report = dict(job_id=receipt["job_id"], backend=receipt["backend"],
                  quantum_seconds=receipt["quantum_seconds"], **scores(inputs["test_labels"], predictions),
                  predictions=predictions.tolist(), retained_modes=fa.shape[1],
                  train_kernel_mae=float(np.mean(np.abs(ka-inputs["exact_train"]))),
                  test_kernel_mae=float(np.mean(np.abs(kb-inputs["exact_test"]))),
                  mean_self_overlap=float(np.diag(ka).mean()))
    np.savez(FOLDER / "ibm_kernels.npz", train=ka, test=kb)
    (FOLDER / "ibm_results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["submit", "collect"])
    args = parser.parse_args()
    submit() if args.action == "submit" else collect()
