"""Render saved local and IBM pilot results without accessing IBM."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent / "results/pilot"
local = json.loads((root / "manifest.json").read_text())
hardware = json.loads((root / "ibm_results.json").read_text())
rows = local["results"] + [{"condition":"ibm_fez", **hardware}]
names = [r["condition"].replace("_", "\n") for r in rows]
fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
axes[0].bar(names, [r["accuracy"]*9 for r in rows], color=["#aaa"]*5+["#722f57"])
axes[0].set(ylabel="Correct classifications / 9", ylim=(0, 10), title="Fixed pilot: same 12 training and 9 test wines")
kernel_rows = [r for r in rows if "test_kernel_mae" in r]
axes[1].bar([r["condition"].replace("_", "\n") for r in kernel_rows],
            [r["test_kernel_mae"] for r in kernel_rows], color="#722f57")
axes[1].set(ylabel="Mean absolute test-kernel error", title=f"IBM hardware: {hardware['quantum_seconds']} QPU seconds charged")
fig.savefig(root / "hardware_comparison.png", dpi=160)
