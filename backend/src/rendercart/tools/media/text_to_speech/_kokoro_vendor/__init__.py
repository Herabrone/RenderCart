"""Vendored, license-preserving English Kokoro inference implementation."""

__version__ = "0.9.4"

from .model import KModel
from .pipeline import KPipeline

__all__ = ["KModel", "KPipeline"]
