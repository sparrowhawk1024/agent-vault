"""Solver comparison and selection suite for AgentVault Procurement.

Executes all supported solvers on identical problem instances and computes
objective values, feasibility, runtimes, and percentage savings against baselines.
"""

from typing import Dict, Any, List
from dataclasses import dataclass, asdict

from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.solvers import ORToolsSolver, QpiAIOptSolver, SolverResult
from backend.app.optimizer.baselines import GreedyBaselineSolver, VendorRuleBaselineSolver


@dataclass
class SolverComparisonReport:
    problem_summary: Dict[str, Any]
    reference_optimum_cost: int
    results: Dict[str, SolverResult]
    savings_vs_greedy_pct: float
    savings_vs_vendor_rule_pct: float
    optimal_basket: List[Dict[str, Any]]


def run_solver_comparison(problem: ProcurementProblem) -> SolverComparisonReport:
    """Run all solvers on the same instance and produce a comparative benchmark report."""
    # 1. Classical Reference Optimum (OR-Tools CP-SAT)
    ortools_solver = ORToolsSolver()
    ref_result = ortools_solver.solve(problem)

    # 2. QpiAI Opt Path
    qpiai_solver = QpiAIOptSolver(fallback_solver=ortools_solver)
    qpiai_result = qpiai_solver.solve(problem)

    # 3. Greedy Baseline
    greedy_solver = GreedyBaselineSolver()
    greedy_result = greedy_solver.solve(problem)

    # 4. Vendor-Rule Baseline
    vendor_rule_solver = VendorRuleBaselineSolver()
    vendor_rule_result = vendor_rule_solver.solve(problem)

    # Reference cost
    ref_cost = ref_result.total_cost if ref_result.feasible else 0

    # Compute percentage savings of optimal vs baselines
    savings_vs_greedy = 0.0
    if greedy_result.feasible and greedy_result.total_cost > 0:
        savings_vs_greedy = (
            (greedy_result.total_cost - ref_cost) / greedy_result.total_cost
        ) * 100.0

    savings_vs_vendor_rule = 0.0
    if vendor_rule_result.feasible and vendor_rule_result.total_cost > 0:
        savings_vs_vendor_rule = (
            (vendor_rule_result.total_cost - ref_cost) / vendor_rule_result.total_cost
        ) * 100.0

    return SolverComparisonReport(
        problem_summary={
            "requirements": problem.requirements,
            "maxBudget": problem.max_budget,
            "maxLines": problem.max_lines,
            "quoteCount": len(problem.quotes),
        },
        reference_optimum_cost=ref_cost,
        results={
            "ortools": ref_result,
            "qpiai": qpiai_result,
            "greedy": greedy_result,
            "vendor_rule": vendor_rule_result,
        },
        savings_vs_greedy_pct=round(savings_vs_greedy, 2),
        savings_vs_vendor_rule_pct=round(savings_vs_vendor_rule, 2),
        optimal_basket=ref_result.selected_quotes,
    )


def run_procurement_benchmark(
    catalog: List[Dict[str, Any]],
    requirements: Dict[str, int],
    max_budget: int = 50_000_000,
    seed: int = 1,
) -> Dict[str, Any]:
    """Helper for FastAPI API endpoint returning serialized benchmark results."""
    eligible_quotes = [q for q in catalog if q.get("isAllowedVendor", True)]
    problem = ProcurementProblem(
        quotes=eligible_quotes,
        requirements=requirements,
        max_budget=max_budget,
        max_lines=16,
    )
    report = run_solver_comparison(problem)

    def serialize_res(res: SolverResult):
        lines = [
            {
                "quoteId": q["quoteId"],
                "vendorId": q["vendorId"],
                "categoryId": q["categoryId"],
                "skuId": q["skuId"],
                "units": q["units"],
                "amount": q["price"],
            }
            for q in res.selected_quotes
        ]
        return {
            "solverName": res.solver_name,
            "executionMode": res.execution_mode,
            "feasible": res.feasible,
            "totalCost": res.total_cost,
            "coverage": res.coverage,
            "lineCount": len(res.selected_quotes),
            "basketLines": lines,
            "timingMs": round(res.runtime_ms, 2),
            "errorMessage": res.error_detail,
        }

    return {
        "summary": {
            "referenceOptimumCost": report.reference_optimum_cost,
            "savingsVsGreedyPct": report.savings_vs_greedy_pct,
            "savingsVsVendorRulePct": report.savings_vs_vendor_rule_pct,
            "seed": seed,
        },
        "solvers": {name: serialize_res(r) for name, r in report.results.items()},
    }

