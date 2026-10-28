"""Unit tests for Verifier Waste Guard."""

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
