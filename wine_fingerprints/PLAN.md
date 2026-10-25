# Quantum Wine Fingerprints — protocol v1

## Question and scope

Can a shallow four-qubit fidelity kernel classify three wine cultivars, and do
data-dependent entangling gates improve performance enough to justify their cost?
This is cultivar recognition from chemical measurements, not wine quality,
geographic authentication, or a quantum advantage demonstration.

## Frozen local experiment

- UCI Wine: 178 rows, 13 numerical features, three classes. Export the bundled
  scikit-learn copy with row IDs, attribution, and a SHA-256 checksum.
- Seed 20261025; stratified 75/25 train/test split. Save explicit indices.
- Three stratified CV folds within training only. Standardization, four-component
  PCA, PC scaling, and arctan bounding are fitted within each fold. All models
  receive identical four-dimensional coordinates.
- Majority, logistic regression, linear SVM, RBF SVM, product-state quantum SVM,
  and data-dependent nearest-neighbour RZZ quantum SVM.
- C in {0.1,1,10}; RBF gamma in {0.1,1,scale}; quantum scale in {0.5,1} and depth
  in {1,2}. Select by CV macro-F1, deterministic first-candidate tie break.
- Refit on all training rows and evaluate the held-out 45 rows. Save all predictions,
  selection scores, confusion matrices and runtimes. Do not retune after viewing test results.
- CV standard deviation describes selection-fold variability, not a confidence
  interval. One small held-out split cannot establish superiority.

## Local hardware rehearsal

Choose the entangled model's settings using training CV only. Use a fixed stratified
12-row training subset and nine test rows, selected by seed rather than prediction
success. Refit preprocessing on those 12 rows for this separate pilot. Train and
evaluate every pilot comparator on these same rows and features. This is a hardware
feasibility pilot, not the full benchmark.

Measure 78 training overlaps (including 12 diagonals) and 108 test-to-training
overlaps: 186 circuits at 1024 shots, 190464 shots total. Preserve self-overlap
circuits with a barrier to prevent cancellation; use the same barrier convention
in all overlap circuits. Run exact, finite-shot and explicitly synthetic noisy
Aer simulations. Save raw counts, kernel spectra, classification results and
kernel errors. For noisy kernels, retain positive training eigenmodes and extend
test features using the same eigensystem; never use test labels for repair.

## IBM stage, after local checks

Eight minutes means 480 seconds total QPU allowance, not queue time. Prepare one
job with a maximum execution time of 360 seconds, leaving 120 seconds reserve.
Use job mode, no automatic retries, no noise-learning job, and no hardware tuning.
Verify remaining account allowance and target-specific compiled duration before
submission. A timeout can consume budget without producing useful results.

IBM's rough formula 2 + 0.00035 * shots gives about 69 seconds for this pilot,
but this is NOT a device-specific estimate or a guarantee. Sub-job overhead,
initialization and reset, actual gate durations, and service behavior matter.
Save job ID immediately, retrieve rather than resubmit on interruption, and record
actual usage and backend calibration context. Recheck the installed Runtime API
and current IBM docs before submitting. No remote submission is part of the local
benchmark command.

## Submission deliverables

Public licensed code and data attribution; reproducible local results; experiment
limitations; one comparison chart; optional clearly separated hardware pilot;
1–3 minute video explaining question, method, results and where classical wins.
Local experiments and the IBM hardware pilot are complete; evidence is recorded in
[RESULTS.md](RESULTS.md). This repository includes the code, data attribution,
saved results and comparison charts. Video recording and final email submission
remain to be completed. No further hardware job is planned.
