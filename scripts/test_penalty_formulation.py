import sys, os
sys.path.insert(0, os.path.abspath("."))
from backend.app.catalog.generator import generate_catalog

quotes = generate_catalog(seed=1, now_timestamp=1700000000, vault_address="0x1111111111111111111111111111111111111111")
allowed = [q for q in quotes if q.get("isAllowedVendor", True)]

api_q = sorted([q for q in allowed if q.get("categoryName") == "API_CALLS"], key=lambda x: (x["units"], x["price"]))[:4]
ai_q = sorted([q for q in allowed if q.get("categoryName") == "AI_CREDITS"], key=lambda x: (x["units"], x["price"]))[:4]
storage_q = sorted([q for q in allowed if q.get("categoryName") == "STORAGE"], key=lambda x: (x["units"], x["price"]))[:3]

eleven_quotes = api_q + ai_q + storage_q
n = len(eleven_quotes) # 11

reqs = {
    api_q[0]["categoryId"]: 2000,
    ai_q[0]["categoryId"]: 1000,
    storage_q[0]["categoryId"]: 200,
}

# Normalize costs to [0, 1] relative to sum of prices or max price
# Let's say cost in dollars:
prices_usd = [q["price"] / 1e6 for q in eleven_quotes]
opt_cost_usd = (eleven_quotes[2]["price"] + eleven_quotes[6]["price"] + eleven_quotes[10]["price"]) / 1e6
print(f"Optimum cost in USD: ${opt_cost_usd:.4f}")

# Category index sets:
cat_indices = {
    "API": [0, 1, 2, 3],       # units: 1000, 1000, 2000, 2000. req: 2000
    "AI": [4, 5, 6, 7],        # units: 500, 500, 1000, 1000. req: 1000
    "STORAGE": [8, 9, 10],     # units: 100, 100, 200. req: 200
}

# Let's test a quadratic penalty formulation:
# For API (req=2000):
# units in thousands: u = [1, 1, 2, 2], req = 2
# Possible sums of chosen units can be 0, 1, 2, 3, 4, 5, 6.
# If sum < 2, deficit is 2 - sum.
# To formulate as QUBO with <= 2-body interactions without adding qubits:
# What if we penalize deficit?
# For API:
# Notice that requirement is MET if (x2=1 or x3=1 or (x0=1 and x1=1)).
# The negation (unmet demand) is: (1 - x2)(1 - x3)(1 - x0 x1).
# Expanding this boolean expression:
# (1 - x2)(1 - x3) = 1 - x2 - x3 + x2 x3.
# If neither x2 nor x3 is selected, this is 1. If we also don't select BOTH x0 and x1:
# The penalty for not meeting API is:
# P_API(x) = A * [ (1 - x2 - x3 + x2 x3) + (1 - x0) + (1 - x1) ] ... wait, let's test exact quadratic forms!

# Let's test a quadratic penalty:
# For each cat, let penalty be:
# P_cat = A_cat * ( (R - sum u_i x_i) + slack )^2
# OR what if we formulate QUBO matrix Q directly?
print("\nTesting Penalty Formulations...")

