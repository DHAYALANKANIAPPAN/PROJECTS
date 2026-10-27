"""Airlock: Defending AI email agents against prompt injection via addressee and authority gates."""

from airlock.gate1 import gate1
from airlock.gate2 import gate2
from airlock.sanitizer import sanitize

__all__ = ["gate1", "gate2", "sanitize"]
__version__ = "0.1.0"
