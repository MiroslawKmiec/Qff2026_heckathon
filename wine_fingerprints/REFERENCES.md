# Methodology and dataset references

Reviewed 2026-10-25. External projects were read for methodology; their code and
assets are not copied into this implementation.

## Winning entries and lessons

- [Organizer's 2025 results](https://www.qaif.org/contests/qpoland-global-quantum-hackathon)
  confirm the QML winner: Hierarchical Topological Quantum Graph Kernels for
  molecular classification, team |Schrödinger’s Qat⟩.
- [Winning repository](https://github.com/nandinii27/QPoland-Hackathon): domain
  features, explicit fidelity kernel, report, presentation and video. Its README
  sketches a fixed terminal CNOT network. Mathematical caveat: if the only change
  is a common final unitary V, inner products are unchanged because V†V=I.
  This is an observation about the displayed formula, not a full audit of the
  repository or a claim that its implemented results are invalid. Our input-dependent
  RZZ angles avoid this cancellation, and a test verifies a changed kernel.
- [Axion Kitchen 2026](https://github.com/Kolo-Naukowe-Axion/qhackathon26): repository
  identifies main-prize and joint VeloxQ awards. The [team's page](https://axion.pwr.edu.pl/)
  reports the same awards. It separates reproducible comparisons from an interactive
  demo and explicitly limits advantage claims. These are presentation lessons;
  this is an optimization winner, not a QML winner. Current README may contain
  post-hackathon extensions; it links the original submission release.
- [Xanadu qml-benchmarks](https://github.com/XanaduAI/qml-benchmarks): methodological
  reference, not presented here as a hackathon winner. Use comparable preprocessing,
  tuning and classical controls; do not import its whole stack for this small task.

## Dataset and implementation references

- [UCI Wine](https://archive.ics.uci.edu/dataset/109/wine), DOI 10.24432/C5PC7J:
  three cultivars from one Italian region, 178 samples, 13 chemical measurements.
  Downloaded here through scikit-learn's bundled UCI copy. Attribution and checksum
  are retained in [data/provenance.json](data/provenance.json). Dataset licence is
  separate from the original code licence.
- [Qiskit quantum kernels](https://qiskit-community.github.io/qiskit-machine-learning/tutorials/03_quantum_kernel.html):
  fidelity kernel definition and precomputed SVM interface. This implementation uses
  Qiskit Statevector directly, avoiding another dependency for four-qubit simulation.
- [IBM execution time limit](https://quantum.cloud.ibm.com/docs/en/guides/max-execution-time):
  max_execution_time is QPU usage, not queue/wall-clock time.
- [IBM workload usage](https://quantum.cloud.ibm.com/docs/en/guides/estimate-job-run-time):
  rough duration formula, actual usage, overhead and failed/cancelled-job billing.
