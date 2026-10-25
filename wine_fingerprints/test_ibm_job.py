import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ibm_job


class BudgetTests(unittest.TestCase):
    def test_current_and_legacy_usage_metrics(self):
        self.assertEqual(ibm_job.charged_seconds({"usage":{"qpu_charge_time_seconds":52,"value":0.859497,"unit":"resource_units"}}),52)
        self.assertEqual(ibm_job.charged_seconds({"usage":{"quantum_seconds":3}}),3)
        self.assertIsNone(ibm_job.charged_seconds({}))

    def setUp(self):
        self.preflight = dict(offline=False, submitted=False, max_execution_time=360,
                              circuits=186, shots=1024, estimated_seconds=70,
                              isa_sha256=hashlib.sha256(b"isa").hexdigest(),
                              logical_sha256=hashlib.sha256(b"logical").hexdigest())

    def test_verified_budget_accepts_frozen_workload(self):
        ibm_job.verify_preflight(self.preflight, {"usage_remaining_seconds":480}, b"isa", b"logical")

    def test_client_sampler_accepts_capped_options(self):
        from qiskit_aer import AerSimulator
        options = ibm_job.SamplerOptions(default_shots=1024, max_execution_time=360)
        sampler = ibm_job.Sampler(mode=AerSimulator(), options=options)
        self.assertEqual(sampler.options.max_execution_time, 360)

    def test_unknown_or_insufficient_budget_blocks(self):
        for remaining in [None, 479, -1, float("nan")]:
            with self.subTest(remaining=remaining), self.assertRaises(ValueError):
                ibm_job.verify_preflight(self.preflight, {"usage_remaining_seconds":remaining}, b"isa", b"logical")

    def test_modified_circuit_blocks(self):
        with self.assertRaises(ValueError):
            ibm_job.verify_preflight(self.preflight, {"usage_remaining_seconds":480}, b"different", b"logical")

    def test_fake_target_blocks(self):
        self.preflight["offline"] = True
        with self.assertRaises(ValueError):
            ibm_job.verify_preflight(self.preflight, {"usage_remaining_seconds":480}, b"isa", b"logical")

    def test_existing_receipt_blocks_before_account_access(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "receipt.json"
            path.write_text('{"state":"submission_attempted"}')
            with patch.object(ibm_job, "RECEIPT", path), patch.object(ibm_job, "create_service") as service:
                with self.assertRaises(RuntimeError):
                    ibm_job.submit()
                service.assert_not_called()


if __name__ == "__main__":
    unittest.main()
