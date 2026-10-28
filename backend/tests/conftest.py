"""Pytest configuration for AgentVault test suite.

Ensures proper mock for pandas if Windows Application Control blocks its native DLL.
"""

import sys
import unittest.mock

# Ensure mock for pandas if blocked by Windows Application Control policy
if "pandas" not in sys.modules:
    try:
        import pandas
    except Exception:
        sys.modules["pandas"] = unittest.mock.MagicMock()
