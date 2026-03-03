"""
MemCore Web Dashboard

Browser-based management interface for memories.
"""
from .server import DashboardServer, run_dashboard

__all__ = ["DashboardServer", "run_dashboard"]
