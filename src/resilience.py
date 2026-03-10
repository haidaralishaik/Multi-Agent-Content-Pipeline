"""
Resilience Layer - Retry logic and circuit breaker for API calls

Provides exponential backoff retry with jitter and a circuit breaker
to handle transient failures from AWS Bedrock gracefully.
"""

import time
import random
import logging
from typing import Callable, TypeVar, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_retries: int = 3
    base_delay: float = 1.0         # seconds
    max_delay: float = 30.0         # seconds
    exponential_base: float = 2.0
    retryable_exceptions: Tuple[type, ...] = (Exception,)


class RetryHandler:
    """
    Executes functions with exponential backoff retry and jitter.

    Tracks retry history for observability.
    """

    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.retry_history: list = []

    def execute_with_retry(self, func: Callable[..., T],
                           *args: Any, **kwargs: Any) -> T:
        """
        Execute function with retry logic.

        On transient failure, waits with exponential backoff + jitter
        before retrying. Returns the result on success or raises the
        last exception after all retries are exhausted.
        """
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except self.config.retryable_exceptions as e:
                last_exception = e

                if attempt < self.config.max_retries:
                    delay = min(
                        self.config.base_delay * (self.config.exponential_base ** attempt),
                        self.config.max_delay
                    )
                    # Add jitter (0.5x to 1.5x)
                    delay *= (0.5 + random.random())

                    self.retry_history.append({
                        'attempt': attempt + 1,
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'delay': round(delay, 2),
                    })

                    logger.warning(
                        f"Retry {attempt + 1}/{self.config.max_retries} "
                        f"after {delay:.1f}s: {type(e).__name__}: {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"All {self.config.max_retries} retries exhausted: "
                        f"{type(e).__name__}: {e}"
                    )

        raise last_exception


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent repeated calls to failing services.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is down, requests fail immediately
    - HALF_OPEN: Testing if service recovered
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5,
                 recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: float = 0
        self.state = self.CLOSED

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function through the circuit breaker."""
        if self.state == self.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = self.HALF_OPEN
                logger.info("Circuit breaker: OPEN -> HALF_OPEN (testing recovery)")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN (failures={self.failure_count}). "
                    f"Retry after {self.recovery_timeout - (time.time() - self.last_failure_time):.0f}s"
                )

        try:
            result = func(*args, **kwargs)

            # Success: reset on half-open, keep closed
            if self.state == self.HALF_OPEN:
                self.state = self.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker: HALF_OPEN -> CLOSED (service recovered)")

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = self.OPEN
                logger.error(
                    f"Circuit breaker: -> OPEN after {self.failure_count} failures"
                )

            raise


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting calls."""
    pass
