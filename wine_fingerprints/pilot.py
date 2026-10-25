"""Offline rehearsal of the exact 186-circuit hardware pilot. Never submits jobs."""
import json
from pathlib import Path

import numpy as np
from qiskit import qpy, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error
from sklearn.datasets import load_wine
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC

from benchmark import ROOT, SEED, scores
from model import WineFeatures, states, fidelity_kernel, overlap_circuit, psd_features

SHOTS = 1024


def build_pilot():
    split = json.loads((ROOT / "data/split.json").read_text())
    report = json.loads((ROOT / "results/benchmark.json").read_text())
    result = next(r for r in report["results"] if r["model"] == "quantum_entangled")
    config = {k.removeprefix("model__"): v for k, v in result["best_params"].items()}
    C = config.pop("C")
    config["entangled"] = True
    wine = load_wine()
    train = np.asarray(split["train_ids"])
    test = np.asarray(split["test_ids"])
    train, _ = train_test_split(train, train_size=12, stratify=wine.target[train], random_state=SEED)
    test, _ = train_test_split(test, train_size=9, stratify=wine.target[test], random_state=SEED)
    pre = WineFeatures().fit(wine.data[train])
    a, b = pre.transform(wine.data[train]), pre.transform(wine.data[test])
    pairs = [("train", i, j) for i in range(len(a)) for j in range(i, len(a))]
    pairs += [("test", i, j) for i in range(len(b)) for j in range(len(a))]
    circuits = [overlap_circuit(a[i] if kind == "train" else b[i], a[j], **config) for kind, i, j in pairs]
    return train, test, a, b, config, C, pairs, circuits


def unpack(probabilities, pairs, n_train=12, n_test=9):
    train, test = np.zeros((n_train, n_train)), np.zeros((n_test, n_train))
    for p, (kind, i, j) in zip(probabilities, pairs):
        if kind == "train":
            train[i, j] = train[j, i] = p
        else:
            test[i, j] = p
    return train, test


def run():
    train, test, a, b, config, C, pairs, circuits = build_pilot()
    y = load_wine().target
    sa, sb = states(a, **config), states(b, **config)
    exact_a, exact_b = fidelity_kernel(sa, sa), fidelity_kernel(sb, sa)
    out = ROOT / "results/pilot"
    out.mkdir(exist_ok=True)
    with (out / "logical_circuits.qpy").open("wb") as f:
        qpy.dump(circuits, f)
    np.savez(out / "inputs.npz", train_ids=train, test_ids=test, train_angles=a, test_angles=b,
             train_labels=y[train], test_labels=y[test], exact_train=exact_a, exact_test=exact_b)
    noise = NoiseModel()
    noise.add_all_qubit_quantum_error(depolarizing_error(0.001, 1), ["sx", "x"])
    noise.add_all_qubit_quantum_error(depolarizing_error(0.01, 2), ["cx"])
    noise.add_all_qubit_readout_error(ReadoutError([[0.985, 0.015], [0.015, 0.985]]))
    conditions = [("exact", None), ("finite_shots", None), ("synthetic_noise", noise)]
    results = []
    for name, noise_model in conditions:
        if name == "exact":
            ka, kb = exact_a, exact_b
        else:
            simulator = AerSimulator(method="density_matrix", noise_model=noise_model,
                                     max_parallel_threads=2)
            compiled = transpile(circuits, basis_gates=["rz", "sx", "x", "cx"],
                                 optimization_level=1, seed_transpiler=SEED, num_processes=1)
            result = simulator.run(compiled, shots=SHOTS, seed_simulator=SEED).result()
            counts = [result.get_counts(i) for i in range(len(circuits))]
            assert all(sum(c.values()) == SHOTS for c in counts)
            (out / f"{name}_counts.json").write_text(json.dumps(counts))
            ka, kb = unpack([c.get("0000", 0)/SHOTS for c in counts], pairs)
        fa, fb = psd_features(ka, kb)
        classifier = SVC(C=C, kernel="linear").fit(fa, y[train])
        predicted = classifier.predict(fb)
        item = dict(condition=name, **scores(y[test], predicted), predictions=predicted.tolist(),
                    min_train_eigenvalue=float(np.linalg.eigvalsh(ka).min()),
                    retained_modes=fa.shape[1], train_kernel_mae=float(np.mean(np.abs(ka-exact_a))),
                    test_kernel_mae=float(np.mean(np.abs(kb-exact_b))),
                    mean_self_overlap=float(np.diag(ka).mean()))
        results.append(item)
        np.savez(out / f"{name}_kernels.npz", train=ka, test=kb)
        print(json.dumps(item), flush=True)
    # Same tiny training/test budget and features; hyperparameters from full training CV only.
    full = json.loads((ROOT / "results/benchmark.json").read_text())
    for model_name, kernel in [("linear_svm", "linear"), ("rbf_svm", "rbf")]:
        params = next(r["best_params"] for r in full["results"] if r["model"] == model_name)
        params = {k.removeprefix("model__"): v for k, v in params.items()}
        predicted = SVC(kernel=kernel, **params).fit(a, y[train]).predict(b)
        results.append(dict(condition=model_name, **scores(y[test], predicted), predictions=predicted.tolist()))
    manifest = dict(settings=config, C=C, shots=SHOTS, circuits=len(circuits), pairs=pairs,
                    total_shots=len(circuits)*SHOTS, train_ids=train.tolist(), test_ids=test.tolist(),
                    rough_seconds=2+0.00035*len(circuits)*SHOTS, max_execution_time=360,
                    total_user_budget_seconds=480, submitted=False,
                    noise={"one_qubit_depolarizing":0.001,"two_qubit_depolarizing":0.01,"readout_flip":0.015},
                    caveat="Synthetic noise, not a calibrated IBM backend. Nine test examples are a feasibility pilot only.",
                    results=results)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    run()
