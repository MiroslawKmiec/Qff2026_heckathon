"""Run the preregistered local benchmark and export data and evidence."""
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.datasets import load_wine
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC

from model import QuantumKernelSVC, WineFeatures

ROOT = Path(__file__).resolve().parent
SEED = 20261025


def scores(y, predictions):
    return dict(accuracy=float(accuracy_score(y, predictions)),
                balanced_accuracy=float(balanced_accuracy_score(y, predictions)),
                macro_f1=float(f1_score(y, predictions, average="macro")))


def run():
    out = ROOT / "results"
    data = ROOT / "data"
    out.mkdir(exist_ok=True)
    data.mkdir(exist_ok=True)
    wine = load_wine()
    X, y = wine.data, wine.target
    with (data / "wine.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["row_id", *wine.feature_names, "cultivar"])
        for i, (x, label) in enumerate(zip(X, y)):
            writer.writerow([i, *x, int(label) + 1])
    train, test = train_test_split(np.arange(len(y)), test_size=0.25, stratify=y, random_state=SEED)
    cv = list(StratifiedKFold(3, shuffle=True, random_state=SEED).split(X[train], y[train]))
    split = {"seed": SEED, "train_ids": train.tolist(), "test_ids": test.tolist(),
             "cv": [{"train_ids": train[a].tolist(), "validation_ids": train[b].tolist()} for a, b in cv]}
    (data / "split.json").write_text(json.dumps(split, indent=2))
    metadata = dict(source="https://archive.ics.uci.edu/dataset/109/wine", doi="10.24432/C5PC7J",
                    obtained_via="sklearn.datasets.load_wine (bundled UCI copy)",
                    licence="CC BY 4.0 (UCI dataset page)", rows=178, features=13,
                    labels="CSV uses cultivar 1,2,3; internal arrays use 0,1,2",
                    sha256=hashlib.sha256((data / "wine.csv").read_bytes()).hexdigest())
    (data / "provenance.json").write_text(json.dumps(metadata, indent=2))
    models = [
        ("majority", DummyClassifier(strategy="most_frequent"), {}),
        ("logistic", LogisticRegression(max_iter=3000), {"model__C": [0.1, 1, 10]}),
        ("linear_svm", SVC(kernel="linear"), {"model__C": [0.1, 1, 10]}),
        ("rbf_svm", SVC(kernel="rbf"), {"model__C": [0.1, 1, 10], "model__gamma": [0.1, 1, "scale"]}),
        ("quantum_product", QuantumKernelSVC(), {"model__C": [0.1, 1, 10], "model__scale": [0.5, 1], "model__depth": [1, 2]}),
        ("quantum_entangled", QuantumKernelSVC(entangled=True), {"model__C": [0.1, 1, 10], "model__scale": [0.5, 1], "model__depth": [1, 2]}),
    ]
    results = []
    for name, estimator, grid in models:
        start = time.perf_counter()
        search = GridSearchCV(Pipeline([("features", WineFeatures()), ("model", estimator)]),
                              grid, scoring="f1_macro", cv=cv, n_jobs=1, error_score="raise")
        search.fit(X[train], y[train])
        fit_seconds = time.perf_counter() - start
        start = time.perf_counter()
        predicted = search.predict(X[test])
        predict_seconds = time.perf_counter() - start
        result = dict(model=name, best_params=search.best_params_,
                      cv_macro_f1=float(search.best_score_),
                      cv_std=float(search.cv_results_["std_test_score"][search.best_index_]),
                      **scores(y[test], predicted), fit_seconds=fit_seconds,
                      predict_seconds=predict_seconds, confusion_matrix=confusion_matrix(y[test], predicted).tolist(),
                      predictions=predicted.tolist())
        results.append(result)
        np.savez(out / f"{name}_cv.npz", mean=search.cv_results_["mean_test_score"],
                 std=search.cv_results_["std_test_score"],
                 params=np.array([json.dumps(p) for p in search.cv_results_["params"]]))
        print(json.dumps(result), flush=True)
    versions = {p: importlib.metadata.version(p) for p in ["numpy", "scipy", "scikit-learn", "qiskit", "qiskit-aer", "qiskit-ibm-runtime", "matplotlib", "python-dotenv"]}
    report = dict(protocol="protocol-v1", seed=SEED, train_size=len(train), test_size=len(test),
                  versions=versions, results=results,
                  note="CV scores are selection scores, not independent generalization estimates. Held-out test evaluated after selection. No quantum advantage claim.")
    (out / "benchmark.json").write_text(json.dumps(report, indent=2))
    (ROOT / "requirements-lock.txt").write_text("\n".join(f"{p}=={v}" for p, v in versions.items()) + "\n")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    names = [r["model"].replace("_", "\n") for r in results]
    axes[0].bar(names, [r["macro_f1"] for r in results], color=["#aaa"]*4+["#b56c9b", "#722f57"])
    axes[0].set(ylabel="Held-out macro-F1", ylim=(0, 1.05), title="Same four features; same 45 test wines")
    axes[1].bar(names, [r["fit_seconds"] for r in results], color="#722f57")
    axes[1].set(ylabel="Grid search + refit seconds (local)", yscale="log", title="Training and tuning cost")
    fig.savefig(out / "comparison.png", dpi=160)
    return report


if __name__ == "__main__":
    run()
