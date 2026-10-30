"""Independent Verifier Waste Guard for AgentVault.

Prevents wasteful or abusive autonomous spending baskets:
- Recomputes exact integer optimum over the verifier's own verified eligible quotes.
- Rejects baskets exceeding WASTE_TOLERANCE_BPS (default 10% / 1000 bps) over reference cost.
- Rejects unjustified excess units exceeding EXCESS_UNITS_MARGIN_BPS.
- Fails closed with VERIFIER_UNAVAILABLE if the benchmark solver cannot execute (F-04).
"""

import sys
from typing import Dict, Any, List, Tuple, Optional

if "pandas" not in sys.modules:
    try:
        import pandas
    except Exception:
        import unittest.mock
        sys.modules["pandas"] = unittest.mock.MagicMock()

from ortools.sat.python import cp_model

from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.solvers import ORToolsSolver


class WasteGuard:
    def __init__(
        self,
        waste_tolerance_bps: int = 1000,       # 10% tolerance over optimal cost
        excess_units_margin_bps: int = 1000,   # 10% margin over optimal coverage
        solver_time_limit_seconds: float = 5.0,
    ):
        self.waste_tolerance_bps = waste_tolerance_bps
        self.excess_units_margin_bps = excess_units_margin_bps
        self.solver_time_limit_seconds = solver_time_limit_seconds
        self.is_solver_available = True  # Can be disabled for F-04 simulation

    def disable_solver_for_testing(self):
        """Simulate solver crash or unavailable dependency (F-04)."""
        self.is_solver_available = False

    def enable_solver(self):
        """Restore solver availability."""
        self.is_solver_available = True

    def evaluate_basket(
        self,
        candidate_lines: List[Dict[str, Any]],
        quotes_by_id: Dict[str, Dict[str, Any]],
        eligible_quotes: List[Dict[str, Any]],
        requirements: Dict[str, int],
        max_budget: int,
    ) -> Tuple[bool, Optional[str], Optional[str], Dict[str, Any]]:
        """Evaluate candidate basket against an independent OR-Tools CP-SAT benchmark.

        Returns (passed, reason_code, detail, benchmark_metadata).
        """
        metadata: Dict[str, Any] = {
            "wasteToleranceBps": self.waste_tolerance_bps,
            "excessUnitsMarginBps": self.excess_units_margin_bps,
        }

        # 1. Fail-closed check if solver is disabled/unavailable (F-04)
        if not self.is_solver_available:
            return (
                False,
                "VERIFIER_UNAVAILABLE",
                "Waste-benchmark solver is unavailable; failing closed per verification policy",
                metadata,
            )

        # 2. Recompute candidate metrics
        candidate_cost = sum(int(line["amount"]) for line in candidate_lines)
        candidate_units: Dict[str, int] = {cat: 0 for cat in requirements}

        for line in candidate_lines:
            qid = line["quoteId"]
            if qid in quotes_by_id:
                q = quotes_by_id[qid]
                cid = q["categoryId"]
                if cid in candidate_units:
                    candidate_units[cid] += int(q["units"])

        metadata["candidateCost"] = candidate_cost
        metadata["candidateUnits"] = candidate_units

        # 3. Verify coverage meets minimum requirement
        for cat_id, req_units in requirements.items():
            acquired = candidate_units.get(cat_id, 0)
            if acquired < req_units:
                return (
                    False,
                    "REQUIREMENT_NOT_MET",
                    f"Coverage for category {cat_id} ({acquired}) is below requirement ({req_units})",
                    metadata,
                )

        # 4. Compute independent benchmark optimum over verifier's eligible quotes
        problem = ProcurementProblem(
            quotes=eligible_quotes,
            requirements=requirements,
            max_budget=max_budget,
            max_lines=16,
        )

        try:
            solver = ORToolsSolver(time_limit_seconds=self.solver_time_limit_seconds)
            bench_res = solver.solve(problem)
        except Exception as e:
            # F-04: If solver throws unexpected error, fail closed
            return (
                False,
                "VERIFIER_UNAVAILABLE",
                f"Benchmark computation threw exception: {type(e).__name__}: {str(e)}",
                metadata,
            )

        if not bench_res.feasible:
            # If no feasible combination exists even in eligible quotes
            return (
                False,
                "REQUIREMENT_NOT_MET",
                "Verifier cannot find any feasible combination in verified eligible quotes",
                metadata,
            )

        # Fail closed if benchmark solver stopped at FEASIBLE instead of proving OPTIMAL (e.g. timeout / incomplete search)
        if bench_res.status != "OPTIMAL":
            return (
                False,
                "VERIFIER_UNAVAILABLE",
                f"Waste-benchmark solver status is '{bench_res.status}' (not OPTIMAL); failing closed per verification policy",
                metadata,
            )

        ref_opt_cost = bench_res.total_cost
        ref_opt_coverage = bench_res.coverage
        metadata["referenceOptimalCost"] = ref_opt_cost
        metadata["referenceOptimalCoverage"] = ref_opt_coverage

        # 5. Check monetary waste threshold
        # max_allowed_cost = ref_opt_cost * (1 + waste_tolerance_bps / 10000)
        max_allowed_cost = (ref_opt_cost * (10_000 + self.waste_tolerance_bps)) // 10_000
        metadata["maxAllowedCost"] = max_allowed_cost

        if candidate_cost > max_allowed_cost:
            excess_cost = candidate_cost - ref_opt_cost
            pct_over = round((excess_cost / ref_opt_cost) * 100, 2)
            return (
                False,
                "WASTEFUL_BASKET",
                f"Candidate cost {candidate_cost} exceeds optimal benchmark {ref_opt_cost} by {pct_over}% (tolerance: {self.waste_tolerance_bps/100}%)",
                metadata,
            )

        # 6. Check excess units waste threshold
        for cat_id, req_units in requirements.items():
            cand_u = candidate_units.get(cat_id, 0)
            bench_u = ref_opt_coverage.get(cat_id, req_units)
            # Threshold accounts for pack lumpiness discovered by benchmark
            baseline_u = max(req_units, bench_u)
            max_allowed_units = (baseline_u * (10_000 + self.excess_units_margin_bps)) // 10_000

            if cand_u > max_allowed_units:
                return (
                    False,
                    "WASTEFUL_BASKET",
                    f"Candidate supplied {cand_u} units for category {cat_id}, exceeding allowance of {max_allowed_units} (baseline {baseline_u})",
                    metadata,
                )

        return True, None, "Waste guard check passed", metadata
