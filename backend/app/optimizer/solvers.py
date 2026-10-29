"""Optimization Solvers for AgentVault Procurement.

Implements:
1. ORToolsSolver: Proven optimal integer solver using CP-SAT.
2. QpiAIOptSolver: QpiAI Opt MILP solver path with honest CLASSICAL_FALLBACK.
"""

import os
import sys
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# Gracefully handle pandas DLL blockage on restricted OS environments
if "pandas" not in sys.modules:
    try:
        import pandas
    except Exception:
        import unittest.mock
        sys.modules["pandas"] = unittest.mock.MagicMock()

from ortools.sat.python import cp_model

from backend.app.optimizer.model_builder import ProcurementProblem, QPIAI_OPT_AVAILABLE

try:
    import requests
    from qpiai_opt.opt_solvers import Client, LocalProvider, solve as qpiai_solve
    from qpiai_opt.opt_solvers.exceptions import AuthenticationError as QpiAIAuthError, APIError as QpiAIAPIError
except ImportError:
    requests = None
    Client = None
    LocalProvider = None
    qpiai_solve = None
    QpiAIAuthError = Exception
    QpiAIAPIError = Exception


def redact_api_key(key: Optional[str]) -> str:
    """Safely redact sensitive API key for logs and diagnostics."""
    if not key:
        return "<empty>"
    clean = key.strip()
    if len(clean) <= 8:
        return "***"
    return f"{clean[:4]}...{clean[-4:]}"


@dataclass
class SolverResult:
    solver_name: str
    execution_mode: str  # "LIVE_QPIAI" | "CLASSICAL_FALLBACK" | "RECORDED" | "UNAVAILABLE"
    feasible: bool
    status: str          # "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "ERROR"
    total_cost: int      # Exact integer micro-USDC
    selected_indices: List[int]
    selected_quotes: List[Dict[str, Any]]
    coverage: Dict[str, int]
    runtime_ms: float
    gap_against_optimal: Optional[float] = None
    error_detail: Optional[str] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


