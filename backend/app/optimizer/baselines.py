"""Purchasing Cost Baselines for AgentVault Procurement.

Implements:
1. GreedyBaselineSolver: Standard effective-unit-cost greedy heuristic for coverage.
2. VendorRuleBaselineSolver: Naive enterprise vendor-lock rule (preferred single vendor per category).
"""

import time
from typing import Dict, Any, List
from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.solvers import SolverResult


class GreedyBaselineSolver:
    """Greedy Heuristic: Selects quotes with the lowest effective price per needed unit.

    Effective unit price = price / min(units, remaining_needed_units)
    This avoids wasteful selection of massive packs that overshoot requirements.
    """

    def solve(self, problem: ProcurementProblem) -> SolverResult:
        start_t = time.perf_counter()
        quotes = problem.quotes
        requirements = dict(problem.requirements)
        max_budget = problem.max_budget
        max_lines = problem.max_lines

        acquired: Dict[str, int] = {cat: 0 for cat in requirements}
        selected_indices: List[int] = []
        current_cost = 0

        # Iteratively pick the quote with lowest effective cost for remaining deficit
        for _ in range(max_lines):
            deficit = {cat: requirements[cat] - acquired[cat] for cat in requirements if acquired[cat] < requirements[cat]}
            if not deficit:
                break

            best_idx = None
            best_eff_price = float("inf")

            for i, q in enumerate(quotes):
                if i in selected_indices:
                    continue
                cid = q["categoryId"]
                if cid not in deficit:
                    continue
                if current_cost + q["price"] > max_budget:
                    continue

                needed = deficit[cid]
                useful_units = min(q["units"], needed)
                if useful_units <= 0:
                    continue

                eff_price = q["price"] / useful_units
                if eff_price < best_eff_price:
                    best_eff_price = eff_price
                    best_idx = i

            if best_idx is None:
                break

            chosen_quote = quotes[best_idx]
            selected_indices.append(best_idx)
            current_cost += chosen_quote["price"]
            acquired[chosen_quote["categoryId"]] += chosen_quote["units"]

        runtime_ms = (time.perf_counter() - start_t) * 1000
        selected_quotes = [quotes[i] for i in selected_indices]
        feasible = all(acquired[cat] >= req for cat, req in requirements.items()) and current_cost <= max_budget

        return SolverResult(
            solver_name="greedy-baseline",
            execution_mode="CLASSICAL_FALLBACK",
            feasible=feasible,
            status="FEASIBLE" if feasible else "INFEASIBLE",
            total_cost=current_cost,
            selected_indices=selected_indices,
            selected_quotes=selected_quotes,
            coverage=acquired,
            runtime_ms=runtime_ms,
            error_detail=None if feasible else "Greedy search failed to satisfy coverage within limits.",
        )


class VendorRuleBaselineSolver:
    """Vendor-Rule Baseline: Naive single-vendor purchasing rule.

    Policy:
    - API_CALLS -> Buy from NimbusAPI (selects smallest pack satisfying requirement)
    - AI_CREDITS -> Buy from TokenForge (selects smallest pack satisfying requirement)
    - STORAGE -> Buy from VaultStore (selects smallest pack satisfying requirement)
    """

    PREFERRED_VENDORS = {
        "API_CALLS": "nimbusapi",
        "AI_CREDITS": "tokenforge",
        "STORAGE": "vaultstore",
    }

    def solve(self, problem: ProcurementProblem) -> SolverResult:
        start_t = time.perf_counter()
        quotes = problem.quotes
        requirements = dict(problem.requirements)
        max_budget = problem.max_budget
        max_lines = problem.max_lines

        acquired: Dict[str, int] = {cat: 0 for cat in requirements}
        selected_indices: List[int] = []
        current_cost = 0

        for cat_id, target_units in requirements.items():
            cat_quotes = [q for q in quotes if q["categoryId"] == cat_id]
            cat_name = cat_quotes[0]["categoryName"] if cat_quotes else ""
            pref_vendor_name = self.PREFERRED_VENDORS.get(cat_name, "")

            # Filter quotes to preferred vendor and sort ascending by units
            pref_candidates = [
                (i, q) for i, q in enumerate(quotes)
                if q["categoryId"] == cat_id and q.get("vendorName") == pref_vendor_name
            ]
            pref_candidates.sort(key=lambda item: item[1]["units"])

            # Find the smallest pack that covers the needed units, or stack packs
            needed = target_units - acquired[cat_id]
            covered = False

            # Check if a single pack satisfies needed
            for idx, q in pref_candidates:
                if q["units"] >= needed and (current_cost + q["price"] <= max_budget) and (len(selected_indices) < max_lines):
                    selected_indices.append(idx)
                    acquired[cat_id] += q["units"]
                    current_cost += q["price"]
                    covered = True
                    break

            # If no single pack covers, stack largest available
            if not covered:
                for idx, q in reversed(pref_candidates):
                    if acquired[cat_id] >= target_units:
                        break
                    if len(selected_indices) >= max_lines:
                        break
                    if current_cost + q["price"] > max_budget:
                        continue
                    if idx in selected_indices:
                        continue
                    selected_indices.append(idx)
                    acquired[cat_id] += q["units"]
                    current_cost += q["price"]

        runtime_ms = (time.perf_counter() - start_t) * 1000
        selected_quotes = [quotes[i] for i in selected_indices]
        feasible = all(acquired[cat] >= req for cat, req in requirements.items()) and current_cost <= max_budget

        return SolverResult(
            solver_name="vendor-rule-baseline",
            execution_mode="CLASSICAL_FALLBACK",
            feasible=feasible,
            status="FEASIBLE" if feasible else "INFEASIBLE",
            total_cost=current_cost,
            selected_indices=selected_indices,
            selected_quotes=selected_quotes,
            coverage=acquired,
            runtime_ms=runtime_ms,
            error_detail=None if feasible else "Vendor rule failed to satisfy requirements within budget.",
        )
