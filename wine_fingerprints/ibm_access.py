"""Secure interactive account setup and read-only IBM access checks."""
import argparse
from getpass import getpass
import json
import os
from pathlib import Path
from dotenv import dotenv_values

from qiskit_ibm_runtime import QiskitRuntimeService


def create_service():
    """Read local credentials without shell evaluation or writing another copy."""
    values = dotenv_values(Path(__file__).resolve().parent / ".env", interpolate=False)
    token = values.get("QISKIT_IBM_TOKEN") or os.environ.get("QISKIT_IBM_TOKEN")
    instance = values.get("QISKIT_IBM_INSTANCE") or os.environ.get("QISKIT_IBM_INSTANCE")
    if token or instance:
        if not token or not instance:
            raise ValueError("Both IBM token and instance must be configured")
        return QiskitRuntimeService(channel="ibm_quantum_platform", token=token, instance=instance)
    return QiskitRuntimeService()


def setup():
    token = getpass("IBM Quantum API key (hidden; never paste into chat): ")
    instance = input("IBM Quantum instance CRN: ").strip()
    if not token.strip() or not instance.startswith("crn:"):
        raise ValueError("A nonempty key and instance CRN are required")
    QiskitRuntimeService.save_account(token=token.strip(), instance=instance,
                                     channel="ibm_quantum_platform",
                                     name="wine-fingerprints", set_as_default=True,
                                     overwrite=False)
    print("Account saved by Qiskit in your local account store. No QPU job submitted.")


def check():
    service = create_service()
    backends = service.backends(operational=True, simulator=False, min_num_qubits=4)
    print(json.dumps({"accessible_backends": [b.name for b in backends]}, indent=2))
    usage = service.usage()
    fields = ["usage_limit_seconds", "usage_allocation_seconds", "usage_consumed_seconds", "usage_remaining_seconds"]
    print(json.dumps({k: usage[k] for k in fields if k in usage}, indent=2))
    print("Read-only access check; no QPU job submitted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "check"])
    args = parser.parse_args()
    if args.action == "setup":
        setup()
    else:
        check()
