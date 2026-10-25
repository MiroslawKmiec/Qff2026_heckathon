"""Compile the frozen pilot, without submitting any remote workload.

Default: offline FakeTorino target. --backend NAME queries a real backend using a
saved account; it still never calls run(). Review manifest before a later submission.
"""
import argparse
import hashlib
import json

from qiskit import qpy
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime.fake_provider import FakeTorino
from qiskit_ibm_runtime.options_models import SamplerOptions

from benchmark import ROOT, SEED


def prepare(backend_name=None, remaining_seconds=480):
    if remaining_seconds < 480:
        raise ValueError("Budget changed: revise the 360-second job plus 120-second reserve before proceeding")
    if backend_name:
        from ibm_access import create_service
        backend = create_service().backend(backend_name)
    else:
        backend = FakeTorino()
    folder = ROOT / "results/pilot"
    with (folder / "logical_circuits.qpy").open("rb") as f:
        circuits = qpy.load(f)
    pilot = json.loads((folder / "manifest.json").read_text())
    assert len(circuits) == pilot["circuits"] == 186
    pm = generate_preset_pass_manager(backend=backend, optimization_level=1, seed_transpiler=SEED)
    compiled = pm.run(circuits, num_processes=1)
    schedule = generate_preset_pass_manager(target=backend.target, optimization_level=0, scheduling_method="alap")
    scheduled = schedule.run(compiled, num_processes=1)
    durations = [float(c.estimate_duration(backend.target)) for c in scheduled]
    rep_delay = float(getattr(backend, "default_rep_delay", None) or 0.00025)
    # Include an extra reset bound on every circuit, in addition to its scheduled duration.
    reset_durations = [p.duration for p in backend.target["reset"].values() if p is not None and p.duration is not None]
    reset_seconds = max(reset_durations)
    estimate = 2 + pilot["shots"] * sum(d + rep_delay + reset_seconds for d in durations)
    if estimate > 300:
        raise ValueError(f"Estimated {estimate:.1f}s exceeds 300s planning ceiling; reduce workload before submission")
    options = SamplerOptions(default_shots=pilot["shots"], max_execution_time=360)
    options.twirling.enable_gates = False
    options.twirling.enable_measure = False
    options.dynamical_decoupling.enable = False
    path = folder / ("ibm_isa.qpy" if backend_name else "fake_torino_isa.qpy")
    with path.open("wb") as f:
        qpy.dump(compiled, f)
    report = dict(backend=backend.name, offline=backend_name is None, submitted=False,
                  circuits=len(compiled), shots=pilot["shots"], max_execution_time=360,
                  remaining_seconds_user_supplied=remaining_seconds, reserve_seconds=120,
                  estimated_seconds=estimate, rep_delay=rep_delay, reset_bound_seconds=reset_seconds,
                  max_depth=max(c.depth() for c in compiled),
                  max_two_qubit_gates=max(sum(len(i.qubits)==2 for i in c.data) for c in compiled),
                  logical_sha256=hashlib.sha256((folder/"logical_circuits.qpy").read_bytes()).hexdigest(),
                  isa_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  warning="Timing is an estimate, not a billing guarantee. Fake target is not a live calibration. Verify actual remaining account usage before submission.")
    report_path = folder / ("ibm_preflight.json" if backend_name else "fake_preflight.json")
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", help="Optional real IBM backend; reads saved account, never submits")
    parser.add_argument("--remaining-seconds", type=int, default=480)
    args = parser.parse_args()
    prepare(args.backend, args.remaining_seconds)
