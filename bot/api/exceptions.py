"""Custom exceptions for Exchange API operations"""


class ExchangeAPIError(Exception):
    """Base exception for all Exchange API errors"""

    pass


class RateLimitError(ExchangeAPIError):
    """Raised when exchange rate limit is exceeded"""

    pass


class AuthenticationError(ExchangeAPIError):
    """Raised when API key authentication fails"""

    pass


class InsufficientFundsError(ExchangeAPIError):
    """Raised when account has insufficient funds for operation"""

    pass


class OrderError(ExchangeAPIError):
    """Raised when order placement or management fails"""

    pass


class NetworkError(ExchangeAPIError):
    """Raised when network communication with exchange fails"""

    pass


class ExchangeNotAvailableError(ExchangeAPIError):
    """Raised when exchange is not available (maintenance, etc.)"""

    pass


class InvalidOrderError(ExchangeAPIError):
    """Raised when order parameters are invalid"""

    pass
