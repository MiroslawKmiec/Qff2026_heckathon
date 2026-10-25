import unittest
import json
import hashlib
from pathlib import Path
import numpy as np
from qiskit.quantum_info import Statevector
from model import WineFeatures, fidelity_kernel, states, overlap_circuit, psd_features


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.X = np.random.default_rng(7).uniform(-1, 1, (8, 4))

    def test_kernel_invariants_and_entangling_effect(self):
        product = fidelity_kernel(states(self.X), states(self.X))
        s = states(self.X, entangled=True)
        kernel = fidelity_kernel(s, s)
        np.testing.assert_allclose(np.diag(kernel), 1, atol=1e-12)
        np.testing.assert_allclose(kernel, kernel.T, atol=1e-12)
        self.assertGreater(np.linalg.eigvalsh(kernel).min(), -1e-10)
        self.assertGreater(np.max(np.abs(product-kernel)), 1e-3)

    def test_overlap_matches_inner_product(self):
        s = states(self.X, entangled=True, depth=2)
        qc = overlap_circuit(self.X[0], self.X[1], entangled=True, depth=2)
        probability = Statevector.from_instruction(qc.remove_final_measurements(inplace=False)).probabilities()[0]
        self.assertAlmostEqual(probability, fidelity_kernel(s, s)[0, 1], places=12)

    def test_transform_does_not_refit_on_test_data(self):
        rng = np.random.default_rng(3)
        pre = WineFeatures().fit(rng.normal(size=(30, 13)))
        mean = pre.scaler_.mean_.copy()
        pre.transform(np.full((5, 13), 1e6))
        np.testing.assert_array_equal(mean, pre.scaler_.mean_)

    def test_psd_extension_matches_exact_kernel(self):
        s = states(self.X)
        k = fidelity_kernel(s, s)
        a, b = psd_features(k, k)
        np.testing.assert_allclose(a@a.T, k, atol=1e-8)
        np.testing.assert_allclose(b@a.T, k, atol=1e-8)

    def test_saved_data_and_disjoint_splits(self):
        root = Path(__file__).resolve().parent
        split = json.loads((root / "data/split.json").read_text())
        train, test = set(split["train_ids"]), set(split["test_ids"])
        self.assertEqual(len(train), 133)
        self.assertEqual(len(test), 45)
        self.assertFalse(train & test)
        self.assertEqual(train | test, set(range(178)))
        validation_ids = []
        for fold in split["cv"]:
            a, b = set(fold["train_ids"]), set(fold["validation_ids"])
            self.assertFalse(a & b)
            self.assertEqual(a | b, train)
            validation_ids.extend(b)
        self.assertEqual(sorted(validation_ids), sorted(train))
        expected = json.loads((root / "data/provenance.json").read_text())["sha256"]
        self.assertEqual(hashlib.sha256((root / "data/wine.csv").read_bytes()).hexdigest(), expected)

    def test_pilot_coverage_and_shots(self):
        root = Path(__file__).resolve().parent / "results/pilot"
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertEqual(len(manifest["pairs"]), 186)
        self.assertEqual(len(set(map(tuple, manifest["pairs"]))), 186)
        for name in ["finite_shots", "synthetic_noise"]:
            counts = json.loads((root / f"{name}_counts.json").read_text())
            self.assertEqual(len(counts), 186)
            self.assertTrue(all(sum(c.values()) == 1024 for c in counts))


if __name__ == "__main__":
    unittest.main()
