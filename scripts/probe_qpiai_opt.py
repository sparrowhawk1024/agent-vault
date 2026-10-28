"""Probe script for qpiai_opt modeller and solvers."""
import inspect
import qpiai_opt
from qpiai_opt import opt_modeller, opt_solvers

print("qpiai_opt version:", getattr(qpiai_opt, "__version__", "unknown"))

# Inspect Model in opt_modeller
Model = opt_modeller.Model
print("Model constructor:", inspect.signature(Model.__init__))
print("Model methods:", [m for m in dir(Model) if not m.startswith("_")])

# Inspect variables
Binary = opt_modeller.Binary
print("Binary signature:", inspect.signature(Binary.__init__))

# Inspect opt_solvers
print("opt_solvers dir:", [s for s in dir(opt_solvers) if not s.startswith("_")])
if hasattr(opt_solvers, "LocalProvider"):
    LP = opt_solvers.LocalProvider
    print("LocalProvider methods:", [m for m in dir(LP) if not m.startswith("_")])
if hasattr(opt_solvers, "solve"):
    print("solve signature:", inspect.signature(opt_solvers.solve))
