"""Unit tests for QAOA quantum procurement experiment using QpiAI Quantum SDK."""

import pytest
from backend.app.catalog.generator import generate_catalog
from backend.app.catalog.vendors import CATEGORIES
from backend.app.optimizer.qaoa_path import (
    formulate_reduced_procurement_ising,
    build_qaoa_circuit,
    run_qaoa_procurement_experiment,
    QPIAI_QUANTUM_AVAILABLE,
)


@pytest.fixture
def catalog_quotes():
    return generate_catalog(seed=1, now_timestamp=1700000000)


def test_qaoa_reduced_ising_formulation(catalog_quotes):
    eligible = [q for q in catalog_quotes if q.get("isAllowedVendor", True)]
    api_quotes = sorted([q for q in eligible if q.get("categoryName") == "API_CALLS"], key=lambda q: q["units"])
    ai_quotes = sorted([q for q in eligible if q.get("categoryName") == "AI_CREDITS"], key=lambda q: q["units"])

    four_quotes = [api_quotes[0], api_quotes[1], ai_quotes[0], ai_quotes[1]]
    reqs = {
        api_quotes[0]["categoryId"]: api_quotes[0]["units"],
        ai_quotes[0]["categoryId"]: ai_quotes[0]["units"],
    }

    h, J, offset = formulate_reduced_procurement_ising(four_quotes, reqs)
    assert len(h) == 4
    assert len(J) >= 2  # intra-category interactions between (0, 1) and (2, 3)
    assert (0, 1) in J
    assert (2, 3) in J


@pytest.mark.skipif(not QPIAI_QUANTUM_AVAILABLE, reason="qpiai-quantum is not installed")
def test_qaoa_procurement_experiment_execution(catalog_quotes):
    reqs = {
        CATEGORIES["API_CALLS"]["id"]: 5_000,
        CATEGORIES["AI_CREDITS"]["id"]: 2_000,
    }

    record = run_qaoa_procurement_experiment(catalog_quotes, reqs, shots=1024)

    assert record.status == "SUCCESS"
    assert record.qubit_count == 4
    assert record.shots == 1024
    assert record.backend_name == "qpiai_quantum.simulator.StatevectorSimulator"
    assert len(record.counts) > 0
    assert len(record.top_bitstrings) >= 1

    # Check decoded candidate
    cand = record.decoded_candidate
    assert "bitstring" in cand
    assert "totalCost" in cand
    assert isinstance(cand["totalCost"], int)
    assert cand["totalCost"] > 0

    # Check classical reference
    assert record.classical_reference["totalCost"] > 0
    assert record.classical_reference["feasible"] is True

    # Check runtime and mode
    assert record.runtime_seconds > 0
    assert record.execution_mode in ("LIVE_QPIAI", "CLASSICAL_FALLBACK")
