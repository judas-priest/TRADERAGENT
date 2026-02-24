"""
Shared rate limiter for the Web API.

Auth endpoints: 5 req/min per IP
All other endpoints: 60 req/min per IP (default)
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
)
