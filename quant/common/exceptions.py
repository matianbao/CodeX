class QuantError(Exception):
    """Base framework exception."""


class DataNotFoundError(QuantError):
    """Raised when market data is missing."""


class InvalidOrderError(QuantError):
    """Raised when an order request is invalid."""


class InsufficientCashError(QuantError):
    """Raised when the account cannot afford a trade."""
