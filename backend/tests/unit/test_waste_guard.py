"""Unit tests for Verifier Waste Guard."""

import random
import pytest
from backend.app.catalog.generator import generate_catalog
from backend.app.catalog.vendors import CATEGORIES
from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.solvers import ORToolsSolver
from backend.app.verifier.waste_guard import WasteGuard


@pytest.fixture
def catalog_quotes():
    quotes = generate_catalog(seed=1, now_timestamp=1700000000)
    return [q for q in quotes if q["isAllowedVendor"]]


@pytest.fixture
def requirements():
    return {
        CATEGORIES["API_CALLS"]["id"]: 10_000,
        CATEGORIES["AI_CREDITS"]["id"]: 5_000,
        CATEGORIES["STORAGE"]["id"]: 1_000,
    }


def test_waste_guard_accepts_optimal_candidate(catalog_quotes, requirements):
    guard = WasteGuard(waste_tolerance_bps=1000)  # 10%
    problem = ProcurementProblem(
        quotes=catalog_quotes,
        requirements=requirements,
        max_budget=100_000_000,
    )
    opt_result = ORToolsSolver().solve(problem)
    assert opt_result.feasible

    # Build lines from optimal candidate
    lines = [
        {
            "quoteId": q["quoteId"],
            "vendorId": q["vendorId"],
            "categoryId": q["categoryId"],
            "amount": q["price"],
        }
        for q in opt_result.selected_quotes
    ]
    quotes_map = {q["quoteId"]: q for q in catalog_quotes}

    passed, reason, detail, meta = guard.evaluate_basket(
        candidate_lines=lines,
        quotes_by_id=quotes_map,
        eligible_quotes=catalog_quotes,
        requirements=requirements,
        max_budget=100_000_000,
    )

    assert passed is True
    assert reason is None
    assert meta["candidateCost"] == opt_result.total_cost


def test_waste_guard_rejects_wasteful_basket(catalog_quotes, requirements):
    guard = WasteGuard(waste_tolerance_bps=1000)  # 10%
    problem = ProcurementProblem(
        quotes=catalog_quotes,
        requirements=requirements,
        max_budget=100_000_000,
    )
    opt_result = ORToolsSolver().solve(problem)
    assert opt_result.feasible

    # Fabricate an overly expensive basket with amounts inflated by 30% (> 10% tolerance)
    quotes_map = {q["quoteId"]: q for q in catalog_quotes}
    expensive_lines = [
        {
            "quoteId": q["quoteId"],
            "vendorId": q["vendorId"],
            "categoryId": q["categoryId"],
            "amount": int(round(q["price"] * 1.30)),
        }
        for q in opt_result.selected_quotes
    ]

    passed, reason, detail, meta = guard.evaluate_basket(
        candidate_lines=expensive_lines,
        quotes_by_id=quotes_map,
        eligible_quotes=catalog_quotes,
        requirements=requirements,
        max_budget=100_000_000,
    )

    assert passed is False
    assert reason == "WASTEFUL_BASKET"
    assert "exceeds optimal benchmark" in detail


def test_waste_guard_rejects_insufficient_coverage(catalog_quotes, requirements):
    guard = WasteGuard()
    quotes_map = {q["quoteId"]: q for q in catalog_quotes}

    # Pass an empty basket or one line that doesn't cover all categories
    single_quote = catalog_quotes[0]
    lines = [
        {
            "quoteId": single_quote["quoteId"],
            "vendorId": single_quote["vendorId"],
            "categoryId": single_quote["categoryId"],
            "amount": single_quote["price"],
        }
    ]

    passed, reason, detail, meta = guard.evaluate_basket(
        candidate_lines=lines,
        quotes_by_id=quotes_map,
        eligible_quotes=catalog_quotes,
        requirements=requirements,
        max_budget=100_000_000,
    )

    assert passed is False
    assert reason == "REQUIREMENT_NOT_MET"


