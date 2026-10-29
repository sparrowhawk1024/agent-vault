import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("QCLOUD_API_KEY")
if not key:
    raise RuntimeError("QCLOUD_API_KEY is missing from environment")

from qpiai_quantum import Circuit, QpiAIQuantumAuth
login = QpiAIQuantumAuth.login

# Authenticate with your QCloud API key
login(key)

# Check available remote backends/QPUs
print("--- Available Compute Resources ---")
resources = QpiAIQuantumAuth.list_compute_resources()

# Build the circuit
qc = Circuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

# Attempt with "QpiAI-QSV-Cloud"
print("\n--- Submitting with device_name='QpiAI-QSV-Cloud' ---")
try:
    job = qc.run(
        shots=4096,
        experiment_name="Bell_State_Cloud_Run",
        device_name="QpiAI-QSV-Cloud",
    )
    counts = job.get_counts()
    print(f"Job ID: {getattr(job, 'job_id', 'N/A')}")
    print(f"Results: {counts}")
except Exception as e:
    print(f"Error ({type(e).__name__}): {e}")

# Attempt with "QpiAI-QSV-Simulator"
print("\n--- Submitting with device_name='QpiAI-QSV-Simulator' ---")
try:
    job = qc.run(
        shots=4096,
        experiment_name="Bell_State_Cloud_Run",
        device_name="QpiAI-QSV-Simulator",
    )
    counts = job.get_counts()
    print(f"Job ID: {getattr(job, 'job_id', 'N/A')}")
    print(f"Results: {counts}")
except Exception as e:
    print(f"Error ({type(e).__name__}): {e}")

