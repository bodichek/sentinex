"""Insight Function exceptions."""


class InsightError(Exception):
    """Base class for Insight Function errors."""


class InsufficientData(InsightError):
    """Raised when underlying data is missing or too sparse to produce a result."""
