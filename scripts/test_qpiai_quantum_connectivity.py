import os
import sys
from dotenv import load_dotenv
from importlib.metadata import version

# Step 1 & 2: Load key and verify authentication
load_dotenv()

key = os.getenv("QCLOUD_API_KEY")
if not key:
    raise RuntimeError("QCLOUD_API_KEY is missing")

sdk_version = version("qpiai-quantum")
print("SDK version:", sdk_version)

from qpiai_quantum import QpiAIQuantumAuth as Auth
from qpiai_quantum import Circuit

Auth.login(key)
verified = bool(Auth.verify_api_key())
print("API key verified:", verified)

# Step 3: Discover available compute resources
print("\n--- Discovering Compute Resources ---")
try:
    resources = Auth.list_compute_resources(display=False)
    print("Resource discovery success: True")
    print(f"Total resources discovered: {len(resources)}")
    for resource in resources:
        print({
            "backend": resource.get("backend_name"),
            "device": resource.get("device_name"),
            "usage_rate": resource.get("usage_rate"),
        })
except Exception as e:
    print("Resource discovery success: False")
    print(f"Error during resource discovery: {type(e).__name__}: {str(e)}")
    resources = []

# Step 4: Test actual remote execution
print("\n--- Testing Remote Execution on QCloud ---")
remote_resources = [
    r for r in resources 
    if r.get("backend_name") and "local" not in r.get("backend_name", "").lower()
]

print(f"Candidate remote backends found: {[r.get('backend_name') for r in remote_resources]}")

if not remote_resources:
    print("No remote backends found to attempt execution.")
else:
    # Build minimal test circuit (2-qubit Bell pair)
    qc = Circuit(2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure_all()

    target_backend = remote_resources[0].get("backend_name", "QpiAI-QSV-Simulator")
    print(f"Attempting minimal circuit submission on remote backend: {target_backend}")
    try:
        # Submit job to remote backend via Circuit.run with Default Experiment
        job_result = qc.run(shots=10, device_name=target_backend, experiment_name="Default Experiment")
        print("Remote execution attempt succeeded!")
        print("Job Result / Details:", job_result)
        if hasattr(job_result, "job_id"):
            print("Job ID:", job_result.job_id)
        if hasattr(job_result, "get_counts"):
            print("Measurement counts:", job_result.get_counts())
    except Exception as e:
        print("Remote execution attempt failed or was blocked.")
        print(f"Captured Exception: {type(e).__name__}: {str(e)}")
