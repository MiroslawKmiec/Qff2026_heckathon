# Qff2026_heckathon

## Quantum Wine Fingerprints

Can a four-qubit quantum kernel recognize wine cultivars, and does entanglement help?

The [project folder](wine_fingerprints/) contains the implementation, licensed code,
data attribution, reproducible local results, and a completed IBM Quantum pilot.

- [Setup and reproduction](wine_fingerprints/README.md)
- [Results and limitations](wine_fingerprints/RESULTS.md)
- [Experiment plan and remaining deliverables](wine_fingerprints/PLAN.md)

On the frozen 45-wine test, the product-state kernel classified 45/45 wines correctly;
the entangled kernel and classical RBF SVM each classified 43/45. In the separate
nine-wine pilot, IBM Fez classified 7/9 correctly, using 52 charged QPU seconds.
These small experiments do not establish quantum advantage.