def test_waste_guard_fails_closed_when_solver_disabled(catalog_quotes, requirements):
    # F-04: solver unavailable must fail closed with VERIFIER_UNAVAILABLE
    guard = WasteGuard()
    guard.disable_solver_for_testing()

    quotes_map = {q["quoteId"]: q for q in catalog_quotes}
    problem = ProcurementProblem(
        quotes=catalog_quotes,
        requirements=requirements,
        max_budget=100_000_000,
    )
    opt_result = ORToolsSolver().solve(problem)

    lines = [
        {
            "quoteId": q["quoteId"],
            "vendorId": q["vendorId"],
            "categoryId": q["categoryId"],
            "amount": q["price"],
        }
        for q in opt_result.selected_quotes
    ]

    passed, reason, detail, meta = guard.evaluate_basket(
        candidate_lines=lines,
        quotes_by_id=quotes_map,
        eligible_quotes=catalog_quotes,
        requirements=requirements,
        max_budget=100_000_000,
    )

    assert passed is False
    assert reason == "VERIFIER_UNAVAILABLE"
    assert "failing closed" in detail


def test_waste_guard_omission_attack(catalog_quotes, requirements):
    """1. Omission attack: Agent hides cheaper quotes from candidate catalog.
    Verifier benchmark uses its own verified eligible quotes, uncovering the omission and rejecting.
    """
    guard = WasteGuard(waste_tolerance_bps=1000)
    
    # Simulate omission: agent creates candidate basket excluding the cheapest quotes (only expensive ones)
    sorted_quotes = sorted(catalog_quotes, key=lambda q: q["price"])
    expensive_subset = sorted_quotes[len(sorted_quotes) // 2:]
    
    agent_problem = ProcurementProblem(
        quotes=expensive_subset,
        requirements=requirements,
        max_budget=100_000_000,
    )
    agent_res = ORToolsSolver().solve(agent_problem)
    assert agent_res.feasible
    
    lines = [
        {
            "quoteId": q["quoteId"],
            "vendorId": q["vendorId"],
            "categoryId": q["categoryId"],
            "amount": q["price"],
        }
        for q in agent_res.selected_quotes
    ]
    quotes_map = {q["quoteId"]: q for q in catalog_quotes}
    
    # The verifier passes its OWN complete eligible quotes (all valid signed quotes)
    passed, reason, detail, meta = guard.evaluate_basket(
        candidate_lines=lines,
        quotes_by_id=quotes_map,
        eligible_quotes=catalog_quotes,  # Full verifier catalog
        requirements=requirements,
        max_budget=100_000_000,
    )
    
    assert passed is False
    assert reason == "WASTEFUL_BASKET"
    assert meta["candidateCost"] > meta["referenceOptimalCost"]
    print(f"\n[Omission Attack Raw Output] Rejected: {reason} | Candidate Cost: ${meta['candidateCost']/1e6:.2f} | Verifier Optimal Benchmark: ${meta['referenceOptimalCost']/1e6:.2f} | Excess: {detail}")


def test_waste_guard_solver_status_non_optimal_fails_closed(catalog_quotes, requirements, monkeypatch):
    """2. Solver status: force a CP-SAT solver status of FEASIBLE instead of OPTIMAL.
    Verifier must return VERIFIER_UNAVAILABLE (fail closed), never approving on non-proven optimum.
    """
    guard = WasteGuard()
    quotes_map = {q["quoteId"]: q for q in catalog_quotes}
    
    problem = ProcurementProblem(
        quotes=catalog_quotes,
        requirements=requirements,
        max_budget=100_000_000,
    )
    opt_result = ORToolsSolver().solve(problem)
    lines = [
        {"quoteId": q["quoteId"], "vendorId": q["vendorId"], "categoryId": q["categoryId"], "amount": q["price"]}
        for q in opt_result.selected_quotes
    ]
    
    # Mock ORToolsSolver.solve inside waste_guard to return FEASIBLE instead of OPTIMAL
    from backend.app.verifier.waste_guard import ORToolsSolver as WGSolver
    original_solve = WGSolver.solve
    def mock_solve(self, prob):
        res = original_solve(self, prob)
        res.status = "FEASIBLE"
        return res
        
    monkeypatch.setattr("backend.app.verifier.waste_guard.ORToolsSolver.solve", mock_solve)
    
    passed, reason, detail, meta = guard.evaluate_basket(
        candidate_lines=lines,
        quotes_by_id=quotes_map,
        eligible_quotes=catalog_quotes,
        requirements=requirements,
        max_budget=100_000_000,
    )
    
    assert passed is False
    assert reason == "VERIFIER_UNAVAILABLE"
    assert "not OPTIMAL" in detail
    print(f"\n[Solver Status Raw Output] Status: {reason} | Detail: {detail}")


def test_waste_guard_property_random_requirements(catalog_quotes):
    """3. Property test: 200 random requirements per seed (seeds 1, 2, 3 = 600 total).
    Optimizer's optimal basket must pass WasteGuard without false rejections.
    """
    guard = WasteGuard(waste_tolerance_bps=1000)
    quotes_map = {q["quoteId"]: q for q in catalog_quotes}
    solver = ORToolsSolver(time_limit_seconds=2.0)
    
    false_rejections = []
    total_feasible = 0
    
    for s in (1, 2, 3):
        rng = random.Random(s * 1000)
        for i in range(200):
            reqs = {
                CATEGORIES["API_CALLS"]["id"]: rng.randint(1000, 15000),
                CATEGORIES["AI_CREDITS"]["id"]: rng.randint(500, 8000),
                CATEGORIES["STORAGE"]["id"]: rng.randint(100, 1500),
            }
            problem = ProcurementProblem(quotes=catalog_quotes, requirements=reqs, max_budget=100_000_000, max_lines=16)
            res = solver.solve(problem)
            if not res.feasible:
                continue
            total_feasible += 1
            lines = [{"quoteId": q["quoteId"], "vendorId": q["vendorId"], "categoryId": q["categoryId"], "amount": q["price"]} for q in res.selected_quotes]
            passed, reason, detail, meta = guard.evaluate_basket(lines, quotes_map, catalog_quotes, reqs, 100_000_000)
            if not passed:
                false_rejections.append((s, i, reqs, reason, detail))
                
    assert len(false_rejections) == 0, f"False rejections found: {false_rejections}"
    print(f"\n[Property Test Raw Output] Tested Feasible: {total_feasible}/600 across seeds 1-3 | False Rejections: {len(false_rejections)}")


def test_waste_guard_lumpy_pack_case():
    """4. Lumpy pack case: need=100, packs available are 500 and 1000 units.
    Evaluates whether excess-units rule handles lumpiness properly.
    """
    cat_id = CATEGORIES["STORAGE"]["id"]
    quotes = [
        {"quoteId": "q_500", "vendorId": "0x1111111111111111111111111111111111111111", "categoryId": cat_id, "units": 500, "price": 500_000, "isAllowedVendor": True},
        {"quoteId": "q_1000", "vendorId": "0x1111111111111111111111111111111111111111", "categoryId": cat_id, "units": 1000, "price": 900_000, "isAllowedVendor": True},
    ]
    quotes_map = {q["quoteId"]: q for q in quotes}
    guard = WasteGuard(excess_units_margin_bps=1000)  # 10%
    
    # Candidate buys 500 pack (optimum)
    lines_500 = [{"quoteId": "q_500", "vendorId": "0x1111111111111111111111111111111111111111", "categoryId": cat_id, "amount": 500_000}]
    passed_opt, reason_opt, detail_opt, meta_opt = guard.evaluate_basket(
        candidate_lines=lines_500,
        quotes_by_id=quotes_map,
        eligible_quotes=quotes,
        requirements={cat_id: 100},
        max_budget=10_000_000,
    )
    
    # Candidate buys 1000 pack (wasteful bloat)
    lines_1000 = [{"quoteId": "q_1000", "vendorId": "0x1111111111111111111111111111111111111111", "categoryId": cat_id, "amount": 900_000}]
    passed_excess, reason_excess, detail_excess, meta_excess = guard.evaluate_basket(
        candidate_lines=lines_1000,
        quotes_by_id=quotes_map,
        eligible_quotes=quotes,
        requirements={cat_id: 100},
        max_budget=10_000_000,
    )
    
    # The optimal 500 pack passes because WasteGuard baseline dynamically uses max(requirement, benchmark_optimum_units)
    assert passed_opt is True
    assert passed_excess is False
    print(f"\n[Lumpy Pack Raw Output] 500-pack (need 100): Passed={passed_opt} | 1000-pack: Passed={passed_excess} (Reason: {reason_excess})")

