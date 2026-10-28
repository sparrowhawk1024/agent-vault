"""Test a real procurement problem using qpiai_opt modeller and local solver."""
import json
import time
from qpiai_opt.opt_modeller import Model, Binary, quicksum
from qpiai_opt.opt_solvers import solve

# Define a real procurement scenario
# Items: 4 vendor packs for 2 product categories:
# Cat A: AI_CREDITS (need >= 100 units)
# Cat B: API_CALLS  (need >= 50 units)
#
# Pack 0: Vendor 1 - AI_CREDITS: 60 units, price: 15_000_000 micro-USDC (15 USDC)
# Pack 1: Vendor 1 - AI_CREDITS: 120 units, price: 25_000_000 micro-USDC (25 USDC)
# Pack 2: Vendor 2 - API_CALLS: 30 units, price: 8_000_000 micro-USDC (8 USDC)
# Pack 3: Vendor 2 - API_CALLS: 60 units, price: 12_000_000 micro-USDC (12 USDC)

model = Model(name="ProcurementTest")

x0 = Binary("pack_0")
x1 = Binary("pack_1")
x2 = Binary("pack_2")
x3 = Binary("pack_3")

model.add_variables([x0, x1, x2, x3])

# Objective: Minimize cost in micro-USDC
cost_expr = 15_000_000 * x0 + 25_000_000 * x1 + 8_000_000 * x2 + 12_000_000 * x3
model.minimize(cost_expr)

# Coverage constraint Cat A (AI_CREDITS): need >= 100
model.add_constraint(60 * x0 + 120 * x1 >= 100)

# Coverage constraint Cat B (API_CALLS): need >= 50
model.add_constraint(30 * x2 + 60 * x3 >= 50)

print("Solving procurement model with mode='local'...")
start_t = time.time()
result = solve(model, mode="local")
elapsed = time.time() - start_t

print("Solve finished in:", elapsed)
print("Result type:", type(result))
print("Result attributes:", [a for a in dir(result) if not a.startswith("_")])
if hasattr(result, "objective_value"):
    print("Objective value:", result.objective_value)
if hasattr(result, "solution"):
    print("Solution:", result.solution)
if hasattr(result, "status"):
    print("Status:", result.status)
if hasattr(result, "variable_values"):
    print("Variable values:", result.variable_values)