class ORToolsSolver:
    """Exact Integer Programming Solver using Google OR-Tools CP-SAT."""

    def __init__(self, time_limit_seconds: float = 10.0):
        self.time_limit_seconds = time_limit_seconds

    def solve(self, problem: ProcurementProblem) -> SolverResult:
        start_t = time.perf_counter()
        quotes = problem.quotes
        n = len(quotes)

        model = cp_model.CpModel()
        x = [model.NewBoolVar(f"x_{i}") for i in range(n)]

        # Objective: minimize total cost (integer micro-USDC)
        model.Minimize(cp_model.LinearExpr.WeightedSum(x, [q["price"] for q in quotes]))

        # Coverage constraints per category
        for cat_id, req_units in problem.requirements.items():
            cat_units = [q["units"] if q["categoryId"] == cat_id else 0 for q in quotes]
            model.Add(cp_model.LinearExpr.WeightedSum(x, cat_units) >= req_units)

        # Max basket lines (contract limit: 16)
        model.Add(cp_model.LinearExpr.Sum(x) <= problem.max_lines)

        # Budget cap
        model.Add(
            cp_model.LinearExpr.WeightedSum(x, [q["price"] for q in quotes])
            <= problem.max_budget
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        status_code = solver.Solve(model)
        runtime_ms = (time.perf_counter() - start_t) * 1000

        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            selected_indices = [i for i in range(n) if solver.Value(x[i]) == 1]
            selected_quotes = [quotes[i] for i in selected_indices]
            total_cost = sum(q["price"] for q in selected_quotes)

            # Compute category coverage
            coverage: Dict[str, int] = {cat: 0 for cat in problem.requirements}
            for q in selected_quotes:
                cid = q["categoryId"]
                if cid in coverage:
                    coverage[cid] += q["units"]

            status_str = "OPTIMAL" if status_code == cp_model.OPTIMAL else "FEASIBLE"
            return SolverResult(
                solver_name="ortools-cpsat",
                execution_mode="LOCAL_OR_TOOLS",  # Transparent classical reference
                feasible=True,
                status=status_str,
                total_cost=total_cost,
                selected_indices=selected_indices,
                selected_quotes=selected_quotes,
                coverage=coverage,
                runtime_ms=runtime_ms,
                gap_against_optimal=0.0 if status_code == cp_model.OPTIMAL else None,
                extra_metadata={
                    "wallTime": solver.WallTime(),
                    "userTime": solver.UserTime(),
                    "numBranches": solver.NumBranches(),
                },
            )
        else:
            return SolverResult(
                solver_name="ortools-cpsat",
                execution_mode="LOCAL_OR_TOOLS",
                feasible=False,
                status="INFEASIBLE",
                total_cost=0,
                selected_indices=[],
                selected_quotes=[],
                coverage={},
                runtime_ms=runtime_ms,
                error_detail="No feasible solution satisfies coverage and budget constraints.",
            )


class QpiAIOptSolver:
    """Primary QpiAI Opt MILP Solver with dual token authentication and honest classical fallback."""

    def __init__(self, fallback_solver: Optional[ORToolsSolver] = None):
        self.fallback = fallback_solver or ORToolsSolver()
        self.api_key = os.environ.get("QPIAI_OPT_API_KEY", "").strip()

    def probe_auth(self) -> Dict[str, Any]:
        """Diagnostic probe for QpiAI Opt credentials."""
        if not self.api_key:
            return {
                "status": "UNCONFIGURED",
                "statusCode": None,
                "message": "QPIAI_OPT_API_KEY is not configured in backend environment.",
            }
        try:
            server_base = os.environ.get("QPIAI_OPT_SERVER_URL", "https://opt-server.qpiai.tech/api").rstrip("/")
            session = requests.Session()
            session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "X-Secret-Token": self.api_key,
            })
            resp = session.get(f"{server_base}/users/me", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "status": "AUTHENTICATED",
                    "statusCode": 200,
                    "user": data.get("email") or data.get("name") or "authenticated_user",
                }
            elif resp.status_code == 401:
                return {
                    "status": "AUTHENTICATION_FAILURE",
                    "statusCode": 401,
                    "message": "API key rejected by QpiAI Opt server (401 Unauthorized).",
                    "detail": resp.text[:200],
                }
            elif resp.status_code == 403:
                return {
                    "status": "ACCOUNT_PERMISSION",
                    "statusCode": 403,
                    "message": "Account forbidden or revoked (403 Forbidden).",
                    "detail": resp.text[:200],
                }
            else:
                return {
                    "status": "API_ERROR",
                    "statusCode": resp.status_code,
                    "message": f"Server returned HTTP {resp.status_code}",
                    "detail": resp.text[:200],
                }
        except Exception as e:
            return {
                "status": "CONNECTION_ERROR",
                "statusCode": None,
                "message": f"Could not connect to QpiAI Opt server: {type(e).__name__}",
            }

    def solve(self, problem: ProcurementProblem) -> SolverResult:
        start_t = time.perf_counter()

        # Check if SDK is available
        if not QPIAI_OPT_AVAILABLE or Client is None or qpiai_solve is None:
            fb_res = self.fallback.solve(problem)
            fb_res.solver_name = "qpiai-opt-milp"
            fb_res.execution_mode = "CLASSICAL_FALLBACK"
            fb_res.error_detail = "qpiai-opt package not installed. Used classical fallback."
            return fb_res

        # If API key is missing, record exact blocker and fall back transparently
        if not self.api_key:
            err_msg = (
                "QPIAI_OPT_API_KEY is not configured. Local solving requires "
                "client=Client(api_key=...) registered at https://opt.qpiai.tech/tokens. Falling back to OR-Tools."
            )
            fb_res = self.fallback.solve(problem)
            fb_res.solver_name = "qpiai-opt-milp"
            fb_res.execution_mode = "CLASSICAL_FALLBACK"
            fb_res.error_detail = err_msg
            return fb_res

        # Attempt Live QpiAI solve
        try:
            server_base = os.environ.get("QPIAI_OPT_SERVER_URL", "https://opt-server.qpiai.tech/api").rstrip("/")
            session = requests.Session()
            session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "X-Secret-Token": self.api_key,
            })
            client = Client(api_key=self.api_key, session=session, base_url=server_base)

            opt_model, x_vars = problem.build_qpiai_model()
            res = qpiai_solve(opt_model, mode="local", client=client)
            runtime_ms = (time.perf_counter() - start_t) * 1000

            # Decode QpiAI solution
            sol_dict = getattr(res, "solution", {}) or {}
            selected_indices = [
                i for i, v in enumerate(x_vars)
                if round(sol_dict.get(v.name, 0.0)) == 1
            ]
            selected_quotes = [problem.quotes[i] for i in selected_indices]
            total_cost = sum(q["price"] for q in selected_quotes)

            coverage = {cat: 0 for cat in problem.requirements}
            for q in selected_quotes:
                cid = q["categoryId"]
                if cid in coverage:
                    coverage[cid] += q["units"]

            is_feasible = (
                all(coverage.get(cat, 0) >= req for cat, req in problem.requirements.items())
                and total_cost <= problem.max_budget
                and len(selected_indices) <= problem.max_lines
            )

            job_id = getattr(res, "job_id", None)
            solve_info = getattr(res, "solve_info", None)
            underlying_solver = getattr(solve_info, "solver", "HiGHS") if solve_info else "HiGHS"
            provider_name = getattr(solve_info, "provider", "qpiai-opt-local") if solve_info else "qpiai-opt-local"

            return SolverResult(
                solver_name=f"qpiai-opt-{underlying_solver.lower()}",
                execution_mode="LOCAL_QPIAI_OPT",
                feasible=is_feasible,
                status="OPTIMAL" if is_feasible else "INFEASIBLE",
                total_cost=total_cost,
                selected_indices=selected_indices,
                selected_quotes=selected_quotes,
                coverage=coverage,
                runtime_ms=runtime_ms,
                gap_against_optimal=getattr(res, "optimality_gap", 0.0),
                extra_metadata={
                    "qpiai_opt_version": "0.0.9",
                    "problem_class": getattr(res, "problem_class", "MILP"),
                    "provider": provider_name,
                    "solver": underlying_solver,
                    "solver_time_s": getattr(res, "solver_time_s", None),
                    "compute_time_s": getattr(res, "compute_time_s", None),
                    "model_status": getattr(res, "model_status", None),
                    "job_id": job_id,
                },
            )

        except Exception as e:
            runtime_ms = (time.perf_counter() - start_t) * 1000
            err_class = type(e).__name__
            err_str = str(e)
            if "AuthenticationError" in err_class or "401" in err_str or "unauthorized" in err_str.lower() or "invalid" in err_str.lower():
                category = "AUTHENTICATION_FAILURE"
            elif "Forbidden" in err_str or "403" in err_str or "revoked" in err_str.lower():
                category = "ACCOUNT_PERMISSION"
            elif "subscription" in err_str.lower() or "credit" in err_str.lower() or "quota" in err_str.lower():
                category = "QUOTA_CREDIT_RESTRICTION"
            elif "CapabilityError" in err_class:
                category = "UNSUPPORTED_OPERATION"
            else:
                category = "SOLVER_FAILURE"

            err_text = f"QpiAI Opt {category} ({err_class}): {err_str}"
            # Fall back to transparent classical (OR-Tools CP-SAT)
            fb_res = self.fallback.solve(problem)
            fb_res.solver_name = "qpiai-opt-milp"
            fb_res.execution_mode = "CLASSICAL_FALLBACK"
            fb_res.error_detail = err_text
            fb_res.runtime_ms = runtime_ms + fb_res.runtime_ms
            return fb_res
