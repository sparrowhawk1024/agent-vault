"""Optimization problem model builder for AgentVault procurement.

Formulates the exact procurement selection problem:
- Objective: Minimize sum(p_i * x_i) in integer micro-USDC
- Subject to:
    - Coverage per required category: sum(u_i * x_i for i in cat) >= req_units
    - Budget cap: sum(p_i * x_i) <= max_budget
    - Line limit: sum(x_i) <= max_lines (default 16)
    - Single-use quotes: x_i in {0, 1}
"""

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

try:
    from qpiai_opt.opt_modeller import Model, Binary
    QPIAI_OPT_AVAILABLE = True
except ImportError:
    QPIAI_OPT_AVAILABLE = False
    Model = None
    Binary = None


@dataclass
class ProcurementProblem:
    quotes: List[Dict[str, Any]]
    requirements: Dict[str, int]  # category_id (hex) -> min_units
    max_budget: int               # micro-USDC
    max_lines: int = 16

    def build_qpiai_model(self) -> Any:
        """Construct a QpiAI Opt Model instance."""
        if not QPIAI_OPT_AVAILABLE:
            raise RuntimeError("qpiai-opt package is not installed.")

        model = Model()
        n = len(self.quotes)
        x_vars = [Binary(f"x_{i}") for i in range(n)]
        for v in x_vars:
            model.add_variable(v)

        # 1. Objective: minimize total cost
        obj_expr = sum(self.quotes[i]["price"] * x_vars[i] for i in range(n))
        model.set_objective(obj_expr, sense="minimize")

        # 2. Coverage constraints per category
        for cat_id, req_units in self.requirements.items():
            cat_expr = sum(
                self.quotes[i]["units"] * x_vars[i]
                for i in range(n)
                if self.quotes[i]["categoryId"] == cat_id
            )
            model.add_constraint(cat_expr >= req_units)

        # 3. Maximum basket lines constraint (smart contract cap: 16)
        line_expr = sum(x_vars)
        model.add_constraint(line_expr <= self.max_lines)

        # 4. Budget cap constraint
        model.add_constraint(obj_expr <= self.max_budget)

        return model, x_vars
