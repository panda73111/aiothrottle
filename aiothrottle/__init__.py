"""
Providing classes for limiting data rates of asyncio sockets
"""

from .throttle import Throttle, ThrottledStreamReader, limit_rate, unlimit_rate

__version__ = "0.1.1"

__all__ = ("Throttle", "ThrottledStreamReader", "limit_rate", "unlimit_rate")
