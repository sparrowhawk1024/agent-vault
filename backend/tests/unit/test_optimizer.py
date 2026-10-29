"""Unit tests for AgentVault optimizer engines and baseline comparison."""

import pytest
from backend.app.catalog.generator import generate_catalog
from backend.app.catalog.vendors import CATEGORIES
from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.solvers import ORToolsSolver, QpiAIOptSolver
from backend.app.optimizer.baselines import GreedyBaselineSolver, VendorRuleBaselineSolver
from backend.app.optimizer.selection import run_solver_comparison


@pytest.fixture
def test_quotes():
    return generate_catalog(seed=1, now_timestamp=1700000000)


@pytest.fixture
def standard_problem(test_quotes):
    # Only allowlisted vendors for standard problem
    allowed_quotes = [q for q in test_quotes if q["isAllowedVendor"]]
    requirements = {
        CATEGORIES["API_CALLS"]["id"]: 15_000,
        CATEGORIES["AI_CREDITS"]["id"]: 8_000,
        CATEGORIES["STORAGE"]["id"]: 1_200,
    }
    return ProcurementProblem(
        quotes=allowed_quotes,
        requirements=requirements,
        max_budget=100_000_000,  # 100 USDC
        max_lines=16,
    )


def test_ortools_solver_optimal(standard_problem):
    solver = ORToolsSolver()
    result = solver.solve(standard_problem)

    assert result.feasible is True
    assert result.status == "OPTIMAL"
    assert result.execution_mode == "LOCAL_OR_TOOLS"
    assert len(result.selected_quotes) <= 16
    assert result.total_cost > 0

    # Calibration test: optimal basket should be between $15 and $40 USDC (15M to 40M micro-USDC)
    assert 15_000_000 <= result.total_cost <= 40_000_000, f"Cost was {result.total_cost}"

    # Verify coverage
    for cat_id, req in standard_problem.requirements.items():
        assert result.coverage[cat_id] >= req


def test_qpiai_opt_solver_fallback_behavior(standard_problem, monkeypatch):
    # 1. Unset key -> must fall back gracefully to CLASSICAL_FALLBACK
    monkeypatch.delenv("QPIAI_OPT_API_KEY", raising=False)
    solver = QpiAIOptSolver()
    result = solver.solve(standard_problem)

    assert result.feasible is True
    assert result.execution_mode == "CLASSICAL_FALLBACK"
    assert "qpiai-opt-milp" in result.solver_name
    assert result.error_detail is not None
    assert "QPIAI_OPT_API_KEY" in result.error_detail or "client=Client" in result.error_detail

    # 2. Invalid/unreachable key -> must classify error and fall back cleanly
    monkeypatch.setenv("QPIAI_OPT_API_KEY", "invalid-test-token-1234")
    solver_invalid = QpiAIOptSolver()
    result_invalid = solver_invalid.solve(standard_problem)

    assert result_invalid.feasible is True
    assert result_invalid.execution_mode == "CLASSICAL_FALLBACK"
    assert "AUTHENTICATION_FAILURE" in result_invalid.error_detail or "AuthenticationError" in result_invalid.error_detail


def test_baseline_solvers_and_calibration(standard_problem):
    report = run_solver_comparison(standard_problem)

    ref_cost = report.reference_optimum_cost
    greedy_cost = report.results["greedy"].total_cost
    vendor_rule_cost = report.results["vendor_rule"].total_cost

    assert report.results["greedy"].feasible is True
    assert report.results["vendor_rule"].feasible is True

    # Optimum must be <= both baselines
    assert ref_cost <= greedy_cost
    assert ref_cost <= vendor_rule_cost

    # Calibration: Naive vendor rule should cost at least 15% more than the exact optimum
    assert report.savings_vs_vendor_rule_pct >= 15.0, (
        f"Savings vs vendor rule was only {report.savings_vs_vendor_rule_pct}% "
        f"(ref={ref_cost}, vendor_rule={vendor_rule_cost})"
    )
