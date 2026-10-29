import sys, os
sys.path.insert(0, os.path.abspath("."))
from backend.app.catalog.generator import generate_catalog
from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.solvers import ORToolsSolver

quotes = generate_catalog(seed=1, now_timestamp=1700000000, vault_address="0x1111111111111111111111111111111111111111")
allowed = [q for q in quotes if q.get("isAllowedVendor", True)]

# Select 10 quotes across all 3 categories:
# 4 API (1000, 1000, 2000, 2000)
# 4 AI (500, 500, 1000, 1000)
# 2 Storage (100, 100) or 3 Storage (100, 100, 200)
api_q = sorted([q for q in allowed if q.get("categoryName") == "API_CALLS"], key=lambda x: (x["units"], x["price"]))[:4]
ai_q = sorted([q for q in allowed if q.get("categoryName") == "AI_CREDITS"], key=lambda x: (x["units"], x["price"]))[:4]
storage_q = sorted([q for q in allowed if q.get("categoryName") == "STORAGE"], key=lambda x: (x["units"], x["price"]))[:3]

ten_quotes = api_q + ai_q + storage_q
n = len(ten_quotes)
print(f"Selected {n} candidate quotes:")
for i, q in enumerate(ten_quotes):
    print(f"  q{i}: {q['categoryName']:<10} units={q['units']:<6} price={q['price']} (${q['price']/1e6:.2f})")

reqs = {
    api_q[0]["categoryId"]: 2000,
    ai_q[0]["categoryId"]: 1000,
    storage_q[0]["categoryId"]: 200,
}
print("\nRequirements:", reqs)

problem = ProcurementProblem(quotes=ten_quotes, requirements=reqs, max_budget=40_000_000, max_lines=16)
opt = ORToolsSolver().solve(problem)
print(f"\nClassical Optimum Cost: {opt.total_cost} (${opt.total_cost/1e6:.2f}), Selected indices: {opt.selected_indices}")

